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


class CaptureBackend:
    def capture(self, request: CaptureRequest) -> list[TraceEvent]:
        raise NotImplementedError


class StaticSampleCaptureBackend(CaptureBackend):
    def capture(self, request: CaptureRequest) -> list[TraceEvent]:
        return sample_trace_events(request.arch)


def resolve_capture_backend() -> tuple[str, CaptureBackend]:
    backend_name = os.environ.get("GDBTRACE_CAPTURE_BACKEND", "static")
    if backend_name == "static":
        return backend_name, StaticSampleCaptureBackend()
    raise GdbTraceError(f"unsupported capture backend: {backend_name}")
