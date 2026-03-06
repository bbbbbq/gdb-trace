from __future__ import annotations

import builtins
import sys
from pathlib import Path

import gdb


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SENTINEL = "_gdbtrace_gdb_init_installed"


def _ensure_repo_on_sys_path() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


class GdbTraceRunCommand(gdb.Command):
    """Run gdbtrace capture agent using GDBTRACE_GDB_* environment variables."""

    def __init__(self) -> None:
        super().__init__("gdbtrace-run", gdb.COMMAND_USER)

    def invoke(self, arg: str, from_tty: bool) -> None:
        del arg, from_tty
        _ensure_repo_on_sys_path()
        from gdbtrace.gdb_agent import run

        run()


def install() -> None:
    _ensure_repo_on_sys_path()
    if getattr(builtins, INSTALL_SENTINEL, False):
        return
    GdbTraceRunCommand()
    setattr(builtins, INSTALL_SENTINEL, True)


install()
