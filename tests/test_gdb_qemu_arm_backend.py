from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROGRAMS_DIR = REPO_ROOT / "test_programs"
ARCH_FLAGS = {
    "arm32": ["-marm"],
    "thumb": ["-mthumb"],
    "thumb2": ["-mthumb", "-march=armv7-a", "-mfpu=vfpv3-d16"],
}
PORTS = {
    "arm32": "127.0.0.1:24001",
    "thumb": "127.0.0.1:24002",
    "thumb2": "127.0.0.1:24003",
}


class QemuArmBackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")
        self.env["GDBTRACE_CAPTURE_BACKEND"] = "gdb-qemu-arm"
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
        source_path = PROGRAMS_DIR / source_name
        output_path = self.state_dir / f"{source_name.replace('.c', '')}_{arch}"
        result = subprocess.run(
            [
                "arm-linux-gnueabihf-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                *ARCH_FLAGS[arch],
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

    def configure(self, arch: str, elf_path: Path, output_path: Path, mode: str, registers: str = "off") -> None:
        self.assertEqual(self.run_cli("set-target", PORTS[arch]).returncode, 0)
        self.assertEqual(self.run_cli("set-arch", arch).returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", mode).returncode, 0)
        self.assertEqual(self.run_cli("set-registers", registers).returncode, 0)

    def strip_program(self, elf_path: Path) -> Path:
        stripped_path = elf_path.with_name(f"{elf_path.name}_stripped")
        result = subprocess.run(
            [
                "arm-linux-gnueabihf-strip",
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

    def compile_stripped_program(self, source_name: str, arch: str) -> Path:
        source_path = PROGRAMS_DIR / source_name
        start_path = PROGRAMS_DIR / "arm32_start.S"
        output_path = self.state_dir / f"{source_name.replace('.c', '')}_{arch}_nosym"
        result = subprocess.run(
            [
                "arm-linux-gnueabihf-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                "-nostdlib",
                "-static",
                "-Wl,-e,_start",
                *ARCH_FLAGS[arch],
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

    def test_qemu_backend_captures_basic_samples_for_all_arm_variants(self) -> None:
        for arch, source_name in {
            "arm32": "arm32_sample.c",
            "thumb": "thumb_sample.c",
            "thumb2": "thumb2_sample.c",
        }.items():
            with self.subTest(arch=arch):
                elf_path = self.compile_program(source_name, arch)
                output_path = self.state_dir / f"{arch}_basic.log"
                self.configure(arch, elf_path, output_path, "both")

                start = self.run_cli("start")
                self.assertEqual(start.returncode, 0, msg=start.stdout)
                save = self.run_cli("save")
                self.assertEqual(save.returncode, 0, msg=save.stdout)

                content = output_path.read_text(encoding="utf-8")
                self.assertIn("backend=gdb-qemu-arm", content)
                self.assertIn("\x1b[32mcall main\x1b[0m", content)
                self.assertIn("call func_a", content)
                self.assertIn("call func_b", content)
                self.assertIn("call leaf_add", content)
                self.assertIn(" bl ", content)
                self.assertIn(" bx lr", content)
                self.run_cli("stop")

    def test_qemu_backend_captures_complex_samples_for_all_arm_variants(self) -> None:
        for arch, source_name in {
            "arm32": "arm32_complex.c",
            "thumb": "thumb_complex.c",
            "thumb2": "thumb2_complex.c",
        }.items():
            with self.subTest(arch=arch):
                elf_path = self.compile_program(source_name, arch)
                output_path = self.state_dir / f"{arch}_complex.log"
                self.configure(arch, elf_path, output_path, "both")

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

    def test_qemu_backend_rejects_aarch64(self) -> None:
        elf_path = self.state_dir / "dummy"
        elf_path.write_text("", encoding="utf-8")
        output_path = self.state_dir / "aarch64.log"
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:24010").returncode, 0)
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)

        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: gdb-qemu-arm backend supports only arm32, thumb, thumb2", result.stdout)

    def test_qemu_backend_captures_inst_trace_for_stripped_arm32_elf(self) -> None:
        elf_path = self.compile_stripped_program("arm32_sample.c", "arm32")
        output_path = self.state_dir / "arm32_stripped.log"
        self.configure("arm32", elf_path, output_path, "inst")

        start = self.run_cli("start")
        self.assertEqual(start.returncode, 0, msg=start.stdout)
        save = self.run_cli("save")
        self.assertEqual(save.returncode, 0, msg=save.stdout)

        content = output_path.read_text(encoding="utf-8")
        self.assertIn("backend=gdb-qemu-arm", content)
        self.assertNotIn("call ", content)
        self.assertNotIn("ret ", content)
        instruction_lines = [line for line in content.splitlines() if line.startswith("0x")]
        self.assertGreaterEqual(len(instruction_lines), 5)
        self.run_cli("stop")

    def test_qemu_backend_rejects_call_trace_for_stripped_arm32_elf(self) -> None:
        elf_path = self.compile_stripped_program("arm32_sample.c", "arm32")
        output_path = self.state_dir / "arm32_stripped_both.log"
        self.configure("arm32", elf_path, output_path, "both")

        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "error: ELF without main symbol supports only inst mode in real backends",
            result.stdout,
        )

    def test_qemu_backend_can_emit_registers_for_arm32(self) -> None:
        elf_path = self.compile_program("arm32_sample.c", "arm32")
        output_path = self.state_dir / "arm32_registers.log"
        self.configure("arm32", elf_path, output_path, "both", registers="on")

        start = self.run_cli("start")
        self.assertEqual(start.returncode, 0, msg=start.stdout)
        save = self.run_cli("save")
        self.assertEqual(save.returncode, 0, msg=save.stdout)

        content = output_path.read_text(encoding="utf-8")
        self.assertIn("[registers] on", content)
        self.assertIn("regs: r0=", content)
        self.assertIn("lr=", content)
        self.run_cli("stop")


if __name__ == "__main__":
    unittest.main()
