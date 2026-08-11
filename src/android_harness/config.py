"""Small JSON configuration with explicit precedence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ExitCode, HarnessError


@dataclass(slots=True)
class HarnessConfig:
    default_serial: str | None = None
    app_aliases: dict[str, str] = field(default_factory=dict)
    command_timeout: float = 15.0

    def resolve_app(self, value: str) -> str:
        return self.app_aliases.get(value.casefold(), value)


def default_config_path() -> Path:
    override = os.environ.get("ANDROID_HARNESS_CONFIG")
    if override:
        return Path(override).expanduser()
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "android-harness" / "config.json"
    return Path.home() / ".config" / "android-harness" / "config.json"


def _validate_mapping(raw: Any, path: Path) -> HarnessConfig:
    if not isinstance(raw, dict):
        raise HarnessError(
            f"Configuration must be a JSON object: {path}",
            code=ExitCode.CONFIG,
            kind="invalid_config",
        )
    serial = raw.get("default_serial")
    aliases = raw.get("app_aliases", {})
    timeout = raw.get("command_timeout", 15.0)
    if serial is not None and not isinstance(serial, str):
        raise HarnessError(
            "default_serial must be a string",
            code=ExitCode.CONFIG,
            kind="invalid_config",
        )
    if not isinstance(aliases, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()
    ):
        raise HarnessError(
            "app_aliases must map string aliases to Android package names",
            code=ExitCode.CONFIG,
            kind="invalid_config",
        )
    try:
        timeout_value = float(timeout)
    except (TypeError, ValueError) as exc:
        raise HarnessError(
            "command_timeout must be a number",
            code=ExitCode.CONFIG,
            kind="invalid_config",
        ) from exc
    if not 1.0 <= timeout_value <= 300.0:
        raise HarnessError(
            "command_timeout must be between 1 and 300 seconds",
            code=ExitCode.CONFIG,
            kind="invalid_config",
        )
    return HarnessConfig(
        default_serial=serial,
        app_aliases={k.casefold(): v for k, v in aliases.items()},
        command_timeout=timeout_value,
    )


def load_config(path: Path | None = None) -> HarnessConfig:
    path = path or default_config_path()
    if not path.exists():
        return HarnessConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(
            f"Cannot read configuration {path}: {exc}",
            code=ExitCode.CONFIG,
            kind="invalid_config",
        ) from exc
    return _validate_mapping(raw, path)
