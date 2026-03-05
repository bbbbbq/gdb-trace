from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from .state import GdbTraceError
from .trace_model import TraceEvent, sample_trace_events


@dataclass(frozen=True)
class CaptureRequest:
    arch: str
    mode: str
    target: str
    elf: str


@dataclass(frozen=True)
class CaptureResult:
    backend: str
    events: list[TraceEvent]
    event_count: int


class CaptureBackend:
    name = "unknown"

    def capture(self, request: CaptureRequest) -> CaptureResult:
        raise NotImplementedError


class StaticSampleCaptureBackend(CaptureBackend):
    name = "static"

    def capture(self, request: CaptureRequest) -> CaptureResult:
        events = sample_trace_events(request.arch)
        return CaptureResult(
            backend=self.name,
            events=events,
            event_count=len(events),
        )


class NativeGdbCaptureBackend(CaptureBackend):
    name = "gdb-native"

    def capture(self, request: CaptureRequest) -> CaptureResult:
        if request.arch != "aarch64":
            raise GdbTraceError("gdb-native backend currently supports only aarch64")

        elf_path = Path(request.elf)
        if not elf_path.exists():
            raise GdbTraceError(f"elf file does not exist: {request.elf}")

        repo_root = Path(__file__).resolve().parents[1]
        with NamedTemporaryFile("w+", suffix=".json", delete=False) as handle:
            output_path = Path(handle.name)

        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        pythonpath_entries = [str(repo_root)]
        if existing_pythonpath:
            pythonpath_entries.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
        env["GDBTRACE_GDB_ELF"] = str(elf_path.resolve())
        env["GDBTRACE_GDB_OUTPUT"] = str(output_path)
        env.setdefault("GDBTRACE_GDB_MAX_STEPS", "4096")

        command = [
            "gdb",
            "-q",
            "-batch",
            "-ex",
            "python from gdbtrace.gdb_agent import run; run()",
        ]
        result = subprocess.run(
            command,
            env=env,
            text=True,
            capture_output=True,
        )
        try:
            if result.returncode != 0:
                error_output = (result.stderr or result.stdout).strip()
                raise GdbTraceError(f"gdb backend failed: {error_output}")

            raw_events = json.loads(output_path.read_text(encoding="utf-8"))
            events = [TraceEvent(**event) for event in raw_events]
            return CaptureResult(
                backend=self.name,
                events=events,
                event_count=len(events),
            )
        finally:
            output_path.unlink(missing_ok=True)


def resolve_capture_backend() -> CaptureBackend:
    backend_name = os.environ.get("GDBTRACE_CAPTURE_BACKEND", "static")
    if backend_name == "static":
        return StaticSampleCaptureBackend()
    if backend_name == "gdb-native":
        return NativeGdbCaptureBackend()
    raise GdbTraceError(f"unsupported capture backend: {backend_name}")
