from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.output_path = self.state_dir / "trace.log"
        self.call_output_path = self.state_dir / "trace.call.log"
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

    def configure_trace(self) -> None:
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)

    def test_start_reports_all_missing_required_config(self) -> None:
        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: missing required trace config: arch, elf, output, mode", result.stdout)

    def test_start_reports_remaining_missing_required_config(self) -> None:
        self.assertEqual(self.run_cli("set-arch", "thumb").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        result = self.run_cli("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: missing required trace config: elf, mode", result.stdout)

    def test_start_no_longer_requires_target_for_static_backend(self) -> None:
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)
        result = self.run_cli("start")
        self.assertEqual(result.returncode, 0)
        self.assertIn("trace started", result.stdout)
        runtime_payload = json.loads((self.state_dir / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime_payload["target"], "static")
        self.assertEqual(self.run_cli("stop").returncode, 0)

    def test_real_backend_requires_explicit_test_harness_target(self) -> None:
        self.assertEqual(self.run_cli("set-arch", "aarch64").returncode, 0)
        self.assertEqual(self.run_cli("set-elf", "demo.elf").returncode, 0)
        self.assertEqual(self.run_cli("set-output", str(self.output_path)).returncode, 0)
        self.assertEqual(self.run_cli("set-mode", "both").returncode, 0)
        result = self.run_cli(
            "start",
            env_override={"GDBTRACE_CAPTURE_BACKEND": "gdb-qemu-aarch64"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "error: gdb-qemu-aarch64 backend requires GDBTRACE_GDB_TARGET when started outside GDB",
            result.stdout,
        )

    def test_pause_start_save_stop_round_trip(self) -> None:
        self.configure_trace()

        started = self.run_cli("start")
        self.assertEqual(started.returncode, 0)
        self.assertIn("trace started", started.stdout)

        paused = self.run_cli("pause")
        self.assertEqual(paused.returncode, 0)
        self.assertIn("trace paused", paused.stdout)

        resumed = self.run_cli("start")
        self.assertEqual(resumed.returncode, 0)
        self.assertIn("trace resumed", resumed.stdout)

        saved = self.run_cli("save")
        self.assertEqual(saved.returncode, 0)
        self.assertIn(f"trace saved to {self.output_path}, {self.call_output_path}", saved.stdout)
        self.assertTrue(self.output_path.exists())
        self.assertTrue(self.call_output_path.exists())
        save_content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("[trace snapshot]", save_content)
        self.assertIn("trace_mode=both", save_content)
        call_save_content = self.call_output_path.read_text(encoding="utf-8")
        self.assertIn("trace_mode=call", call_save_content)
        self.assertIn("\x1b[32mcall main\x1b[0m", call_save_content)
        self.assertNotIn("0x400580 stp x29, x30, [sp, #-16]!", call_save_content)

        stopped = self.run_cli("stop")
        self.assertEqual(stopped.returncode, 0)
        self.assertIn(f"trace stopped and saved to {self.output_path}, {self.call_output_path}", stopped.stdout)
        stop_content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("[trace final]", stop_content)
        self.assertIn("\x1b[32mcall main\x1b[0m", stop_content)
        self.assertIn("    0x400580 stp x29, x30, [sp, #-16]!", stop_content)

    def test_resume_rejects_new_runtime_arguments(self) -> None:
        self.configure_trace()
        self.assertEqual(self.run_cli("start").returncode, 0)
        self.assertEqual(self.run_cli("pause").returncode, 0)
        result = self.run_cli("start", "--start", "0x400580")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: cannot change trace arguments while resuming a paused trace", result.stdout)


if __name__ == "__main__":
    unittest.main()
