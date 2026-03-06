from __future__ import annotations

import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = REPO_ROOT / "gdbtrace" / "gdb_init.py"
EXPECTED_USER_COMMANDS = (
    "gdbtrace -- gdbtrace command namespace.",
    "gdbtrace clear-arch",
    "gdbtrace clear-default-target",
    "gdbtrace clear-elf",
    "gdbtrace clear-mode",
    "gdbtrace clear-output",
    "gdbtrace clear-registers",
    "gdbtrace clear-target",
    "gdbtrace pause",
    "gdbtrace run",
    "gdbtrace save",
    "gdbtrace set-arch",
    "gdbtrace set-default-target",
    "gdbtrace set-elf",
    "gdbtrace set-mode",
    "gdbtrace set-output",
    "gdbtrace set-registers",
    "gdbtrace set-target",
    "gdbtrace show-config",
    "gdbtrace show-target",
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
                    "help gdbtrace set-target\n"
                    "gdbtrace set-target 127.0.0.1:1234\n"
                    "gdbtrace set-arch aarch64\n"
                    "gdbtrace set-elf demo.elf\n"
                    "gdbtrace set-output trace.log\n"
                    "gdbtrace set-mode both\n"
                    "gdbtrace show-config\n"
                    "gdbtrace show-target\n"
                    "gdbtrace start\n"
                    "gdbtrace save\n"
                    "gdbtrace stop\n"
                    "quit\n"
                ),
                env=env,
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("Set the current session target. Usage: gdbtrace set-target <ip:port>", result.stdout)
            self.assertIn("target=127.0.0.1:1234", result.stdout)
            self.assertIn("arch=aarch64", result.stdout)
            self.assertIn("elf=demo.elf", result.stdout)
            self.assertIn("output=trace.log", result.stdout)
            self.assertIn("mode=both", result.stdout)
            self.assertIn("effective_target=127.0.0.1:1234", result.stdout)
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
                    "gdbtrace set-target 127.0.0.1:1234\n"
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
                    "gdbtrace set-target 127.0.0.1:1234\n"
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


if __name__ == "__main__":
    unittest.main()
