from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = REPO_ROOT / "gdbtrace" / "gdb_init.py"
EXPECTED_USER_COMMANDS = (
    "set-target",
    "set-default-target",
    "show-target",
    "clear-target",
    "clear-default-target",
    "set-arch",
    "set-elf",
    "set-output",
    "set-mode",
    "set-registers",
    "show-config",
    "clear-arch",
    "clear-elf",
    "clear-output",
    "clear-mode",
    "clear-registers",
    "start",
    "pause",
    "save",
    "stop",
    "gdbtrace-run",
)


class GdbInitInstallTest(unittest.TestCase):
    def run_gdb(
        self,
        *args: str,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gdb", *args],
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
                    "help set-target\n"
                    "set-target 127.0.0.1:1234\n"
                    "set-arch aarch64\n"
                    "set-elf demo.elf\n"
                    "set-output trace.log\n"
                    "set-mode both\n"
                    "show-config\n"
                    "show-target\n"
                    "start\n"
                    "save\n"
                    "stop\n"
                    "quit\n"
                ),
                env=env,
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("Set the current session target. Usage: set-target <ip:port>", result.stdout)
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


if __name__ == "__main__":
    unittest.main()
