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
ARM_ARCH_FLAGS = {
    "arm32": ["-marm"],
    "thumb": ["-mthumb"],
    "thumb2": ["-mthumb", "-march=armv7-a", "-mfpu=vfpv3-d16"],
}
ARM_PORTS = {
    "arm32": "127.0.0.1:24101",
    "thumb": "127.0.0.1:24102",
    "thumb2": "127.0.0.1:24103",
}
RISCV64_PORT = "127.0.0.1:26164"


class QemuUserUserspaceAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")
        self.env["GDBTRACE_GDB_MAX_STEPS"] = "20000"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str, env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(self.env)
        if env_override:
            env.update(env_override)
        return subprocess.run(
            [sys.executable, "-m", "gdbtrace", *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def compile_arm_userspace(self, arch: str, source_name: str = "userspace_qemu_app.c") -> tuple[Path, str]:
        stem = Path(source_name).stem
        output_path = self.state_dir / f"{stem}_{arch}"
        result = subprocess.run(
            [
                "arm-linux-gnueabihf-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                "-Wl,-z,now",
                *ARM_ARCH_FLAGS[arch],
                str(PROGRAMS_DIR / source_name),
                "-o",
                str(output_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        file_result = subprocess.run(["file", str(output_path)], text=True, capture_output=True)
        self.assertEqual(file_result.returncode, 0, msg=file_result.stderr)
        self.assertIn("dynamically linked", file_result.stdout)
        return output_path, file_result.stdout

    def compile_riscv64_userspace(self, source_name: str = "userspace_qemu_app.c") -> tuple[Path, str]:
        stem = Path(source_name).stem
        output_path = self.state_dir / f"{stem}_riscv64"
        result = subprocess.run(
            [
                "riscv64-linux-gnu-gcc",
                "-g",
                "-O0",
                "-fno-omit-frame-pointer",
                "-Wl,-z,now",
                "-march=rv64gc",
                "-mabi=lp64d",
                str(PROGRAMS_DIR / source_name),
                "-o",
                str(output_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        file_result = subprocess.run(["file", str(output_path)], text=True, capture_output=True)
        self.assertEqual(file_result.returncode, 0, msg=file_result.stderr)
        self.assertIn("dynamically linked", file_result.stdout)
        return output_path, file_result.stdout

    def configure(self, target: str, arch: str, elf_path: Path, output_path: Path, env_override: dict[str, str]) -> str:
        env_override["GDBTRACE_GDB_TARGET"] = target
        self.assertEqual(self.run_cli("set-arch", arch, env_override=env_override).returncode, 0)
        self.assertEqual(self.run_cli("set-elf", str(elf_path), env_override=env_override).returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(output_path), env_override=env_override).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both", env_override=env_override).returncode, 0)
        return output_path.read_text(encoding="utf-8") if output_path.exists() else ""

    def assert_userspace_trace(self, content: str, backend_name: str) -> None:
        self.assertIn(f"backend={backend_name}", content)
        self.assertIn("call process_payload", content)
        self.assertIn("call accumulate_scores", content)
        self.assertIn("call normalize_token", content)
        self.assertRegex(content, r"call .*strlen")
        self.assertTrue(
            any(marker in content for marker in ("call parse_weight", "call compose_record", "call strlen")),
            msg=content,
        )
        self.assertTrue(
            any(marker in content for marker in ("strlen", "snprintf", "strtol", "memcpy", "strstr")),
            msg=content,
        )
        instruction_lines = [line for line in content.splitlines() if re.match(r"^\s*0x[0-9a-f]+ ", line)]
        self.assertGreaterEqual(len(instruction_lines), 25)

    def assert_printf_trace(self, content: str, backend_name: str) -> None:
        self.assertIn(f"backend={backend_name}", content)
        self.assertIn("call emit_summary", content)
        self.assertIn("call printf", content)
        self.assertNotIn("call printf@plt", content)
        instruction_lines = [line for line in content.splitlines() if re.match(r"^\s*0x[0-9a-f]+ ", line)]
        self.assertGreaterEqual(len(instruction_lines), 12)

    def test_qemu_user_arm_userspace_programs(self) -> None:
        env_override = {
            "GDBTRACE_CAPTURE_BACKEND": "gdb-qemu-arm",
            "GDBTRACE_GDB_MAX_STEPS": "20000",
            "LD_BIND_NOW": "1",
        }
        for arch in ("arm32", "thumb", "thumb2"):
            with self.subTest(arch=arch):
                elf_path, _ = self.compile_arm_userspace(arch)
                output_path = self.state_dir / f"{arch}_userspace.log"
                self.configure(ARM_PORTS[arch], arch, elf_path, output_path, env_override)

                try:
                    start = self.run_cli("start", env_override=env_override)
                    self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
                    save = self.run_cli("save", env_override=env_override)
                    self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

                    content = output_path.read_text(encoding="utf-8")
                    self.assert_userspace_trace(content, "gdb-qemu-arm")
                finally:
                    self.run_cli("stop", env_override=env_override)

    def test_qemu_user_riscv64_userspace_program(self) -> None:
        env_override = {
            "GDBTRACE_CAPTURE_BACKEND": "gdb-qemu-riscv",
            "GDBTRACE_GDB_MAX_STEPS": "20000",
            "GDBTRACE_GDB_QEMU_RISCV_SYSROOT": "/usr/riscv64-linux-gnu",
            "LD_BIND_NOW": "1",
        }
        elf_path, _ = self.compile_riscv64_userspace()
        output_path = self.state_dir / "riscv64_userspace.log"
        self.configure(RISCV64_PORT, "riscv64", elf_path, output_path, env_override)

        try:
            start = self.run_cli("start", env_override=env_override)
            self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
            save = self.run_cli("save", env_override=env_override)
            self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

            content = output_path.read_text(encoding="utf-8")
            self.assert_userspace_trace(content, "gdb-qemu-riscv")
        finally:
            self.run_cli("stop", env_override=env_override)

    def test_qemu_user_arm_printf_program(self) -> None:
        env_override = {
            "GDBTRACE_CAPTURE_BACKEND": "gdb-qemu-arm",
            "GDBTRACE_GDB_MAX_STEPS": "20000",
            "LD_BIND_NOW": "1",
        }
        elf_path, _ = self.compile_arm_userspace("arm32", "userspace_printf_app.c")
        output_path = self.state_dir / "arm32_printf.log"
        self.configure(ARM_PORTS["arm32"], "arm32", elf_path, output_path, env_override)

        try:
            start = self.run_cli("start", env_override=env_override)
            self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
            save = self.run_cli("save", env_override=env_override)
            self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

            content = output_path.read_text(encoding="utf-8")
            self.assert_printf_trace(content, "gdb-qemu-arm")
        finally:
            self.run_cli("stop", env_override=env_override)

    def test_qemu_user_riscv64_printf_program(self) -> None:
        env_override = {
            "GDBTRACE_CAPTURE_BACKEND": "gdb-qemu-riscv",
            "GDBTRACE_GDB_MAX_STEPS": "20000",
            "GDBTRACE_GDB_QEMU_RISCV_SYSROOT": "/usr/riscv64-linux-gnu",
            "LD_BIND_NOW": "1",
        }
        elf_path, _ = self.compile_riscv64_userspace("userspace_printf_app.c")
        output_path = self.state_dir / "riscv64_printf.log"
        self.configure(RISCV64_PORT, "riscv64", elf_path, output_path, env_override)

        try:
            start = self.run_cli("start", env_override=env_override)
            self.assertEqual(start.returncode, 0, msg=start.stdout or start.stderr)
            save = self.run_cli("save", env_override=env_override)
            self.assertEqual(save.returncode, 0, msg=save.stdout or save.stderr)

            content = output_path.read_text(encoding="utf-8")
            self.assert_printf_trace(content, "gdb-qemu-riscv")
        finally:
            self.run_cli("stop", env_override=env_override)


if __name__ == "__main__":
    unittest.main()
