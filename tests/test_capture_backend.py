from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CaptureBackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.output_path = self.state_dir / "trace.log"
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(REPO_ROOT)
        self.env["GDBTRACE_SESSION_FILE"] = str(self.state_dir / "session.json")
        self.env["GDBTRACE_GLOBAL_CONFIG"] = str(self.state_dir / "global.json")
        self.env["GDBTRACE_RUNTIME_FILE"] = str(self.state_dir / "runtime.json")

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

    def configure(self) -> None:
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)

    def test_start_uses_default_static_backend(self) -> None:
        self.configure()
        self.assertEqual(self.run_cli("start").returncode, 0)
        runtime_payload = Path(self.env["GDBTRACE_RUNTIME_FILE"]).read_text(encoding="utf-8")
        self.assertIn('"capture_backend": "static"', runtime_payload)
        self.assertIn('"event_count": 14', runtime_payload)

    def test_start_rejects_unknown_backend(self) -> None:
        self.configure()
        result = self.run_cli("start", env_override={"GDBTRACE_CAPTURE_BACKEND": "gdb"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: unsupported capture backend: gdb", result.stdout)


if __name__ == "__main__":
    unittest.main()
