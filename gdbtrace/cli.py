from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .capture import CaptureRequest, resolve_capture_backend
from .filters import apply_filters
from .formatter import render_log
from .state import (
    GdbTraceError,
    Paths,
    clear_file,
    resolve_paths,
    runtime_state,
    save_runtime_state,
    save_session_state,
    session_state,
    validate_arch,
    validate_mode,
    validate_output,
    validate_registers,
    validate_target,
)
from .trace_model import TraceEvent


CommandHandler = Callable[[argparse.Namespace, Paths], int]


def _set_session_value(paths: Paths, key: str, value: str) -> int:
    payload = session_state(paths)
    payload[key] = value
    save_session_state(paths, payload)
    print(f"{key}={value}")
    return 0


def _clear_session_value(paths: Paths, key: str) -> int:
    payload = session_state(paths)
    payload.pop(key, None)
    if payload:
        save_session_state(paths, payload)
    else:
        clear_file(paths.session_file)
    print(f"cleared {key}")
    return 0


def cmd_set_arch(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "arch", validate_arch(args.arch))


def cmd_set_elf(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "elf", args.elf)


def cmd_set_output(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "output", validate_output(args.output))


def cmd_set_mode(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "mode", validate_mode(args.mode))


def cmd_set_registers(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "registers", validate_registers(args.registers))


def cmd_show_config(_: argparse.Namespace, paths: Paths) -> int:
    payload = session_state(paths)
    for key in ("arch", "elf", "output", "mode", "registers"):
        print(f"{key}={payload.get(key, '<unset>')}")
    return 0


def cmd_clear_arch(_: argparse.Namespace, paths: Paths) -> int:
    return _clear_session_value(paths, "arch")


def cmd_clear_elf(_: argparse.Namespace, paths: Paths) -> int:
    return _clear_session_value(paths, "elf")


def cmd_clear_output(_: argparse.Namespace, paths: Paths) -> int:
    return _clear_session_value(paths, "output")


def cmd_clear_mode(_: argparse.Namespace, paths: Paths) -> int:
    return _clear_session_value(paths, "mode")


def cmd_clear_registers(_: argparse.Namespace, paths: Paths) -> int:
    return _clear_session_value(paths, "registers")


def _active_runtime(paths: Paths) -> dict[str, str]:
    runtime = runtime_state(paths)
    if runtime.get("capture_in_progress"):
        runtime = _finalize_interrupted_runtime(paths, runtime)
    return runtime


def _required_config(session: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for key in ("arch", "elf", "output", "mode"):
        if not session.get(key):
            missing.append(key)
    return missing


def _capture_target_from_env() -> str:
    target = os.environ.get("GDBTRACE_GDB_TARGET", "")
    if not target:
        return ""
    return validate_target(target)


def _derived_call_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.call.log")


def _log_targets(runtime: dict[str, object]) -> list[tuple[Path, str]]:
    output_path = Path(runtime["config"]["output"])
    mode = runtime["config"]["mode"]
    if mode == "both":
        return [
            (output_path, "both"),
            (_derived_call_output_path(output_path), "call"),
        ]
    return [(output_path, mode)]


def _write_log_snapshot(runtime: dict[str, object], snapshot_kind: str) -> None:
    for output_path, mode in _log_targets(runtime):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            render_log(runtime, snapshot_kind, mode=mode, output_path=str(output_path)),
            encoding="utf-8",
        )


def _snapshot_output_message(runtime: dict[str, object]) -> str:
    return ", ".join(str(path) for path, _ in _log_targets(runtime))


def _capture_registers_enabled(session: dict[str, str]) -> bool:
    return session.get("registers", "off") == "on" and session.get("mode") != "call"


def _is_capture_interrupt(exc: BaseException) -> bool:
    if isinstance(exc, KeyboardInterrupt):
        return True
    message = str(exc).lower()
    return "interrupted" in message or "quit" in message or "sigint" in message


def _capture_spool_path(paths: Paths) -> Path:
    runtime_name = paths.runtime_file.name
    return paths.runtime_file.with_name(f"{runtime_name}.events.jsonl")


