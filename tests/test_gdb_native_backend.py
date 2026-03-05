from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROGRAMS_DIR = REPO_ROOT / "test_programs"


class NativeGdbBackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")
        self.env["GDBTRACE_CAPTURE_BACKEND"] = "gdb-native"
        self.env["GDBTRACE_GDB_MAX_STEPS"] = "4096"

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

    def compile_program(self, source_name: str) -> Path:
        source_path = PROGRAMS_DIR / source_name
        output_path = self.state_dir / source_name.replace(".c", "")
        result = subprocess.run(
            [
                "aarch64-linux-gnu-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                "-no-pie",
                str(source_path),
                "-o",
                str(output_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return output_path

    def configure(self, elf_path: Path, output_path: Path, mode: str) -> None:
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:1234").returncode, 0)
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", mode).returncode, 0)

    def strip_program(self, elf_path: Path) -> Path:
        stripped_path = elf_path.with_name(f"{elf_path.name}_stripped")
        result = subprocess.run(
            [
                "aarch64-linux-gnu-strip",
                "--strip-all",
                "-o",
                str(stripped_path),
                str(elf_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return stripped_path

    def compile_stripped_program(self, source_name: str) -> Path:
        source_path = PROGRAMS_DIR / source_name
        start_path = PROGRAMS_DIR / "aarch64_start.S"
        output_path = self.state_dir / source_name.replace(".c", "_nosym")
        result = subprocess.run(
            [
                "aarch64-linux-gnu-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                "-nostdlib",
                "-static",
                "-no-pie",
                "-Wl,-e,_start",
                str(start_path),
                str(source_path),
                "-o",
                str(output_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return self.strip_program(output_path)

    def test_gdb_native_backend_captures_basic_aarch64_sample(self) -> None:
        elf_path = self.compile_program("aarch64_sample.c")
        output_path = self.state_dir / "aarch64_sample.log"
        self.configure(elf_path, output_path, "both")

        start = self.run_cli("start")
        self.assertEqual(start.returncode, 0, msg=start.stdout)
        save = self.run_cli("save")
        self.assertEqual(save.returncode, 0, msg=save.stdout)

        content = output_path.read_text(encoding="utf-8")
        self.assertIn("backend=gdb-native", content)
        self.assertIn("\x1b[32mcall main\x1b[0m", content)
        self.assertIn("call func_a", content)
        self.assertIn("call func_b", content)
        self.assertIn("call leaf_add", content)
        self.assertIn(" bl ", content)
        self.assertIn(" ret", content)

        runtime_payload = Path(self.env["GDBTRACE_RUNTIME_FILE"]).read_text(encoding="utf-8")
        self.assertIn('"capture_backend": "gdb-native"', runtime_payload)
        self.run_cli("stop")

    def test_gdb_native_backend_captures_complex_aarch64_sample(self) -> None:
        elf_path = self.compile_program("aarch64_complex.c")
        output_path = self.state_dir / "aarch64_complex.log"
        self.configure(elf_path, output_path, "both")

        start = self.run_cli("start")
        self.assertEqual(start.returncode, 0, msg=start.stdout)
        save = self.run_cli("save")
        self.assertEqual(save.returncode, 0, msg=save.stdout)

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

    def test_gdb_native_backend_rejects_non_aarch64_arch(self) -> None:
        elf_path = self.compile_program("aarch64_sample.c")
        output_path = self.state_dir / "arm32.log"
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:1234").returncode, 0)
        self.assertEqual(self.run_cli("set-arch", "arm32").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)

        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: gdb-native backend currently supports only aarch64", result.stdout)

    def test_gdb_native_backend_captures_inst_trace_for_stripped_elf(self) -> None:
        elf_path = self.compile_stripped_program("aarch64_sample.c")
        output_path = self.state_dir / "aarch64_stripped.log"
        self.configure(elf_path, output_path, "inst")

        start = self.run_cli("start")
        self.assertEqual(start.returncode, 0, msg=start.stdout)
        save = self.run_cli("save")
        self.assertEqual(save.returncode, 0, msg=save.stdout)

        content = output_path.read_text(encoding="utf-8")
        self.assertIn("backend=gdb-native", content)
        self.assertNotIn("call ", content)
        self.assertNotIn("ret ", content)
        instruction_lines = [line for line in content.splitlines() if line.startswith("0x")]
        self.assertGreaterEqual(len(instruction_lines), 5)
        self.run_cli("stop")

    def test_gdb_native_backend_rejects_call_trace_for_stripped_elf(self) -> None:
        elf_path = self.compile_stripped_program("aarch64_sample.c")
        output_path = self.state_dir / "aarch64_stripped_both.log"
        self.configure(elf_path, output_path, "both")

        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "error: ELF without main symbol supports only inst mode in real backends",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
