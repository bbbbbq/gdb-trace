from __future__ import annotations

import importlib
import sys
import types
import unittest


class _FakeGdbError(Exception):
    pass


class GdbAgentTest(unittest.TestCase):
    def load_module(self, fake_gdb: types.SimpleNamespace):
        original_gdb = sys.modules.get("gdb")
        original_agent = sys.modules.get("gdbtrace.gdb_agent")
        sys.modules["gdb"] = fake_gdb
        sys.modules.pop("gdbtrace.gdb_agent", None)
        module = importlib.import_module("gdbtrace.gdb_agent")

        def cleanup() -> None:
            sys.modules.pop("gdbtrace.gdb_agent", None)
            if original_agent is not None:
                sys.modules["gdbtrace.gdb_agent"] = original_agent
            if original_gdb is not None:
                sys.modules["gdb"] = original_gdb
            else:
                sys.modules.pop("gdb", None)

        self.addCleanup(cleanup)
        return module

    def test_step_and_capture_registers_reads_after_stepi(self) -> None:
        call_order: list[str] = []
        fake_gdb = types.SimpleNamespace(error=_FakeGdbError)

        def execute(command: str, to_string: bool = False) -> str:
            del to_string
            call_order.append(command)
            return ""

        fake_gdb.execute = execute
        module = self.load_module(fake_gdb)

        def current_registers(_: str, enabled: bool) -> dict[str, str]:
            self.assertTrue(enabled)
            call_order.append("registers")
            return {"x29": "0x0000000000000001"}

        module._current_registers = current_registers

        registers, exited = module._step_and_capture_registers("aarch64", True)

        self.assertFalse(exited)
        self.assertEqual({"x29": "0x0000000000000001"}, registers)
        self.assertEqual(["stepi", "registers"], call_order)

    def test_step_until_exit_records_post_step_registers(self) -> None:
        call_order: list[str] = []
        fake_gdb = types.SimpleNamespace(error=_FakeGdbError)

        def execute(command: str, to_string: bool = False) -> str:
            del to_string
            call_order.append(command)
            return ""

        fake_gdb.execute = execute
        module = self.load_module(fake_gdb)

        instruction_calls = 0

        def current_instruction() -> tuple[str, str]:
            nonlocal instruction_calls
            instruction_calls += 1
            if instruction_calls == 1:
                return "0x400584", "mov x29, sp"
            raise fake_gdb.error("No registers")

        def current_registers(_: str, enabled: bool) -> dict[str, str]:
            self.assertTrue(enabled)
            call_order.append("registers")
            return {"x29": "0x0000007fffffe0", "sp": "0x0000007fffffe0"}

        module._current_instruction = current_instruction
        module._current_registers = current_registers

        events: list[dict[str, object]] = []
        steps = module._step_until_exit(4, events, "aarch64", True)

        self.assertEqual(1, steps)
        self.assertEqual(["stepi", "registers"], call_order)
        self.assertEqual(
            [
                {
                    "kind": "inst",
                    "depth": 0,
                    "function": "",
                    "pc": "0x400584",
                    "instruction": "mov x29, sp",
                    "registers": {"x29": "0x0000007fffffe0", "sp": "0x0000007fffffe0"},
                }
            ],
            events,
        )


if __name__ == "__main__":
    unittest.main()
