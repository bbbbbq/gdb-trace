from __future__ import annotations

import builtins
import sys
from pathlib import Path

import gdb


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SENTINEL = "_gdbtrace_gdb_init_installed"
GDBTRACE_PREFIX = "gdbtrace"
CLI_COMMAND_DOCS = {
    "set-target": "Set the current session target. Usage: gdbtrace set-target <ip:port>",
    "set-default-target": "Set the default target. Usage: gdbtrace set-default-target <ip:port>",
    "show-target": "Show current, default, and effective target addresses.",
    "clear-target": "Clear the current session target.",
    "clear-default-target": "Clear the default target address.",
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
    "start": "Start or resume trace capture. Usage: gdbtrace start [--target <ip:port>] [--start <addr|symbol>] [--stop <addr|symbol>] [--filter-func <pattern>] [--filter-range <start:end>]",
    "pause": "Pause the current trace.",
    "save": "Write the current trace snapshot to the configured output path.",
    "stop": "Stop the current trace and save the final result.",
}


def _ensure_repo_on_sys_path() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _invoke_cli_command(name: str, arg: str) -> None:
    _ensure_repo_on_sys_path()
    from gdbtrace.cli import build_parser
    from gdbtrace.state import GdbTraceError, resolve_paths

    parser = build_parser()
    argv = [name, *gdb.string_to_argv(arg)]
    try:
        parsed = parser.parse_args(argv)
        return_code = parsed.handler(parsed, resolve_paths())
    except GdbTraceError as exc:
        raise gdb.GdbError(f"error: {exc}") from exc
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code:
            raise gdb.GdbError(f"invalid arguments for {name}") from None
        return
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
