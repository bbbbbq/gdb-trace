from __future__ import annotations

import json
import os
import re
from pathlib import Path

import gdb


INSTRUCTION_RE = re.compile(r"(?:=>\s*)?(0x[0-9a-fA-F]+)(?:\s+<[^>]+>)?:\s*(.*)")
ENTRY_RE = re.compile(r"Entry point:\s*(0x[0-9a-fA-F]+)")


def _relevant_stack() -> list[str]:
    frame = gdb.selected_frame()
    names: list[str] = []
    found_main = False
    while frame is not None:
        name = frame.name()
        if name:
            names.append(name)
            if name == "main":
                found_main = True
                break
        frame = frame.older()
    if not found_main:
        return []
    return list(reversed(names))


def _current_instruction() -> tuple[str, str]:
    line = gdb.execute("x/i $pc", to_string=True).strip()
    match = INSTRUCTION_RE.search(line)
    if not match:
        raise RuntimeError(f"failed to parse instruction line: {line}")
    pc = match.group(1).lower()
    instruction = " ".join(match.group(2).replace("\t", " ").split())
    return pc, instruction


def _common_prefix_size(left: list[str], right: list[str]) -> int:
    common = 0
    for left_value, right_value in zip(left, right):
        if left_value != right_value:
            break
        common += 1
    return common


def _entry_point() -> str:
    info = gdb.execute("info files", to_string=True)
    match = ENTRY_RE.search(info)
    if not match:
        raise RuntimeError("failed to determine ELF entry point")
    return match.group(1).lower()


def _emit_call_events(events: list[dict[str, object]], stack: list[str]) -> None:
    for depth, function in enumerate(stack):
        events.append({"kind": "call", "depth": depth, "function": function, "pc": "", "instruction": ""})


def _emit_stack_transition(
    events: list[dict[str, object]],
    previous_stack: list[str],
    next_stack: list[str],
) -> None:
    common = _common_prefix_size(previous_stack, next_stack)
    for depth in range(len(previous_stack) - 1, common - 1, -1):
        events.append(
            {
                "kind": "ret",
                "depth": depth,
                "function": previous_stack[depth],
                "pc": "",
                "instruction": "",
            }
        )
    for depth in range(common, len(next_stack)):
        events.append(
            {
                "kind": "call",
                "depth": depth,
                "function": next_stack[depth],
                "pc": "",
                "instruction": "",
            }
        )


def _step_until_exit(max_steps: int, events: list[dict[str, object]]) -> int:
    steps = 0
    while steps < max_steps:
        try:
            pc, instruction = _current_instruction()
        except gdb.error as exc:
            if "No registers" in str(exc):
                break
            raise
        events.append(
            {
                "kind": "inst",
                "depth": 0,
                "function": "",
                "pc": pc,
                "instruction": instruction,
            }
        )
        steps += 1

        try:
            gdb.execute("stepi")
        except gdb.error as exc:
            message = str(exc)
            if "exited" not in message and "Inferior" not in message and "program is not being run" not in message:
                raise
            break
    return steps


def run() -> None:
    elf = os.environ["GDBTRACE_GDB_ELF"]
    output_path = Path(os.environ["GDBTRACE_GDB_OUTPUT"])
    max_steps = int(os.environ.get("GDBTRACE_GDB_MAX_STEPS", "4096"))
    transport = os.environ.get("GDBTRACE_GDB_TRANSPORT", "native")
    symbol_mode = os.environ.get("GDBTRACE_GDB_SYMBOL_MODE", "main")

    gdb.execute("set pagination off")
    gdb.execute("set confirm off")
    gdb.execute("set print thread-events off")
    gdb.execute("set disassemble-next-line off")
    gdb.execute("set debuginfod enabled off")
    gdb.execute(f'file "{elf}"')
    if transport == "remote":
        sysroot = os.environ.get("GDBTRACE_GDB_SYSROOT", "")
        target = os.environ["GDBTRACE_GDB_TARGET"]
        if sysroot:
            gdb.execute(f'set sysroot "{sysroot}"')
        gdb.execute(f"target remote {target}")
        if symbol_mode == "main":
            gdb.execute("tbreak main")
            gdb.execute("continue")
    else:
        if symbol_mode == "main":
            gdb.execute("tbreak main")
            gdb.execute("run")
        else:
            gdb.execute(f"tbreak *{_entry_point()}")
            gdb.execute("run")

    events: list[dict[str, object]] = []
    if symbol_mode == "entry":
        steps = _step_until_exit(max_steps, events)
        if steps >= max_steps:
            raise RuntimeError(f"gdb stepping exceeded limit: {max_steps}")
        output_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
        return

    stack = _relevant_stack()
    if not stack:
        raise RuntimeError("failed to stop in main")

    _emit_call_events(events, stack)

    steps = 0
    while steps < max_steps:
        current_stack = _relevant_stack()
        if not current_stack:
            break

        pc, instruction = _current_instruction()
        events.append(
            {
                "kind": "inst",
                "depth": len(current_stack),
                "function": current_stack[-1],
                "pc": pc,
                "instruction": instruction,
            }
        )
        steps += 1

        try:
            gdb.execute("stepi")
        except gdb.error as exc:
            message = str(exc)
            if "exited" not in message and "Inferior" not in message and "program is not being run" not in message:
                raise
            break

        next_stack = _relevant_stack()
        _emit_stack_transition(events, current_stack, next_stack)
        stack = next_stack

    if steps >= max_steps:
        raise RuntimeError(f"gdb stepping exceeded limit: {max_steps}")

    _emit_stack_transition(events, stack, [])
    output_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
