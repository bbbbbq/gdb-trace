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
    registers: bool


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
        events = sample_trace_events(request.arch, include_registers=request.registers)
        return CaptureResult(
            backend=self.name,
            events=events,
            event_count=len(events),
        )


def _has_main_symbol(elf_path: Path) -> bool:
    for command in (["readelf", "-Ws", str(elf_path)], ["nm", "-a", str(elf_path)]):
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
            )
        except FileNotFoundError:
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            columns = line.split()
            if columns and columns[-1] == "main":
                return True
    return False


class NativeGdbCaptureBackend(CaptureBackend):
    name = "gdb-native"

    def capture(self, request: CaptureRequest) -> CaptureResult:
        if request.arch != "aarch64":
            raise GdbTraceError("gdb-native backend currently supports only aarch64")

        elf_path = Path(request.elf)
        if not elf_path.exists():
            raise GdbTraceError(f"elf file does not exist: {request.elf}")
        has_main_symbol = _has_main_symbol(elf_path)
        if request.mode != "inst" and not has_main_symbol:
            raise GdbTraceError("ELF without main symbol supports only inst mode in real backends")

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
        env["GDBTRACE_GDB_ARCH"] = request.arch
        env["GDBTRACE_GDB_SYMBOL_MODE"] = "main" if has_main_symbol else "entry"
        env["GDBTRACE_GDB_REGISTERS"] = "on" if request.registers else "off"
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


class QemuRemoteCaptureBackend(CaptureBackend):
    qemu_bin_by_arch: dict[str, str] = {}
    supported_archs: tuple[str, ...] = ()
    default_sysroot = ""
    error_label = "qemu"

    def _validate_arch(self, request: CaptureRequest) -> None:
        if request.arch not in self.supported_archs:
            raise GdbTraceError(
                f"{self.name} backend supports only {', '.join(self.supported_archs)}"
            )

    def capture(self, request: CaptureRequest) -> CaptureResult:
        self._validate_arch(request)
        elf_path = Path(request.elf)
        if not elf_path.exists():
            raise GdbTraceError(f"elf file does not exist: {request.elf}")
        has_main_symbol = _has_main_symbol(elf_path)
        if request.mode != "inst" and not has_main_symbol:
            raise GdbTraceError("ELF without main symbol supports only inst mode in real backends")

        host, _, port_text = request.target.rpartition(":")
        if host not in {"127.0.0.1", "localhost"}:
            raise GdbTraceError(f"{self.name} backend requires a local target host")
        port = int(port_text)
        sysroot = os.environ.get(self._sysroot_env_var(), self.default_sysroot)

        repo_root = Path(__file__).resolve().parents[1]
        with NamedTemporaryFile("w+", suffix=".json", delete=False) as handle:
            output_path = Path(handle.name)

        qemu_command = [self.qemu_bin_by_arch[request.arch], "-g", str(port)]
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
            env["GDBTRACE_GDB_ARCH"] = request.arch
            env["GDBTRACE_GDB_SYMBOL_MODE"] = "main" if has_main_symbol else "entry"
            env["GDBTRACE_GDB_REGISTERS"] = "on" if request.registers else "off"
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
                raise GdbTraceError(f"{self.name} backend failed: {error_output}")

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
                raise GdbTraceError(f"{self.error_label} exited before gdb attached: {stderr}")
            if self._port_is_listening(host, port):
                return
            time.sleep(0.1)
        raise GdbTraceError(f"timed out waiting for {self.error_label} gdb stub")

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

    def _sysroot_env_var(self) -> str:
        return f"GDBTRACE_{self.name.upper().replace('-', '_')}_SYSROOT"


class QemuArmRemoteCaptureBackend(QemuRemoteCaptureBackend):
    name = "gdb-qemu-arm"
    supported_archs = ("arm32", "thumb", "thumb2")
    qemu_bin_by_arch = {
        "arm32": "qemu-arm",
        "thumb": "qemu-arm",
        "thumb2": "qemu-arm",
    }
    default_sysroot = "/usr/arm-linux-gnueabihf"
    error_label = "qemu-arm"


class QemuAarch64RemoteCaptureBackend(QemuRemoteCaptureBackend):
    name = "gdb-qemu-aarch64"
    supported_archs = ("aarch64",)
    qemu_bin_by_arch = {
        "aarch64": "qemu-aarch64",
    }
    default_sysroot = "/usr/aarch64-linux-gnu"
    error_label = "qemu-aarch64"


class QemuRiscvRemoteCaptureBackend(QemuRemoteCaptureBackend):
    name = "gdb-qemu-riscv"
    supported_archs = ("riscv32", "riscv64")
    qemu_bin_by_arch = {
        "riscv32": "qemu-riscv32",
        "riscv64": "qemu-riscv64",
    }
    default_sysroot = ""
    error_label = "qemu-riscv"


def resolve_capture_backend() -> CaptureBackend:
    backend_name = os.environ.get("GDBTRACE_CAPTURE_BACKEND", "static")
    if backend_name == "static":
        return StaticSampleCaptureBackend()
    if backend_name == "gdb-native":
        return NativeGdbCaptureBackend()
    if backend_name == "gdb-qemu-aarch64":
        return QemuAarch64RemoteCaptureBackend()
    if backend_name == "gdb-qemu-arm":
        return QemuArmRemoteCaptureBackend()
    if backend_name == "gdb-qemu-riscv":
        return QemuRiscvRemoteCaptureBackend()
    raise GdbTraceError(f"unsupported capture backend: {backend_name}")
