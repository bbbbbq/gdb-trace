from __future__ import annotations

from .trace_model import TraceEvent


ANSI_CYAN = "\x1b[36m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"
INDENT = " " * 4


def render_log_header(
    runtime: dict[str, object],
    snapshot_kind: str,
    render_mode: str,
    output_path: str,
) -> list[str]:
    config = runtime["config"]
    filters = runtime["filters"]
    lines = [
        f"{ANSI_CYAN}[trace {snapshot_kind}]{ANSI_RESET} "
        f"target={runtime['target']} arch={config['arch']} elf={config['elf']} "
        f"trace_mode={render_mode} status={runtime['status']} start_time={runtime['started_at']}",
        f"[output] path={output_path}",
        f"[capture] backend={runtime['capture_backend']} events={runtime['event_count']}",
    ]
    if filters.get("start"):
        lines.append(f"[range] start={filters['start']}")
    if filters.get("stop"):
        lines.append(f"[range] stop={filters['stop']}")
    if filters.get("filter_func"):
        lines.append(f"[filter] func={filters['filter_func']}")
    if filters.get("filter_range"):
        lines.append(f"[filter] range={filters['filter_range']}")
    return lines


def format_inst(events: list[TraceEvent]) -> list[str]:
    return [f"{event.pc} {event.instruction}" for event in events if event.kind == "inst"]


def format_call(events: list[TraceEvent]) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.kind == "call":
            lines.append(f"{INDENT * event.depth}{ANSI_GREEN}call {event.function}{ANSI_RESET}")
        elif event.kind == "ret":
            lines.append(f"{INDENT * event.depth}{ANSI_RED}ret {event.function}{ANSI_RESET}")
    return lines


def format_both(events: list[TraceEvent]) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.kind == "call":
            lines.append(f"{INDENT * event.depth}{ANSI_GREEN}call {event.function}{ANSI_RESET}")
        elif event.kind == "ret":
            lines.append(f"{INDENT * event.depth}{ANSI_RED}ret {event.function}{ANSI_RESET}")
        else:
            lines.append(f"{INDENT * event.depth}{event.pc} {event.instruction}")
    return lines


def render_log(runtime: dict[str, object], snapshot_kind: str, mode: str | None = None, output_path: str | None = None) -> str:
    render_mode = mode or runtime["config"]["mode"]
    render_output_path = output_path or runtime["config"]["output"]
    events = [TraceEvent(**event) for event in runtime["events"]]
    lines = render_log_header(runtime, snapshot_kind, render_mode, render_output_path)
    lines.append("")
    if render_mode == "inst":
        lines.extend(format_inst(events))
    elif render_mode == "call":
        lines.extend(format_call(events))
    else:
        lines.extend(format_both(events))
    return "\n".join(lines) + "\n"
