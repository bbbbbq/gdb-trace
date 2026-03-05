from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARCH_CHOICES = ("thumb", "thumb2", "arm32", "aarch64")
MODE_CHOICES = ("inst", "call", "both")


class GdbTraceError(RuntimeError):
    """Domain error with a user-facing message."""


@dataclass(frozen=True)
class Paths:
    session_file: Path
    global_config_file: Path
    runtime_file: Path


def resolve_paths() -> Paths:
    cwd = Path.cwd()
    session_override = os.environ.get("GDBTRACE_SESSION_FILE")
    global_override = os.environ.get("GDBTRACE_GLOBAL_CONFIG")
    runtime_override = os.environ.get("GDBTRACE_RUNTIME_FILE")
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Paths(
        session_file=Path(session_override) if session_override else cwd / ".gdbtrace_session.json",
        global_config_file=(
            Path(global_override) if global_override else xdg_config_home / "gdbtrace" / "config.json"
        ),
        runtime_file=Path(runtime_override) if runtime_override else cwd / ".gdbtrace_runtime.json",
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GdbTraceError(f"failed to read state file: {path}") from exc


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def clear_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def validate_target(value: str) -> str:
    host, sep, port_text = value.rpartition(":")
    if not sep or not host:
        raise GdbTraceError("target must be in host:port format")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise GdbTraceError("target port must be an integer") from exc
    if port < 1 or port > 65535:
        raise GdbTraceError("target port must be between 1 and 65535")
    return value


def validate_arch(value: str) -> str:
    if value not in ARCH_CHOICES:
        raise GdbTraceError(f"arch must be one of: {', '.join(ARCH_CHOICES)}")
    return value


def validate_mode(value: str) -> str:
    if value not in MODE_CHOICES:
        raise GdbTraceError(f"mode must be one of: {', '.join(MODE_CHOICES)}")
    return value


def validate_output(value: str) -> str:
    if not value.endswith(".log"):
        raise GdbTraceError("output path must end with .log")
    return value


def session_state(paths: Paths) -> dict[str, Any]:
    return load_json(paths.session_file)


def save_session_state(paths: Paths, payload: dict[str, Any]) -> None:
    save_json(paths.session_file, payload)


def global_state(paths: Paths) -> dict[str, Any]:
    return load_json(paths.global_config_file)


def save_global_state(paths: Paths, payload: dict[str, Any]) -> None:
    save_json(paths.global_config_file, payload)


def runtime_state(paths: Paths) -> dict[str, Any]:
    return load_json(paths.runtime_file)


def save_runtime_state(paths: Paths, payload: dict[str, Any]) -> None:
    save_json(paths.runtime_file, payload)
