from __future__ import annotations

import os
from dataclasses import dataclass

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


def resolve_capture_backend() -> CaptureBackend:
    backend_name = os.environ.get("GDBTRACE_CAPTURE_BACKEND", "static")
    if backend_name == "static":
        return StaticSampleCaptureBackend()
    raise GdbTraceError(f"unsupported capture backend: {backend_name}")
