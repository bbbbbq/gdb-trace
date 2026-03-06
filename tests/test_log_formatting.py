from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class LogFormattingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.output_path = self.state_dir / "trace.log"
        self.call_output_path = self.state_dir / "trace.call.log"
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "gdbtrace", *args],
            cwd=REPO_ROOT,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def configure(self, mode: str, registers: str = "off") -> None:
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:1234").returncode, 0)
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", mode).returncode, 0)
        self.assertEqual(self.run_cli("set-registers", registers).returncode, 0)
        self.assertEqual(self.run_cli("start").returncode, 0)

    def test_inst_mode_writes_pc_and_instruction_only(self) -> None:
        self.configure("inst")
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("0x400580 stp x29, x30, [sp, #-16]!", content)
        self.assertNotIn("call main", content)
        self.assertNotIn("opcode=", content)
        self.assertNotIn("disasm=", content)

    def test_call_mode_writes_nested_call_and_ret_lines(self) -> None:
        self.configure("call")
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("call main", content)
        self.assertIn("    \x1b[32mcall func_a\x1b[0m", content)
        self.assertIn("        \x1b[32mcall func_b\x1b[0m", content)
        self.assertIn("        \x1b[31mret func_b\x1b[0m", content)
        self.assertNotIn("0x400580 stp x29, x30, [sp, #-16]!", content)

    def test_both_mode_combines_nested_calls_and_instructions(self) -> None:
        self.configure("both")
        self.assertEqual(self.run_cli("stop").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        call_content = self.call_output_path.read_text(encoding="utf-8")
        self.assertIn("\x1b[32mcall main\x1b[0m", content)
        self.assertIn("    0x400580 stp x29, x30, [sp, #-16]!", content)
        self.assertIn("    \x1b[32mcall func_a\x1b[0m", content)
        self.assertIn("        0x4005a8 sub sp, sp, #0x10", content)
        self.assertIn("        \x1b[32mcall func_b\x1b[0m", content)
        self.assertIn("        \x1b[31mret func_b\x1b[0m", content)
        self.assertIn("trace_mode=call", call_content)
        self.assertIn("\x1b[32mcall main\x1b[0m", call_content)
        self.assertIn("    \x1b[32mcall func_a\x1b[0m", call_content)
        self.assertNotIn("0x400580 stp x29, x30, [sp, #-16]!", call_content)

    def test_inst_mode_can_include_general_registers_when_enabled(self) -> None:
        self.configure("inst", registers="on")
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("[registers] on", content)
        self.assertIn("    regs: x0=", content)
        self.assertIn("sp=", content)

    def test_both_mode_can_include_general_registers_when_enabled(self) -> None:
        self.configure("both", registers="on")
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("        regs: x0=", content)
        self.assertIn("x29=", content)

    def test_call_mode_does_not_capture_or_render_registers(self) -> None:
        self.configure("call", registers="on")
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertNotIn("[registers] on", content)
        self.assertNotIn("regs:", content)

        runtime = json.loads(Path(self.env["GDBTRACE_RUNTIME_FILE"]).read_text(encoding="utf-8"))
        inst_events = [event for event in runtime["events"] if event["kind"] == "inst"]
        self.assertTrue(inst_events)
        self.assertTrue(all(event["registers"] == {} for event in inst_events))


if __name__ == "__main__":
    unittest.main()
