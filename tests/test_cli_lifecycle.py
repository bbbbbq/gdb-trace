from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gdbtrace import cli
from gdbtrace.capture import CaptureResult
from gdbtrace.filters import apply_filters
from gdbtrace.state import Paths
from gdbtrace.trace_model import TraceEvent, sample_trace_events


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
        initial_event_count = len(sample_trace_events("aarch64"))

        started = self.run_cli("start")
        self.assertEqual(started.returncode, 0)
        self.assertIn("trace started", started.stdout)
        initial_runtime = json.loads((self.state_dir / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(initial_runtime["event_count"], initial_event_count)

        paused = self.run_cli("pause")
        self.assertEqual(paused.returncode, 0)
        self.assertIn("trace paused", paused.stdout)

        resumed = self.run_cli("start")
        self.assertEqual(resumed.returncode, 0)
        self.assertIn("trace resumed", resumed.stdout)
        resumed_runtime = json.loads((self.state_dir / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(resumed_runtime["event_count"], initial_event_count * 2)

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

    def test_pause_recovers_interrupted_current_session_trace_and_autosaves_snapshot(self) -> None:
        self.configure_trace()
        spool_path = self.state_dir / "runtime.json.events.jsonl"
        runtime_payload = {
            "status": "running",
            "started_at": "2026-03-06T00:00:00+00:00",
            "target": "gdb-managed",
            "config": {
                "arch": "aarch64",
                "elf": "demo.elf",
                "output": str(self.output_path),
                "mode": "both",
                "registers": "off",
            },
            "capture_backend": "gdb-current-session",
            "event_count": 0,
            "filters": {
                "start": "",
                "stop": "",
                "filter_func": "",
                "filter_range": "",
            },
            "events": [],
            "capture_in_progress": True,
            "capture_spool": str(spool_path),
        }
        (self.state_dir / "runtime.json").write_text(json.dumps(runtime_payload), encoding="utf-8")
        spool_path.write_text(
            "\n".join(json.dumps(event.__dict__) for event in sample_trace_events("aarch64")) + "\n",
            encoding="utf-8",
        )

        paused = self.run_cli("pause")
        self.assertNotEqual(paused.returncode, 0)
        self.assertIn("error: no running trace to pause", paused.stdout)
        normalized_runtime = json.loads((self.state_dir / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(normalized_runtime["status"], "paused")
        self.assertNotIn("capture_in_progress", normalized_runtime)
        self.assertFalse(spool_path.exists())
        self.assertTrue(self.output_path.exists())
        self.assertIn("[trace snapshot]", self.output_path.read_text(encoding="utf-8"))
        self.assertTrue(self.call_output_path.exists())

    def test_resume_failure_preserves_existing_runtime(self) -> None:
        raw_events = sample_trace_events("aarch64")
        runtime_payload = {
            "status": "paused",
            "started_at": "2026-03-06T00:00:00+00:00",
            "target": "static",
            "config": {
                "arch": "aarch64",
                "elf": "demo.elf",
                "output": str(self.output_path),
                "mode": "both",
                "registers": "off",
            },
            "capture_backend": "static",
            "event_count": len(raw_events),
            "filters": {
                "start": "",
                "stop": "",
                "filter_func": "",
                "filter_range": "",
            },
            "raw_events": [event.__dict__ for event in raw_events],
            "events": [event.__dict__ for event in raw_events],
        }
        runtime_path = self.state_dir / "runtime.json"
        runtime_path.write_text(json.dumps(runtime_payload), encoding="utf-8")
        paths = Paths(
            session_file=self.state_dir / "session.json",
            global_config_file=self.state_dir / "global.json",
            runtime_file=runtime_path,
        )

        class FailingBackend:
            name = "static"

            def capture(self, request, event_sink=None):
                del request, event_sink
                raise RuntimeError("backend exploded during resume")

        args = argparse.Namespace(start_addr=None, stop_addr=None, filter_func=None, filter_range=None)
        with mock.patch("gdbtrace.cli.resolve_capture_backend_by_name", return_value=FailingBackend()):
            with self.assertRaisesRegex(RuntimeError, "backend exploded during resume"):
                cli.cmd_start(args, paths)

        restored_runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        self.assertEqual(runtime_payload, restored_runtime)

    def test_resume_reapplies_filters_over_full_raw_trace(self) -> None:
        raw_events = sample_trace_events("aarch64")
        filtered_events = apply_filters(raw_events, filter_func="func_b")
        runtime_payload = {
            "status": "paused",
            "started_at": "2026-03-06T00:00:00+00:00",
            "target": "static",
            "config": {
                "arch": "aarch64",
                "elf": "demo.elf",
                "output": str(self.output_path),
                "mode": "both",
                "registers": "off",
            },
            "capture_backend": "static",
            "event_count": len(filtered_events),
            "filters": {
                "start": "",
                "stop": "",
                "filter_func": "func_b",
                "filter_range": "",
            },
            "raw_events": [event.__dict__ for event in raw_events],
            "events": [event.__dict__ for event in filtered_events],
        }
        runtime_path = self.state_dir / "runtime.json"
        runtime_path.write_text(json.dumps(runtime_payload), encoding="utf-8")
        paths = Paths(
            session_file=self.state_dir / "session.json",
            global_config_file=self.state_dir / "global.json",
            runtime_file=runtime_path,
        )
        resumed_segment = [
            TraceEvent("call", 0, "resume_only"),
            TraceEvent("inst", 1, "resume_only", "0x500000", "nop"),
            TraceEvent("ret", 0, "resume_only"),
        ]

        class ReturningBackend:
            name = "static"

            def capture(self, request, event_sink=None):
                del request, event_sink
                return CaptureResult(
                    backend="static",
                    target_label="static",
                    events=resumed_segment,
                    event_count=len(resumed_segment),
                    interrupted=False,
                )

        args = argparse.Namespace(start_addr=None, stop_addr=None, filter_func=None, filter_range=None)
        with mock.patch("gdbtrace.cli.resolve_capture_backend_by_name", return_value=ReturningBackend()):
            result = cli.cmd_start(args, paths)

        self.assertEqual(0, result)
        resumed_runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        self.assertEqual("running", resumed_runtime["status"])
        self.assertEqual(len(raw_events) + len(resumed_segment), len(resumed_runtime["raw_events"]))
        self.assertEqual([event.__dict__ for event in filtered_events], resumed_runtime["events"])

    def test_save_after_interrupted_resume_keeps_prior_filtered_trace(self) -> None:
        raw_events = sample_trace_events("aarch64")
        filtered_events = apply_filters(raw_events, filter_func="func_b")
        spool_path = self.state_dir / "runtime.json.events.jsonl"
        runtime_payload = {
            "status": "running",
            "started_at": "2026-03-06T00:00:00+00:00",
            "target": "gdb-managed",
            "config": {
                "arch": "aarch64",
                "elf": "demo.elf",
                "output": str(self.output_path),
                "mode": "both",
                "registers": "off",
            },
            "capture_backend": "gdb-current-session",
            "event_count": len(filtered_events),
            "filters": {
                "start": "",
                "stop": "",
                "filter_func": "func_b",
                "filter_range": "",
            },
            "raw_events": [event.__dict__ for event in raw_events],
            "events": [event.__dict__ for event in filtered_events],
            "capture_in_progress": True,
            "capture_spool": str(spool_path),
        }
        (self.state_dir / "runtime.json").write_text(json.dumps(runtime_payload), encoding="utf-8")
        resumed_segment = [
            TraceEvent("call", 0, "resume_only"),
            TraceEvent("inst", 1, "resume_only", "0x500000", "nop"),
            TraceEvent("ret", 0, "resume_only"),
        ]
        spool_path.write_text(
            "\n".join(json.dumps(event.__dict__) for event in resumed_segment) + "\n",
            encoding="utf-8",
        )

        saved = self.run_cli("save")
        self.assertEqual(saved.returncode, 0)
        resumed_runtime = json.loads((self.state_dir / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual([event.__dict__ for event in filtered_events], resumed_runtime["events"])
        self.assertEqual(len(raw_events) + len(resumed_segment), len(resumed_runtime["raw_events"]))


if __name__ == "__main__":
    unittest.main()
