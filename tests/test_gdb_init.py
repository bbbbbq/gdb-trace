from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = REPO_ROOT / "gdbtrace" / "gdb_init.py"


class GdbInitInstallTest(unittest.TestCase):
    def test_gdb_init_loads_package_and_registers_command(self) -> None:
        result = subprocess.run(
            [
                "gdb",
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
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn(str(REPO_ROOT / "gdbtrace" / "__init__.py"), result.stdout)
        self.assertIn("gdbtrace-run", result.stdout)
        self.assertIn("GDBTRACE_GDB_", result.stdout)


if __name__ == "__main__":
    unittest.main()
