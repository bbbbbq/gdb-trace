from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliConfigTest(unittest.TestCase):
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

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "gdbtrace", *args],
            cwd=REPO_ROOT,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_target_resolution_prefers_session_target(self) -> None:
        self.assertEqual(self.run_cli("set-default-target", "10.0.0.1:1234").returncode, 0)
        self.assertEqual(self.run_cli("set-target", "127.0.0.1:9999").returncode, 0)
        result = self.run_cli("show-target")
        self.assertEqual(result.returncode, 0)
        self.assertIn("current_target=127.0.0.1:9999", result.stdout)
        self.assertIn("default_target=10.0.0.1:1234", result.stdout)
        self.assertIn("effective_target=127.0.0.1:9999", result.stdout)

    def test_show_and_clear_config_round_trip(self) -> None:
        self.assertEqual(self.run_cli("set-arch", "thumb2").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", "trace.log").returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)
        shown = self.run_cli("show-config")
        self.assertIn("arch=thumb2", shown.stdout)
        self.assertIn("elf=demo.elf", shown.stdout)
        self.assertIn("output=trace.log", shown.stdout)
        self.assertIn("mode=both", shown.stdout)

        self.assertEqual(self.run_cli("clear-arch").returncode, 0)
        self.assertEqual(self.run_cli("clear-elf").returncode, 0)
        self.assertEqual(self.run_cli("clear-output").returncode, 0)
        self.assertEqual(self.run_cli("clear-mode").returncode, 0)
        cleared = self.run_cli("show-config")
        self.assertIn("arch=<unset>", cleared.stdout)
        self.assertIn("elf=<unset>", cleared.stdout)
        self.assertIn("output=<unset>", cleared.stdout)
        self.assertIn("mode=<unset>", cleared.stdout)

    def test_rejects_invalid_output_extension(self) -> None:
        result = self.run_cli("set-output", "trace.txt")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: output path must end with .log", result.stdout)


if __name__ == "__main__":
    unittest.main()
