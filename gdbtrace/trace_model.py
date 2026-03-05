from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TraceEventKind = Literal["call", "ret", "inst"]


@dataclass(frozen=True)
class TraceEvent:
    kind: TraceEventKind
    depth: int
    function: str
    pc: str = ""
    instruction: str = ""


def sample_trace_events(arch: str) -> list[TraceEvent]:
    if arch == "aarch64":
        return [
            TraceEvent("call", 0, "main"),
            TraceEvent("inst", 1, "main", "0x400580", "stp x29, x30, [sp, #-16]!"),
            TraceEvent("inst", 1, "main", "0x400584", "mov x29, sp"),
            TraceEvent("inst", 1, "main", "0x400588", "bl func_a"),
            TraceEvent("call", 1, "func_a"),
            TraceEvent("inst", 2, "func_a", "0x4005a8", "sub sp, sp, #0x10"),
            TraceEvent("inst", 2, "func_a", "0x4005ac", "bl func_b"),
            TraceEvent("call", 2, "func_b"),
            TraceEvent("inst", 3, "func_b", "0x4005bc", "mov x1, x0"),
            TraceEvent("inst", 3, "func_b", "0x4005c0", "ret"),
            TraceEvent("ret", 2, "func_b"),
            TraceEvent("inst", 2, "func_a", "0x4005b4", "ret"),
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
            TraceEvent("inst", 1, "main", entry_pc, first_inst),
            TraceEvent("inst", 1, "main", "0x00010484", "bl func_a"),
            TraceEvent("call", 1, "func_a"),
            TraceEvent("inst", 2, "func_a", "0x00010498", "mov r0, r1"),
            TraceEvent("inst", 2, "func_a", "0x0001049c", "bx lr"),
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
            TraceEvent("inst", 1, "main", entry_pc, first_inst),
            TraceEvent("inst", 1, "main", second_pc, "jal ra,func_a"),
            TraceEvent("call", 1, "func_a"),
            TraceEvent("inst", 2, "func_a", "0x000101b0", "mv a0,a1"),
            TraceEvent("inst", 2, "func_a", "0x000101b4", "ret"),
            TraceEvent("ret", 1, "func_a"),
            TraceEvent("ret", 0, "main"),
        ]

    return [
        TraceEvent("call", 0, "main"),
        TraceEvent("inst", 1, "main", "0x0", "nop"),
        TraceEvent("ret", 0, "main"),
    ]
