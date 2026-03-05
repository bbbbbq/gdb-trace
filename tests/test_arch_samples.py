from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ArchitectureSampleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def output_path_for(self, arch: str, mode: str) -> Path:
        return self.state_dir / f"{arch}_{mode}.log"

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "gdbtrace", *args],
            cwd=REPO_ROOT,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def configure(self, arch: str, mode: str, output_path: Path) -> None:
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:1234").returncode, 0)
        self.assertEqual(self.run_cli("set-arch", arch).returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", mode).returncode, 0)

    def test_inst_mode_outputs_expected_instruction_samples_for_each_arch(self) -> None:
        expectations = {
            "arm32": "0x00010480 push {r11, lr}",
            "thumb": "0x00010481 push {r7, lr}",
            "thumb2": "0x00020481 push.w {r4, r7, lr}",
            "riscv32": "0x0001018c addi sp,sp,-16",
            "riscv64": "0x000000000001017c addi sp,sp,-32",
        }
        for arch, first_line in expectations.items():
            with self.subTest(arch=arch):
                output_path = self.output_path_for(arch, "inst")
                self.configure(arch, "inst", output_path)
                self.assertEqual(self.run_cli("start").returncode, 0)
                self.assertEqual(self.run_cli("save").returncode, 0)
                content = output_path.read_text(encoding="utf-8")
                self.assertIn(first_line, content)
                if arch in {"arm32", "thumb", "thumb2"}:
                    self.assertIn("0x00010484 bl func_a", content)
                else:
                    self.assertIn("jal ra,func_a", content)
                self.assertNotIn("call main", content)
                self.run_cli("stop")

    def test_call_mode_outputs_nested_calls_for_each_arch(self) -> None:
        for arch in ("arm32", "thumb", "thumb2", "riscv32", "riscv64"):
            with self.subTest(arch=arch):
                output_path = self.output_path_for(arch, "call")
                self.configure(arch, "call", output_path)
                self.assertEqual(self.run_cli("start").returncode, 0)
                self.assertEqual(self.run_cli("save").returncode, 0)
                content = output_path.read_text(encoding="utf-8")
                self.assertIn("\x1b[32mcall main\x1b[0m", content)
                self.assertIn("    \x1b[32mcall func_a\x1b[0m", content)
                self.assertIn("    \x1b[31mret func_a\x1b[0m", content)
                self.assertIn("\x1b[31mret main\x1b[0m", content)
                self.run_cli("stop")


if __name__ == "__main__":
    unittest.main()
