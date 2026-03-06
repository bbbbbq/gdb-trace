from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = REPO_ROOT / "gdbtrace" / "gdb_init.py"


class GdbInitInstallTest(unittest.TestCase):
    def run_gdb(
        self,
        *args: str,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gdb", *args],
            cwd=REPO_ROOT,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
        )

    def test_gdb_init_loads_package_and_registers_command(self) -> None:
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
        self.assertIn("gdbtrace-run", result.stdout)
        self.assertIn("GDBTRACE_GDB_", result.stdout)

    def test_gdbinit_autoloads_init_in_interactive_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
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

            result = self.run_gdb(
                "-q",
                input_text="set pagination off\nhelp gdbtrace-run\nquit\n",
                env=env,
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("Run gdbtrace capture agent using GDBTRACE_GDB_* environment variables.", result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("Undefined command", result.stdout)


if __name__ == "__main__":
    unittest.main()
