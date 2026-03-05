from __future__ import annotations

import json
import os
import subprocess
import time
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


class QemuArmRemoteCaptureBackend(CaptureBackend):
    name = "gdb-qemu-arm"

    def capture(self, request: CaptureRequest) -> CaptureResult:
        if request.arch not in {"arm32", "thumb", "thumb2"}:
            raise GdbTraceError("gdb-qemu-arm backend supports only arm32, thumb, thumb2")

        elf_path = Path(request.elf)
        if not elf_path.exists():
            raise GdbTraceError(f"elf file does not exist: {request.elf}")

        host, _, port_text = request.target.rpartition(":")
        if host not in {"127.0.0.1", "localhost"}:
            raise GdbTraceError("gdb-qemu-arm backend requires a local target host")
        port = int(port_text)
        sysroot = os.environ.get("GDBTRACE_QEMU_ARM_SYSROOT", "/usr/arm-linux-gnueabihf")

        repo_root = Path(__file__).resolve().parents[1]
        with NamedTemporaryFile("w+", suffix=".json", delete=False) as handle:
            output_path = Path(handle.name)

        qemu_command = ["qemu-arm", "-g", str(port)]
        if sysroot:
            qemu_command.extend(["-L", sysroot])
        qemu_command.append(str(elf_path.resolve()))
        qemu_process = subprocess.Popen(
            qemu_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            self._wait_for_stub(host, port, qemu_process)
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            pythonpath_entries = [str(repo_root)]
            if existing_pythonpath:
                pythonpath_entries.append(existing_pythonpath)
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
            env["GDBTRACE_GDB_ELF"] = str(elf_path.resolve())
            env["GDBTRACE_GDB_OUTPUT"] = str(output_path)
            env["GDBTRACE_GDB_TARGET"] = request.target
            env["GDBTRACE_GDB_TRANSPORT"] = "remote"
            env["GDBTRACE_GDB_SYSROOT"] = sysroot
            env.setdefault("GDBTRACE_GDB_MAX_STEPS", "8192")

            command = [
                "gdb-multiarch",
                "-q",
                "-batch",
                "-ex",
                "python from gdbtrace.gdb_agent import run; run()",
            ]
            result = self._run_gdb_with_retry(command, env)
            if result.returncode != 0:
                error_output = (result.stderr or result.stdout).strip()
                raise GdbTraceError(f"gdb-qemu-arm backend failed: {error_output}")

            raw_events = json.loads(output_path.read_text(encoding="utf-8"))
            events = [TraceEvent(**event) for event in raw_events]
            return CaptureResult(
                backend=self.name,
                events=events,
                event_count=len(events),
            )
        finally:
            output_path.unlink(missing_ok=True)
            if qemu_process.poll() is None:
                qemu_process.terminate()
                try:
                    qemu_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    qemu_process.kill()
                    qemu_process.wait(timeout=2)

    def _wait_for_stub(self, host: str, port: int, process: subprocess.Popen[str]) -> None:
        deadline = time.time() + 5
        while time.time() < deadline:
            if process.poll() is not None:
                stderr = ""
                if process.stderr is not None:
                    stderr = process.stderr.read().strip()
                raise GdbTraceError(f"qemu-arm exited before gdb attached: {stderr}")
            if self._port_is_listening(host, port):
                return
            time.sleep(0.1)
        raise GdbTraceError("timed out waiting for qemu-arm gdb stub")

    def _port_is_listening(self, host: str, port: int) -> bool:
        del host
        encoded_port = f"{port:04X}"
        for path in ("/proc/net/tcp", "/proc/net/tcp6"):
            proc_file = Path(path)
            if not proc_file.exists():
                continue
            for line in proc_file.read_text(encoding="utf-8").splitlines()[1:]:
                columns = line.split()
                if len(columns) < 4:
                    continue
                local_address = columns[1]
                state = columns[3]
                if state != "0A":
                    continue
                if local_address.endswith(f":{encoded_port}"):
                    return True
        return False

    def _run_gdb_with_retry(self, command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        last_result: subprocess.CompletedProcess[str] | None = None
        for _ in range(5):
            result = subprocess.run(
                command,
                env=env,
                text=True,
                capture_output=True,
            )
            last_result = result
            if result.returncode == 0:
                return result
            stderr = result.stderr or result.stdout
            if "could not connect" not in stderr:
                return result
            time.sleep(0.2)
        assert last_result is not None
        return last_result


def resolve_capture_backend() -> CaptureBackend:
    backend_name = os.environ.get("GDBTRACE_CAPTURE_BACKEND", "static")
    if backend_name == "static":
        return StaticSampleCaptureBackend()
    if backend_name == "gdb-native":
        return NativeGdbCaptureBackend()
    if backend_name == "gdb-qemu-arm":
        return QemuArmRemoteCaptureBackend()
    raise GdbTraceError(f"unsupported capture backend: {backend_name}")
