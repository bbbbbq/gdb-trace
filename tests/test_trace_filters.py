from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TraceFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.output_path = self.state_dir / "trace.log"
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

    def configure(self, mode: str = "both", registers: str = "off") -> None:
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:1234").returncode, 0)
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", mode).returncode, 0)
        self.assertEqual(self.run_cli("set-registers", registers).returncode, 0)

    def test_filter_func_keeps_matching_subtree(self) -> None:
        self.configure("both")
        self.assertEqual(self.run_cli("start", "--filter-func", "func_b").returncode, 0)
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("\x1b[32mcall func_b\x1b[0m", content)
        self.assertIn("    0x4005bc mov x1, x0", content)
        self.assertIn("\x1b[31mret func_b\x1b[0m", content)
        self.assertNotIn("call main", content)
        self.assertNotIn("call func_a", content)

    def test_filter_func_preserves_registers_after_rebase(self) -> None:
        self.configure("both", registers="on")
        self.assertEqual(self.run_cli("start", "--filter-func", "func_b").returncode, 0)
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("[registers] on", content)
        self.assertIn("\x1b[32mcall func_b\x1b[0m", content)
        self.assertIn("    0x4005bc mov x1, x0", content)
        self.assertIn("        regs: x0=", content)
        self.assertIn("x29=", content)

    def test_filter_range_keeps_matching_instruction_window(self) -> None:
        self.configure("inst")
        self.assertEqual(self.run_cli("start", "--filter-range", "0x4005a8:0x4005c0").returncode, 0)
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("0x4005a8 sub sp, sp, #0x10", content)
        self.assertIn("0x4005ac bl func_b", content)
        self.assertIn("0x4005bc mov x1, x0", content)
        self.assertIn("0x4005c0 ret", content)
        self.assertNotIn("0x400580 stp x29, x30, [sp, #-16]!", content)

    def test_start_stop_markers_restrict_event_window(self) -> None:
        self.configure("both")
        self.assertEqual(self.run_cli("start", "--start", "func_a", "--stop", "func_b").returncode, 0)
        self.assertEqual(self.run_cli("save").returncode, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("\x1b[32mcall func_a\x1b[0m", content)
        self.assertIn("\x1b[32mcall func_b\x1b[0m", content)
        self.assertNotIn("call main", content)
        self.assertNotIn("\x1b[31mret func_b\x1b[0m", content)

    def test_filter_errors_are_reported(self) -> None:
        self.configure("inst")
        result = self.run_cli("start", "--filter-func", "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: function filter matched no events: missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
