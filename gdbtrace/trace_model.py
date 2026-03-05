from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


TraceEventKind = Literal["call", "ret", "inst"]


@dataclass(frozen=True)
class TraceEvent:
    kind: TraceEventKind
    depth: int
    function: str
    pc: str = ""
    instruction: str = ""
    registers: dict[str, str] = field(default_factory=dict)


def _sample_registers(arch: str) -> dict[str, str]:
    if arch == "aarch64":
        return {
            "x0": "0x0000000000000005",
            "x1": "0x0000000000000007",
            "x29": "0x0000007ffffff0",
            "x30": "0x0000000000400590",
            "sp": "0x0000007fffffe0",
        }
    if arch in {"arm32", "thumb", "thumb2"}:
        return {
            "r0": "0x00000005",
            "r1": "0x00000007",
            "r11": "0x7fffffe0",
            "lr": "0x00010490",
            "sp": "0x7fffffd0",
        }
    if arch in {"riscv32", "riscv64"}:
        return {
            "a0": "0x00000005" if arch == "riscv32" else "0x0000000000000005",
            "a1": "0x00000007" if arch == "riscv32" else "0x0000000000000007",
            "ra": "0x00010190" if arch == "riscv32" else "0x0000000000010180",
            "sp": "0x7fffffd0" if arch == "riscv32" else "0x0000003ffffff0",
        }
    return {}


def _inst(arch: str, depth: int, function: str, pc: str, instruction: str, include_registers: bool) -> TraceEvent:
    return TraceEvent(
        "inst",
        depth,
        function,
        pc,
        instruction,
        registers=_sample_registers(arch) if include_registers else {},
    )


def sample_trace_events(arch: str, include_registers: bool = False) -> list[TraceEvent]:
    if arch == "aarch64":
        return [
            TraceEvent("call", 0, "main"),
            _inst(arch, 1, "main", "0x400580", "stp x29, x30, [sp, #-16]!", include_registers),
            _inst(arch, 1, "main", "0x400584", "mov x29, sp", include_registers),
            _inst(arch, 1, "main", "0x400588", "bl func_a", include_registers),
            TraceEvent("call", 1, "func_a"),
            _inst(arch, 2, "func_a", "0x4005a8", "sub sp, sp, #0x10", include_registers),
            _inst(arch, 2, "func_a", "0x4005ac", "bl func_b", include_registers),
            TraceEvent("call", 2, "func_b"),
            _inst(arch, 3, "func_b", "0x4005bc", "mov x1, x0", include_registers),
            _inst(arch, 3, "func_b", "0x4005c0", "ret", include_registers),
            TraceEvent("ret", 2, "func_b"),
            _inst(arch, 2, "func_a", "0x4005b4", "ret", include_registers),
            TraceEvent("ret", 1, "func_a"),
            TraceEvent("ret", 0, "main"),
        ]

    if arch in {"arm32", "thumb", "thumb2"}:
        entry_pc = {
            "arm32": "0x00010480",
            "thumb": "0x00010481",
            "thumb2": "0x00020481",
        }[arch]
        first_inst = {
            "arm32": "push {r11, lr}",
            "thumb": "push {r7, lr}",
            "thumb2": "push.w {r4, r7, lr}",
        }[arch]
        return [
            TraceEvent("call", 0, "main"),
            _inst(arch, 1, "main", entry_pc, first_inst, include_registers),
            _inst(arch, 1, "main", "0x00010484", "bl func_a", include_registers),
            TraceEvent("call", 1, "func_a"),
            _inst(arch, 2, "func_a", "0x00010498", "mov r0, r1", include_registers),
            _inst(arch, 2, "func_a", "0x0001049c", "bx lr", include_registers),
            TraceEvent("ret", 1, "func_a"),
            TraceEvent("ret", 0, "main"),
        ]

    if arch in {"riscv32", "riscv64"}:
        entry_pc = {
            "riscv32": "0x0001018c",
            "riscv64": "0x000000000001017c",
        }[arch]
        second_pc = {
            "riscv32": "0x00010190",
            "riscv64": "0x0000000000010180",
        }[arch]
        first_inst = {
            "riscv32": "addi sp,sp,-16",
            "riscv64": "addi sp,sp,-32",
        }[arch]
        return [
            TraceEvent("call", 0, "main"),
            _inst(arch, 1, "main", entry_pc, first_inst, include_registers),
            _inst(arch, 1, "main", second_pc, "jal ra,func_a", include_registers),
            TraceEvent("call", 1, "func_a"),
            _inst(arch, 2, "func_a", "0x000101b0", "mv a0,a1", include_registers),
            _inst(arch, 2, "func_a", "0x000101b4", "ret", include_registers),
            TraceEvent("ret", 1, "func_a"),
            TraceEvent("ret", 0, "main"),
        ]

    return [
        TraceEvent("call", 0, "main"),
        _inst(arch, 1, "main", "0x0", "nop", include_registers),
        TraceEvent("ret", 0, "main"),
    ]
