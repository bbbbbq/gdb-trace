from __future__ import annotations

from .trace_model import TraceEvent


ANSI_CYAN = "\x1b[36m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"
INDENT = " " * 4


def _register_order(arch: str) -> list[str]:
    if arch == "aarch64":
        return [*(f"x{index}" for index in range(31)), "sp"]
    if arch in {"arm32", "thumb", "thumb2"}:
        return [*(f"r{index}" for index in range(13)), "sp", "lr"]
    if arch == "riscv32" or arch == "riscv64":
        return [
            "ra",
            "sp",
            "gp",
            "tp",
            "t0",
            "t1",
            "t2",
            "s0",
            "s1",
            "a0",
            "a1",
            "a2",
            "a3",
            "a4",
            "a5",
            "a6",
            "a7",
            "s2",
            "s3",
            "s4",
            "s5",
            "s6",
            "s7",
            "s8",
            "s9",
            "s10",
            "s11",
            "t3",
            "t4",
            "t5",
            "t6",
        ]
    return []


def _ordered_register_items(registers: dict[str, str], arch: str) -> list[tuple[str, str]]:
    preferred_order = _register_order(arch)
    ordered_names = [name for name in preferred_order if name in registers]
    ordered_names.extend(sorted(name for name in registers if name not in set(ordered_names)))
    return [(name, registers[name]) for name in ordered_names]


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
    if config.get("registers", "off") == "on":
        lines.append("[registers] on")
    if filters.get("start"):
        lines.append(f"[range] start={filters['start']}")
    if filters.get("stop"):
        lines.append(f"[range] stop={filters['stop']}")
    if filters.get("filter_func"):
        lines.append(f"[filter] func={filters['filter_func']}")
    if filters.get("filter_range"):
        lines.append(f"[filter] range={filters['filter_range']}")
    return lines


def _register_line(event: TraceEvent, indent_level: int, arch: str) -> str:
    register_payload = " ".join(
        f"{name}={value}" for name, value in _ordered_register_items(event.registers, arch)
    )
    return f"{INDENT * indent_level}regs: {register_payload}"


def format_inst(events: list[TraceEvent], arch: str) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.kind != "inst":
            continue
        lines.append(f"{event.pc} {event.instruction}")
        if event.registers:
            lines.append(_register_line(event, 1, arch))
    return lines


def format_call(events: list[TraceEvent]) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.kind == "call":
            lines.append(f"{INDENT * event.depth}{ANSI_GREEN}call {event.function}{ANSI_RESET}")
        elif event.kind == "ret":
            lines.append(f"{INDENT * event.depth}{ANSI_RED}ret {event.function}{ANSI_RESET}")
    return lines


def format_both(events: list[TraceEvent], arch: str) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.kind == "call":
            lines.append(f"{INDENT * event.depth}{ANSI_GREEN}call {event.function}{ANSI_RESET}")
        elif event.kind == "ret":
            lines.append(f"{INDENT * event.depth}{ANSI_RED}ret {event.function}{ANSI_RESET}")
        else:
            lines.append(f"{INDENT * event.depth}{event.pc} {event.instruction}")
            if event.registers:
                lines.append(_register_line(event, event.depth + 1, arch))
    return lines


def render_log(runtime: dict[str, object], snapshot_kind: str, mode: str | None = None, output_path: str | None = None) -> str:
    render_mode = mode or runtime["config"]["mode"]
    render_output_path = output_path or runtime["config"]["output"]
    events = [TraceEvent(**event) for event in runtime["events"]]
    arch = runtime["config"]["arch"]
    lines = render_log_header(runtime, snapshot_kind, render_mode, render_output_path)
    lines.append("")
    if render_mode == "inst":
        lines.extend(format_inst(events, arch))
    elif render_mode == "call":
        lines.extend(format_call(events))
    else:
        lines.extend(format_both(events, arch))
    return "\n".join(lines) + "\n"