def _runtime_filters(args: argparse.Namespace) -> dict[str, str]:
    return {
        "start": args.start_addr or "",
        "stop": args.stop_addr or "",
        "filter_func": args.filter_func or "",
        "filter_range": args.filter_range or "",
    }


def _runtime_payload(
    session: dict[str, str],
    filters: dict[str, str],
    *,
    status: str,
    started_at: str,
    target: str,
    capture_backend: str,
    events: list[TraceEvent] | None = None,
) -> dict[str, object]:
    payload_events = events or []
    return {
        "status": status,
        "started_at": started_at,
        "target": target,
        "config": {
            "arch": session["arch"],
            "elf": session["elf"],
            "output": session["output"],
            "mode": session["mode"],
            "registers": session.get("registers", "off"),
        },
        "capture_backend": capture_backend,
        "event_count": len(payload_events),
        "filters": filters,
        "events": [event.__dict__ for event in payload_events],
    }


def _append_spooled_events(spool_path: Path, events: list[dict[str, object]]) -> None:
    if not events:
        return
    spool_path.parent.mkdir(parents=True, exist_ok=True)
    with spool_path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")


def _load_spooled_events(spool_path: Path) -> list[TraceEvent]:
    if not spool_path.exists():
        return []
    events: list[TraceEvent] = []
    with spool_path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            events.append(TraceEvent(**json.loads(stripped)))
    return events


def _filtered_runtime_events(
    raw_events: list[TraceEvent],
    filters: dict[str, str],
    *,
    best_effort: bool,
) -> list[TraceEvent]:
    try:
        return apply_filters(
            raw_events,
            start=filters.get("start", ""),
            stop=filters.get("stop", ""),
            filter_func=filters.get("filter_func", ""),
            filter_range=filters.get("filter_range", ""),
        )
    except GdbTraceError:
        if best_effort:
            return raw_events
        raise


def _finalize_interrupted_runtime(paths: Paths, runtime: dict[str, object]) -> dict[str, object]:
    spool_text = str(runtime.get("capture_spool", ""))
    spool_path = Path(spool_text) if spool_text else _capture_spool_path(paths)
    raw_events = _load_spooled_events(spool_path)
    filtered_events = _filtered_runtime_events(
        raw_events,
        runtime.get("filters", {}),
        best_effort=True,
    )
    runtime["events"] = [event.__dict__ for event in filtered_events]
    runtime["event_count"] = len(filtered_events)
    runtime["status"] = "paused"
    runtime.pop("capture_in_progress", None)
    runtime.pop("capture_spool", None)
    save_runtime_state(paths, runtime)
    clear_file(spool_path)
    _write_log_snapshot(runtime, "snapshot")
    return runtime


