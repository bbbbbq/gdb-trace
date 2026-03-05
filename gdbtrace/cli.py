from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .filters import apply_filters
from .formatter import render_log
from .state import (
    GdbTraceError,
    Paths,
    clear_file,
    resolve_paths,
    runtime_state,
    save_global_state,
    save_runtime_state,
    save_session_state,
    session_state,
    global_state,
    validate_arch,
    validate_mode,
    validate_output,
    validate_target,
)
from .trace_model import sample_trace_events


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


def cmd_set_target(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "target", validate_target(args.target))


def cmd_set_default_target(args: argparse.Namespace, paths: Paths) -> int:
    payload = global_state(paths)
    payload["default_target"] = validate_target(args.target)
    save_global_state(paths, payload)
    print(f"default_target={payload['default_target']}")
    return 0


def cmd_show_target(_: argparse.Namespace, paths: Paths) -> int:
    session = session_state(paths)
    global_cfg = global_state(paths)
    current = session.get("target")
    default = global_cfg.get("default_target")
    effective = current or default
    print(f"current_target={current or '<unset>'}")
    print(f"default_target={default or '<unset>'}")
    print(f"effective_target={effective or '<unset>'}")
    return 0


def cmd_clear_target(_: argparse.Namespace, paths: Paths) -> int:
    return _clear_session_value(paths, "target")


def cmd_clear_default_target(_: argparse.Namespace, paths: Paths) -> int:
    payload = global_state(paths)
    payload.pop("default_target", None)
    if payload:
        save_global_state(paths, payload)
    else:
        clear_file(paths.global_config_file)
    print("cleared default_target")
    return 0


def cmd_set_arch(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "arch", validate_arch(args.arch))


def cmd_set_elf(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "elf", args.elf)


def cmd_set_output(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "output", validate_output(args.output))


def cmd_set_mode(args: argparse.Namespace, paths: Paths) -> int:
    return _set_session_value(paths, "mode", validate_mode(args.mode))


def cmd_show_config(_: argparse.Namespace, paths: Paths) -> int:
    payload = session_state(paths)
    for key in ("arch", "elf", "output", "mode"):
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


def _active_runtime(paths: Paths) -> dict[str, str]:
    return runtime_state(paths)


def _required_config(session: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for key in ("arch", "elf", "output", "mode"):
        if not session.get(key):
            missing.append(key)
    return missing


def _resolve_target(paths: Paths, explicit_target: str | None) -> str:
    if explicit_target:
        return validate_target(explicit_target)
    session = session_state(paths)
    if session.get("target"):
        return session["target"]
    global_cfg = global_state(paths)
    if global_cfg.get("default_target"):
        return global_cfg["default_target"]
    raise GdbTraceError("remote target is not configured")


def _write_log_snapshot(runtime: dict[str, object], snapshot_kind: str) -> None:
    output_path = Path(runtime["config"]["output"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_log(runtime, snapshot_kind), encoding="utf-8")


def cmd_start(args: argparse.Namespace, paths: Paths) -> int:
    runtime = _active_runtime(paths)
    if runtime.get("status") == "running":
        raise GdbTraceError("trace is already running")
    if runtime.get("status") == "paused":
        if any((args.target, args.start_addr, args.stop_addr, args.filter_func, args.filter_range)):
            raise GdbTraceError("cannot change trace arguments while resuming a paused trace")
        runtime["status"] = "running"
        save_runtime_state(paths, runtime)
        print("trace resumed")
        return 0

    session = session_state(paths)
    missing = _required_config(session)
    if missing:
        raise GdbTraceError(f"missing required trace config: {', '.join(missing)}")

    target = _resolve_target(paths, args.target)
    source_events = sample_trace_events(session["arch"])
    filtered_events = apply_filters(
        source_events,
        start=args.start_addr or "",
        stop=args.stop_addr or "",
        filter_func=args.filter_func or "",
        filter_range=args.filter_range or "",
    )
    new_runtime = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "config": {
            "arch": session["arch"],
            "elf": session["elf"],
            "output": session["output"],
            "mode": session["mode"],
        },
        "filters": {
            "start": args.start_addr or "",
            "stop": args.stop_addr or "",
            "filter_func": args.filter_func or "",
            "filter_range": args.filter_range or "",
        },
        "events": [event.__dict__ for event in filtered_events],
    }
    save_runtime_state(paths, new_runtime)
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
    print(f"trace saved to {runtime['config']['output']}")
    return 0


def cmd_stop(_: argparse.Namespace, paths: Paths) -> int:
    runtime = _active_runtime(paths)
    if runtime.get("status") not in {"running", "paused"}:
        raise GdbTraceError("no active trace to stop")
    _write_log_snapshot(runtime, "final")
    clear_file(paths.runtime_file)
    print(f"trace stopped and saved to {runtime['config']['output']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdbtrace")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_command(name: str, handler: CommandHandler) -> argparse.ArgumentParser:
        subparser = subparsers.add_parser(name)
        subparser.set_defaults(handler=handler)
        return subparser

    add_command("set-target", cmd_set_target).add_argument("target")
    add_command("set-default-target", cmd_set_default_target).add_argument("target")
    add_command("show-target", cmd_show_target)
    add_command("clear-target", cmd_clear_target)
    add_command("clear-default-target", cmd_clear_default_target)

    add_command("set-arch", cmd_set_arch).add_argument("arch")
    add_command("set-elf", cmd_set_elf).add_argument("elf")
    add_command("set-output", cmd_set_output).add_argument("output")
    add_command("set-mode", cmd_set_mode).add_argument("mode")
    add_command("show-config", cmd_show_config)
    add_command("clear-arch", cmd_clear_arch)
    add_command("clear-elf", cmd_clear_elf)
    add_command("clear-output", cmd_clear_output)
    add_command("clear-mode", cmd_clear_mode)

    start_parser = add_command("start", cmd_start)
    start_parser.add_argument("--target")
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
