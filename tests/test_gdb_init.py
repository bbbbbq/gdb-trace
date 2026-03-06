from __future__ import annotations

import json
import os
import fcntl
import pty
import select
import subprocess
import tempfile
import termios
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = REPO_ROOT / "gdbtrace" / "gdb_init.py"
EXPECTED_USER_COMMANDS = (
    "gdbtrace -- gdbtrace command namespace.",
    "gdbtrace clear-arch",
    "gdbtrace clear-elf",
    "gdbtrace clear-mode",
    "gdbtrace clear-output",
    "gdbtrace clear-registers",
    "gdbtrace pause",
    "gdbtrace run",
    "gdbtrace save",
    "gdbtrace set-arch",
    "gdbtrace set-elf",
    "gdbtrace set-mode",
    "gdbtrace set-output",
    "gdbtrace set-registers",
    "gdbtrace show-config",
    "gdbtrace start",
    "gdbtrace stop",
)


class GdbInitInstallTest(unittest.TestCase):
    def run_gdb(
        self,
        *args: str,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        gdb_bin: str = "gdb",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [gdb_bin, *args],
            cwd=cwd or REPO_ROOT,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
        )

    def test_gdb_init_loads_package_and_registers_commands(self) -> None:
        result = self.run_gdb(
            "-q",
            "-batch",
            "-ex",
            f"python import runpy; runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
            "-ex",
            f"python import runpy; runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
            "-ex",
            "python import gdbtrace; print(gdbtrace.__file__)",
            "-ex",
            "help user-defined",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn(str(REPO_ROOT / "gdbtrace" / "__init__.py"), result.stdout)
        for command_name in EXPECTED_USER_COMMANDS:
            self.assertIn(command_name, result.stdout)

        help_result = self.run_gdb(
            "-q",
            "-batch",
            "-ex",
            f"python import runpy; runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
            "-ex",
            "help gdbtrace start",
        )
        self.assertEqual(help_result.returncode, 0, msg=help_result.stderr or help_result.stdout)
        self.assertNotIn("--target", help_result.stdout)

    def test_gdbinit_autoloads_commands_and_runs_minimal_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_workdir:
            workdir = Path(temp_workdir)
            gdbinit_path = Path(temp_home) / ".gdbinit"
            gdbinit_path.write_text(
                "\n".join(
                    [
                        "python",
                        "import runpy",
                        f"runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = temp_home
            env.pop("PYTHONPATH", None)
            env["GDBTRACE_GLOBAL_CONFIG"] = str(workdir / "global.json")
            env["GDBTRACE_SESSION_FILE"] = str(workdir / "session.json")
            env["GDBTRACE_RUNTIME_FILE"] = str(workdir / "runtime.json")
            env["GDBTRACE_CAPTURE_BACKEND"] = "static"

            result = self.run_gdb(
                "-q",
                input_text=(
                    "set pagination off\n"
                    "help gdbtrace set-output\n"
                    "gdbtrace set-arch aarch64\n"
                    "gdbtrace set-elf demo.elf\n"
                    "gdbtrace set-output trace.log\n"
                    "gdbtrace set-mode both\n"
                    "gdbtrace show-config\n"
                    "gdbtrace start\n"
                    "gdbtrace save\n"
                    "gdbtrace stop\n"
                    "quit\n"
                ),
                env=env,
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("Set the current session log path. Usage: gdbtrace set-output <path.log>", result.stdout)
            self.assertIn("arch=aarch64", result.stdout)
            self.assertIn("elf=demo.elf", result.stdout)
            self.assertIn("output=trace.log", result.stdout)
            self.assertIn("mode=both", result.stdout)
            self.assertNotIn("target=", result.stdout)
            self.assertIn("trace started", result.stdout)
            self.assertIn("trace saved to trace.log, trace.call.log", result.stdout)
            self.assertIn("trace stopped and saved to trace.log, trace.call.log", result.stdout)
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Undefined command", result.stdout)
            self.assertTrue((workdir / "trace.log").exists())
            self.assertTrue((workdir / "trace.call.log").exists())

    def test_gdbtrace_start_rejects_removed_target_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_workdir:
            workdir = Path(temp_workdir)
            gdbinit_path = Path(temp_home) / ".gdbinit"
            gdbinit_path.write_text(
                "\n".join(
                    [
                        "python",
                        "import runpy",
                        f"runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = temp_home
            env.pop("PYTHONPATH", None)
            env["GDBTRACE_GLOBAL_CONFIG"] = str(workdir / "global.json")
            env["GDBTRACE_SESSION_FILE"] = str(workdir / "session.json")
            env["GDBTRACE_RUNTIME_FILE"] = str(workdir / "runtime.json")
            env["GDBTRACE_CAPTURE_BACKEND"] = "static"

            result = self.run_gdb(
                "-q",
                input_text="gdbtrace start --target 127.0.0.1:1234\nquit\n",
                env=env,
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("invalid arguments for start", result.stderr)

    def test_gdbtrace_start_can_infer_elf_from_current_gdb_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_workdir:
            workdir = Path(temp_workdir)
            gdbinit_path = Path(temp_home) / ".gdbinit"
            gdbinit_path.write_text(
                "\n".join(
                    [
                        "python",
                        "import runpy",
                        f"runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = temp_home
            env.pop("PYTHONPATH", None)
            env["GDBTRACE_GLOBAL_CONFIG"] = str(workdir / "global.json")
            env["GDBTRACE_SESSION_FILE"] = str(workdir / "session.json")
            env["GDBTRACE_RUNTIME_FILE"] = str(workdir / "runtime.json")
            env["GDBTRACE_CAPTURE_BACKEND"] = "static"

            result = self.run_gdb(
                "-q",
                input_text=(
                    "set pagination off\n"
                    "file /bin/true\n"
                    "gdbtrace set-arch aarch64\n"
                    "gdbtrace set-output infer.log\n"
                    "gdbtrace set-mode both\n"
                    "gdbtrace start\n"
                    "gdbtrace save\n"
                    "gdbtrace stop\n"
                    "quit\n"
                ),
                env=env,
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("Reading symbols from /bin/true", result.stdout)
            self.assertIn("trace started", result.stdout)
            self.assertTrue((workdir / "infer.log").exists())
            self.assertTrue((workdir / "infer.call.log").exists())
            self.assertIn("elf=/usr/bin/true", (workdir / "infer.log").read_text(encoding="utf-8"))

            session_payload = json.loads((workdir / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session_payload["elf"], "/usr/bin/true")

    def test_gdbtrace_start_can_infer_arch_from_current_gdb_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_workdir:
            workdir = Path(temp_workdir)
            gdbinit_path = Path(temp_home) / ".gdbinit"
            gdbinit_path.write_text(
                "\n".join(
                    [
                        "python",
                        "import runpy",
                        f"runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = temp_home
            env.pop("PYTHONPATH", None)
            env["GDBTRACE_GLOBAL_CONFIG"] = str(workdir / "global.json")
            env["GDBTRACE_SESSION_FILE"] = str(workdir / "session.json")
            env["GDBTRACE_RUNTIME_FILE"] = str(workdir / "runtime.json")
            env["GDBTRACE_CAPTURE_BACKEND"] = "static"

            result = self.run_gdb(
                "-q",
                input_text=(
                    "set pagination off\n"
                    "set architecture aarch64\n"
                    "file /bin/true\n"
                    "gdbtrace set-output infer_arch.log\n"
                    "gdbtrace set-mode both\n"
                    "gdbtrace start\n"
                    "gdbtrace save\n"
                    "gdbtrace stop\n"
                    "quit\n"
                ),
                env=env,
                cwd=workdir,
                gdb_bin="gdb-multiarch",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn('The target architecture is set to "aarch64".', result.stdout)
            self.assertIn("trace started", result.stdout)
            self.assertTrue((workdir / "infer_arch.log").exists())
            self.assertIn("arch=aarch64", (workdir / "infer_arch.log").read_text(encoding="utf-8"))

            session_payload = json.loads((workdir / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session_payload["arch"], "aarch64")

    def test_gdbtrace_start_requires_debuggable_current_inferior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_workdir:
            workdir = Path(temp_workdir)
            gdbinit_path = Path(temp_home) / ".gdbinit"
            gdbinit_path.write_text(
                "\n".join(
                    [
                        "python",
                        "import runpy",
                        f"runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = temp_home
            env.pop("PYTHONPATH", None)
            env["GDBTRACE_GLOBAL_CONFIG"] = str(workdir / "global.json")
            env["GDBTRACE_SESSION_FILE"] = str(workdir / "session.json")
            env["GDBTRACE_RUNTIME_FILE"] = str(workdir / "runtime.json")

            result = self.run_gdb(
                "-q",
                input_text=(
                    "gdbtrace set-arch aarch64\n"
                    "gdbtrace set-elf demo.elf\n"
                    "gdbtrace set-output trace.log\n"
                    "gdbtrace set-mode both\n"
                    "gdbtrace start\n"
                    "quit\n"
                ),
                env=env,
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("current inferior is not stopped at a debuggable location", result.stderr)

    def test_gdbtrace_start_interrupt_keeps_partial_trace_for_save_and_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_workdir:
            workdir = Path(temp_workdir)
            gdbinit_path = Path(temp_home) / ".gdbinit"
            program_path = workdir / "interrupt_probe"
            source_path = workdir / "interrupt_probe.c"
            output_path = workdir / "interrupt.log"
            source_path.write_text(
                "\n".join(
                    [
                        "#include <stdio.h>",
                        "int main(void) {",
                        "    volatile unsigned long counter = 0;",
                        "    while (1) {",
                        "        counter += 1;",
                        "    }",
                        "    return (int)counter;",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            compile_result = subprocess.run(
                ["cc", "-g", "-O0", str(source_path), "-o", str(program_path)],
                cwd=workdir,
                text=True,
                capture_output=True,
            )
            self.assertEqual(compile_result.returncode, 0, msg=compile_result.stderr)

            gdbinit_path.write_text(
                "\n".join(
                    [
                        "python",
                        "import runpy",
                        f"runpy.run_path({str(INIT_SCRIPT)!r}, run_name='__main__')",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = temp_home
            env.pop("PYTHONPATH", None)
            env["GDBTRACE_GLOBAL_CONFIG"] = str(workdir / "global.json")
            env["GDBTRACE_SESSION_FILE"] = str(workdir / "session.json")
            env["GDBTRACE_RUNTIME_FILE"] = str(workdir / "runtime.json")
            env["GDBTRACE_GDB_MAX_STEPS"] = "200000"

            master_fd, slave_fd = pty.openpty()

            def _preexec() -> None:
                os.setsid()
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

            process = subprocess.Popen(
                ["gdb", "-q", str(program_path)],
                cwd=workdir,
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                preexec_fn=_preexec,
                close_fds=True,
            )
            os.close(slave_fd)

            def write_input(text: str) -> None:
                os.write(master_fd, text.encode("utf-8"))

            def read_until(marker: str, timeout: float = 15.0) -> str:
                deadline = time.time() + timeout
                chunks: list[bytes] = []
                while time.time() < deadline:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        continue
                    chunk = os.read(master_fd, 4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    text = b"".join(chunks).decode("utf-8", errors="replace")
                    if marker in text:
                        return text
                raise AssertionError(f"did not observe marker: {marker}")

            def read_command_output(marker: str, timeout: float = 20.0) -> str:
                deadline = time.time() + timeout
                chunks: list[bytes] = []
                while time.time() < deadline:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        continue
                    chunk = os.read(master_fd, 4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    text = b"".join(chunks).decode("utf-8", errors="replace")
                    marker_index = text.find(marker)
                    if marker_index != -1 and "(gdb)" in text[marker_index:]:
                        return text
                raise AssertionError(f"did not observe completed command output for: {marker}")

            try:
                read_until("(gdb)")
                write_input("set pagination off\n")
                write_input("set confirm off\n")
                write_input("break main\n")
                write_input("gdbtrace set-arch aarch64\n")
                write_input(f"gdbtrace set-elf {program_path}\n")
                write_input(f"gdbtrace set-output {output_path}\n")
                write_input("gdbtrace set-mode both\n")
                write_input("run\n")
                read_until("Breakpoint 1", timeout=20.0)
                read_until("(gdb)", timeout=20.0)
                write_input("gdbtrace start\n")
                time.sleep(1.0)
                os.write(master_fd, b"\x03")
                interrupted_output = read_command_output(
                    "trace interrupted and paused; use gdbtrace save or gdbtrace stop",
                    timeout=20.0,
                )

                write_input("gdbtrace save\n")
                save_output = read_command_output("trace saved to", timeout=20.0)
                write_input("gdbtrace stop\n")
                stop_output = read_command_output("trace stopped and saved to", timeout=20.0)
                write_input("kill\n")
                read_until("(gdb)")
                write_input("quit\n")
                process.wait(timeout=10)
            finally:
                os.close(master_fd)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

            combined_output = interrupted_output + save_output + stop_output
            self.assertEqual(process.returncode, 0, msg=combined_output)
            self.assertIn("trace interrupted and paused; use gdbtrace save or gdbtrace stop", combined_output)
            self.assertIn("trace saved to", combined_output)
            self.assertIn("trace stopped and saved to", combined_output)
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("[trace final]", content)
            self.assertIn("call main", content)
            self.assertNotIn("no active trace to save", combined_output)
            self.assertNotIn("no active trace to stop", combined_output)


if __name__ == "__main__":
    unittest.main()