def cmd_start(args: argparse.Namespace, paths: Paths) -> int:
    runtime = _active_runtime(paths)
    if runtime.get("status") == "running":
        raise GdbTraceError("trace is already running")
    if runtime.get("status") == "paused":
        if any((args.start_addr, args.stop_addr, args.filter_func, args.filter_range)):
            raise GdbTraceError("cannot change trace arguments while resuming a paused trace")
        runtime["status"] = "running"
        save_runtime_state(paths, runtime)
        print("trace resumed")
        return 0

    session = session_state(paths)
    missing = _required_config(session)
    if missing:
        raise GdbTraceError(f"missing required trace config: {', '.join(missing)}")

    backend = resolve_capture_backend()
    started_at = datetime.now(timezone.utc).isoformat()
    filters = _runtime_filters(args)
    capture_request = CaptureRequest(
        arch=session["arch"],
        mode=session["mode"],
        target=_capture_target_from_env(),
        elf=session["elf"],
        registers=_capture_registers_enabled(session),
    )
    spool_path = _capture_spool_path(paths)
    clear_file(spool_path)
    provisional_runtime = _runtime_payload(
        session,
        filters,
        status="running",
        started_at=started_at,
        target="gdb-managed" if backend.name == "gdb-current-session" else backend.name,
        capture_backend=backend.name,
    )
    if backend.name == "gdb-current-session":
        provisional_runtime["capture_in_progress"] = True
        provisional_runtime["capture_spool"] = str(spool_path)
    save_runtime_state(paths, provisional_runtime)
    try:
        capture_result = backend.capture(
            capture_request,
            event_sink=(
                (lambda pending_events: _append_spooled_events(spool_path, pending_events))
                if backend.name == "gdb-current-session"
                else None
            ),
        )
    except BaseException as exc:
        if not (backend.name == "gdb-current-session" and _is_capture_interrupt(exc)):
            clear_file(spool_path)
            clear_file(paths.runtime_file)
        raise

    try:
        filtered_events = _filtered_runtime_events(
            capture_result.events,
            filters,
            best_effort=False,
        )
        new_runtime = _runtime_payload(
            session,
            filters,
            status="paused" if capture_result.interrupted else "running",
            started_at=started_at,
            target=capture_result.target_label,
            capture_backend=capture_result.backend,
            events=filtered_events,
        )
        save_runtime_state(paths, new_runtime)
        clear_file(spool_path)
    except BaseException:
        clear_file(spool_path)
        clear_file(paths.runtime_file)
        raise
    if capture_result.interrupted:
        _write_log_snapshot(new_runtime, "snapshot")
        print(f"trace interrupted, paused, and saved to {_snapshot_output_message(new_runtime)}")
    else:
        print("trace started")
    return 0


def cmd_pause(_: argparse.Namespace, paths: Paths) -> int:
    runtime = _active_runtime(paths)
    if runtime.get("status") != "running":
        raise GdbTraceError("no running trace to pause")
    runtime["status"] = "paused"
    save_runtime_state(paths, runtime)
    print("trace paused")
    return 0


def cmd_save(_: argparse.Namespace, paths: Paths) -> int:
    runtime = _active_runtime(paths)
    if runtime.get("status") not in {"running", "paused"}:
        raise GdbTraceError("no active trace to save")
    _write_log_snapshot(runtime, "snapshot")
    print(f"trace saved to {_snapshot_output_message(runtime)}")
    return 0


def cmd_stop(_: argparse.Namespace, paths: Paths) -> int:
    runtime = _active_runtime(paths)
    if runtime.get("status") not in {"running", "paused"}:
        raise GdbTraceError("no active trace to stop")
    _write_log_snapshot(runtime, "final")
    output_message = _snapshot_output_message(runtime)
    clear_file(paths.runtime_file)
    print(f"trace stopped and saved to {output_message}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdbtrace")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_command(name: str, handler: CommandHandler) -> argparse.ArgumentParser:
        subparser = subparsers.add_parser(name)
        subparser.set_defaults(handler=handler)
        return subparser

    add_command("set-arch", cmd_set_arch).add_argument("arch")
    add_command("set-elf", cmd_set_elf).add_argument("elf")
    add_command("set-output", cmd_set_output).add_argument("output")
    add_command("set-mode", cmd_set_mode).add_argument("mode")
    add_command("set-registers", cmd_set_registers).add_argument("registers")
    add_command("show-config", cmd_show_config)
    add_command("clear-arch", cmd_clear_arch)
    add_command("clear-elf", cmd_clear_elf)
    add_command("clear-output", cmd_clear_output)
    add_command("clear-mode", cmd_clear_mode)
    add_command("clear-registers", cmd_clear_registers)

    start_parser = add_command("start", cmd_start)
    start_parser.add_argument("--start", dest="start_addr")
    start_parser.add_argument("--stop", dest="stop_addr")
    start_parser.add_argument("--filter-func")
    start_parser.add_argument("--filter-range")
    add_command("pause", cmd_pause)
    add_command("save", cmd_save)
    add_command("stop", cmd_stop)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = resolve_paths()
    try:
        return args.handler(args, paths)
    except GdbTraceError as exc:
        print(f"error: {exc}")
        return 1
