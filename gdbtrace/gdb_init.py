from __future__ import annotations

import builtins
import os
import re
import sys
from pathlib import Path

import gdb


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SENTINEL = "_gdbtrace_gdb_init_installed"
GDBTRACE_PREFIX = "gdbtrace"
CLI_COMMAND_DOCS = {
    "set-arch": "Set the trace architecture. Usage: gdbtrace set-arch <thumb|thumb2|arm32|aarch64|riscv32|riscv64>",
    "set-elf": "Set the current session ELF path. Usage: gdbtrace set-elf <file>",
    "set-output": "Set the current session log path. Usage: gdbtrace set-output <path.log>",
    "set-mode": "Set the trace mode. Usage: gdbtrace set-mode <inst|call|both>",
    "set-registers": "Set register logging. Usage: gdbtrace set-registers <on|off>",
    "show-config": "Show the current trace configuration.",
    "clear-arch": "Clear the current session architecture.",
    "clear-elf": "Clear the current session ELF path.",
    "clear-output": "Clear the current session output path.",
    "clear-mode": "Clear the current session trace mode.",
    "clear-registers": "Clear the current session register logging mode.",
    "start": "Start or resume trace capture. Usage: gdbtrace start [--start <addr|symbol>] [--stop <addr|symbol>] [--filter-func <pattern>] [--filter-range <start:end>]",
    "pause": "Pause the current trace.",
    "save": "Write the current trace snapshot to the configured output path.",
    "stop": "Stop the current trace and save the final result.",
}


def _ensure_repo_on_sys_path() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _current_elf_from_gdb() -> str:
    return gdb.current_progspace().filename or ""


def _current_arch_from_gdb() -> str:
    show_arch_output = gdb.execute("show architecture", to_string=True).lower()
    if "aarch64" in show_arch_output:
        return "aarch64"
    if "riscv:rv64" in show_arch_output:
        return "riscv64"
    if "riscv:rv32" in show_arch_output:
        return "riscv32"
    if re.search(r"\barm\b", show_arch_output) or "armv" in show_arch_output:
        return "arm32"
    return ""


def _ensure_current_inferior_ready() -> None:
    try:
        gdb.execute("x/i $pc", to_string=True)
    except gdb.error as exc:
        if "No registers" in str(exc):
            raise gdb.GdbError("error: current inferior is not stopped at a debuggable location") from None
        raise


def _invoke_cli_command(name: str, arg: str) -> None:
    _ensure_repo_on_sys_path()
    from gdbtrace.cli import build_parser
    from gdbtrace.state import GdbTraceError, resolve_paths, save_session_state, session_state

    parser = build_parser()
    argv = [name, *gdb.string_to_argv(arg)]
    paths = resolve_paths()
    previous_backend = os.environ.get("GDBTRACE_CAPTURE_BACKEND")

    if name == "start":
        session = session_state(paths)
        if not session.get("arch"):
            current_arch = _current_arch_from_gdb()
            if current_arch:
                session["arch"] = current_arch
        if not session.get("elf"):
            current_elf = _current_elf_from_gdb()
            if current_elf:
                session["elf"] = current_elf
        if session.get("arch") or session.get("elf"):
            save_session_state(paths, session)
        if not previous_backend:
            os.environ["GDBTRACE_CAPTURE_BACKEND"] = "gdb-current-session"
        if os.environ.get("GDBTRACE_CAPTURE_BACKEND") != "static":
            _ensure_current_inferior_ready()

    try:
        parsed = parser.parse_args(argv)
        return_code = parsed.handler(parsed, paths)
    except GdbTraceError as exc:
        raise gdb.GdbError(f"error: {exc}") from exc
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code:
            raise gdb.GdbError(f"invalid arguments for {name}") from None
        return
    finally:
        if name == "start":
            if previous_backend is None:
                os.environ.pop("GDBTRACE_CAPTURE_BACKEND", None)
            else:
                os.environ["GDBTRACE_CAPTURE_BACKEND"] = previous_backend
    if return_code:
        raise gdb.GdbError(f"gdbtrace command failed: {name}")


class GdbTracePrefixCommand(gdb.Command):
    """gdbtrace command namespace."""

    def __init__(self) -> None:
        super().__init__(GDBTRACE_PREFIX, gdb.COMMAND_USER, prefix=True)


class GdbTraceRunCommand(gdb.Command):
    """Run gdbtrace capture agent using GDBTRACE_GDB_* environment variables."""

    def __init__(self) -> None:
        super().__init__(f"{GDBTRACE_PREFIX} run", gdb.COMMAND_USER)

    def invoke(self, arg: str, from_tty: bool) -> None:
        del arg, from_tty
        _ensure_repo_on_sys_path()
        from gdbtrace.gdb_agent import run

        run()


class _GdbTraceCliCommand(gdb.Command):
    command_name = ""

    def __init__(self) -> None:
        super().__init__(f"{GDBTRACE_PREFIX} {self.command_name}", gdb.COMMAND_USER)

    def invoke(self, arg: str, from_tty: bool) -> None:
        del from_tty
        _invoke_cli_command(self.command_name, arg)


def _register_cli_commands() -> None:
    for command_name, command_doc in CLI_COMMAND_DOCS.items():
        class_name = "".join(part.capitalize() for part in command_name.split("-")) + "Command"
        command_type = type(
            class_name,
            (_GdbTraceCliCommand,),
            {
                "__doc__": command_doc,
                "command_name": command_name,
            },
        )
        command_type()


def install() -> None:
    _ensure_repo_on_sys_path()
    if getattr(builtins, INSTALL_SENTINEL, False):
        return
    GdbTracePrefixCommand()
    _register_cli_commands()
    GdbTraceRunCommand()
    setattr(builtins, INSTALL_SENTINEL, True)


install()
