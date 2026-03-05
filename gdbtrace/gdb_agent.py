from __future__ import annotations

import json
import os
import re
from pathlib import Path

import gdb


INSTRUCTION_RE = re.compile(r"(?:=>\s*)?(0x[0-9a-fA-F]+)(?:\s+<([^>]+)>)?:\s*(.*)")
ENTRY_RE = re.compile(r"Entry point:\s*(0x[0-9a-fA-F]+)")
BACKTRACE_RE = re.compile(r"^#\d+\s+(?:0x[0-9a-fA-Fx]+\s+in\s+)?([^\s(]+)")
CALL_RE = re.compile(r"^([a-z.]+)\s+([^\s]+)(?:\s+<([^>]+)>)?")


def _normalized_frame_name(name: str) -> str:
    if name.endswith("@plt"):
        return name[:-4]
    return name


def _instruction_details() -> tuple[str, str, str]:
    line = gdb.execute("x/i $pc", to_string=True).strip()
    match = INSTRUCTION_RE.search(line)
    if not match:
        raise RuntimeError(f"failed to parse instruction line: {line}")
    pc = match.group(1).lower()
    symbol = ""
    if match.group(2):
        symbol = _normalized_frame_name(match.group(2).split("+", 1)[0])
    instruction = " ".join(match.group(3).replace("\t", " ").split())
    return pc, symbol, instruction


def _current_symbol_name() -> str:
    try:
        info = gdb.execute("info symbol $pc", to_string=True).strip()
    except gdb.error:
        return ""
    if not info or info.startswith("No symbol matches"):
        return ""
    symbol = info.split(" + ", 1)[0].split(" in section ", 1)[0].strip()
    if not symbol or symbol == "??":
        return ""
    return _normalized_frame_name(symbol)


def _relevant_stack() -> list[str]:
    names: list[str] = []
    found_main = False
    backtrace = gdb.execute("bt", to_string=True)
    for line in backtrace.splitlines():
        match = BACKTRACE_RE.match(line.strip())
        if not match:
            continue
        normalized_name = _normalized_frame_name(match.group(1))
        if normalized_name == "??":
            continue
        if not names or names[-1] != normalized_name:
            names.append(normalized_name)
        if normalized_name == "main":
            found_main = True
            break
    if not found_main:
        return []
    _, instruction_symbol, _ = _instruction_details()
    current_symbol = instruction_symbol or _current_symbol_name()
    if current_symbol and (not names or names[0] != current_symbol):
        names.insert(0, current_symbol)
    return list(reversed(names))


def _current_instruction() -> tuple[str, str]:
    pc, _, instruction = _instruction_details()
    return pc, instruction


def _instruction_mnemonic(instruction: str) -> str:
    return instruction.split(maxsplit=1)[0].lower() if instruction else ""


def _is_return_instruction(instruction: str) -> bool:
    mnemonic = _instruction_mnemonic(instruction)
    if mnemonic == "ret":
        return True
    return instruction.startswith("bx lr") or instruction.startswith("bx\txlr") or instruction == "jr ra"


def _inferred_call_target(instruction: str) -> str:
    match = CALL_RE.match(instruction)
    if not match:
        return ""
    mnemonic = match.group(1).lower()
    if mnemonic not in {"bl", "blx", "blr", "jal", "jalr", "call"}:
        return ""
    if match.group(3):
        return _normalized_frame_name(match.group(3).split("+", 1)[0])
    target = match.group(2)
    if target.startswith("0x"):
        return f"sub_{target[2:].lower()}"
    return ""


def _next_stack(
    current_stack: list[str],
    observed_stack: list[str],
    instruction: str,
) -> list[str]:
    next_stack = observed_stack or []
    if len(next_stack) < len(current_stack) and not _is_return_instruction(instruction):
        next_stack = list(current_stack)

    inferred_target = _inferred_call_target(instruction)
    if inferred_target and len(next_stack) <= len(current_stack):
        if not current_stack or current_stack[-1] != inferred_target:
            next_stack = list(current_stack) + [inferred_target]

    return next_stack


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
        current_stack = list(stack)
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

        observed_stack = _relevant_stack()
        next_stack = _next_stack(current_stack, observed_stack, instruction)
        _emit_stack_transition(events, current_stack, next_stack)
        stack = next_stack

    if steps >= max_steps:
        raise RuntimeError(f"gdb stepping exceeded limit: {max_steps}")

    _emit_stack_transition(events, stack, [])
    output_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
