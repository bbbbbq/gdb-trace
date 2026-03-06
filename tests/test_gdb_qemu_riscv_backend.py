from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROGRAMS_DIR = REPO_ROOT / "test_programs"
ARCH_FLAGS = {
    "riscv32": ["-march=rv32imac", "-mabi=ilp32"],
    "riscv64": ["-march=rv64gc", "-mabi=lp64d"],
}
PORTS = {
    "riscv32": "127.0.0.1:25031",
    "riscv64": "127.0.0.1:25064",
}


class QemuRiscvBackendTest(unittest.TestCase):
    @staticmethod
    def _normalized_lines(content: str) -> list[str]:
        return [re.sub(r"\x1b\[[0-9;]*m", "", line) for line in content.splitlines()]

    def assert_call_subsequence(self, content: str, expected: list[str]) -> None:
        call_lines = [line.strip() for line in self._normalized_lines(content) if "call " in line]
        cursor = 0
        for expected_line in expected:
            while cursor < len(call_lines) and call_lines[cursor] != expected_line:
                cursor += 1
            self.assertLess(cursor, len(call_lines), msg=f"missing call subsequence item: {expected_line}\n{call_lines}")
            cursor += 1

    def count_calls(self, content: str, function: str) -> int:
        return sum(1 for line in self._normalized_lines(content) if line.strip() == f"call {function}")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")
        self.env["GDBTRACE_CAPTURE_BACKEND"] = "gdb-qemu-riscv"
        self.env["GDBTRACE_GDB_MAX_STEPS"] = "8192"

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

    def compile_program(self, source_name: str, arch: str) -> Path:
        output_path = self.state_dir / f"{source_name.replace('.c', '')}_{arch}"
        result = subprocess.run(
            [
                "riscv64-linux-gnu-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                "-nostdlib",
                "-static",
                "-Wl,-e,_start",
                *ARCH_FLAGS[arch],
                str(PROGRAMS_DIR / "riscv_start.S"),
                str(PROGRAMS_DIR / source_name),
                "-o",
                str(output_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return output_path

    def configure(self, arch: str, elf_path: Path, output_path: Path, mode: str) -> None:
        self.env["GDBTRACE_GDB_TARGET"] = PORTS[arch]
        self.assertEqual(self.run_cli("set-arch", arch).returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", mode).returncode, 0)

    def test_qemu_backend_captures_basic_samples_for_riscv(self) -> None:
        for arch, source_name in {
            "riscv32": "riscv32_sample.c",
            "riscv64": "riscv64_sample.c",
        }.items():
            with self.subTest(arch=arch):
                elf_path = self.compile_program(source_name, arch)
                output_path = self.state_dir / f"{arch}_basic.log"
                self.configure(arch, elf_path, output_path, "both")

                start = self.run_cli("start")
                self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
                save = self.run_cli("save")
                self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

                content = output_path.read_text(encoding="utf-8")
                self.assertIn("backend=gdb-qemu-riscv", content)
                self.assertIn("\x1b[32mcall main\x1b[0m", content)
                self.assertIn("call func_a", content)
                self.assertIn("call func_b", content)
                self.assertIn("call leaf_add", content)
                self.assertRegex(content, r"0x[0-9a-f]+ ")
                self.assertIn("ret", content)
                self.run_cli("stop")

    def test_qemu_backend_captures_complex_samples_for_riscv(self) -> None:
        for arch, source_name in {
            "riscv32": "riscv32_complex.c",
            "riscv64": "riscv64_complex.c",
        }.items():
            with self.subTest(arch=arch):
                elf_path = self.compile_program(source_name, arch)
                output_path = self.state_dir / f"{arch}_complex.log"
                self.configure(arch, elf_path, output_path, "both")

                start = self.run_cli("start")
                self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
                save = self.run_cli("save")
                self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

                content = output_path.read_text(encoding="utf-8")
                self.assertIn("call parse_and_route", content)
                self.assertIn("call dispatch", content)
                self.assertTrue("call worker_primary" in content or "call worker_fallback" in content)
                self.assertIn("call helper_mix", content)
                self.assertIn("call helper_recursive", content)
                instruction_lines = [
                    line for line in content.splitlines() if line.startswith("    0x") or line.startswith("        0x")
                ]
                self.assertGreaterEqual(len(instruction_lines), 25)
                self.run_cli("stop")

    def test_qemu_backend_preserves_dual_dispatch_flow_for_riscv(self) -> None:
        expectations = {
            "riscv32": "riscv32_complex.c",
            "riscv64": "riscv64_complex.c",
        }
        for arch, source_name in expectations.items():
            with self.subTest(arch=arch):
                elf_path = self.compile_program(source_name, arch)
                output_path = self.state_dir / f"{arch}_complex_flow.log"
                self.configure(arch, elf_path, output_path, "both")

                start = self.run_cli("start")
                self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
                save = self.run_cli("save")
                self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

                try:
                    content = output_path.read_text(encoding="utf-8")
                    self.assert_call_subsequence(
                        content,
                        [
                            "call main",
                            "call parse_and_route",
                            "call dispatch",
                            "call worker_primary",
                            "call helper_mix",
                            "call helper_recursive",
                            "call dispatch",
                            "call worker_fallback",
                        ],
                    )
                    self.assertGreaterEqual(self.count_calls(content, "dispatch"), 2)
                    self.assertGreaterEqual(self.count_calls(content, "helper_mix"), 2)
                    self.assertGreaterEqual(self.count_calls(content, "helper_recursive"), 2)
                finally:
                    self.run_cli("stop")

    def test_qemu_backend_rejects_arm_arch(self) -> None:
        elf_path = self.state_dir / "dummy"
        elf_path.write_text("", encoding="utf-8")
        output_path = self.state_dir / "arm32.log"
        self.env["GDBTRACE_GDB_TARGET"] = "127.0.0.1:25099"
        self.assertEqual(self.run_cli("set-arch", "arm32").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)

        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: gdb-qemu-riscv backend supports only riscv32, riscv64", result.stdout)


if __name__ == "__main__":
    unittest.main()
