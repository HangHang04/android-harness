"""Stable error types and process exit codes."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    OK = 0
    GENERAL = 1
    USAGE = 2
    CONFIG = 10
    ADB_NOT_FOUND = 11
    NO_DEVICE = 12
    MULTIPLE_DEVICES = 13
    UNAUTHORIZED = 14
    OFFLINE = 15
    UNSUPPORTED = 16
    LOCKED = 17
    CAPABILITY = 18
    OPERATION = 19
    TIMEOUT = 20


class HarnessError(RuntimeError):
    """Expected failure that can be reported cleanly to an agent or user."""

    def __init__(
        self,
        message: str,
        *,
        code: ExitCode = ExitCode.GENERAL,
        kind: str = "harness_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.kind = kind
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "kind": self.kind,
                "message": self.message,
                "exit_code": int(self.code),
                "details": self.details,
            },
        }


class AdbNotFoundError(HarnessError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ExitCode.ADB_NOT_FOUND, kind="adb_not_found")


class DeviceSelectionError(HarnessError):
    pass


class CapabilityError(HarnessError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code=ExitCode.CAPABILITY,
            kind="capability_unavailable",
            details=details,
        )


class OperationError(HarnessError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code=ExitCode.OPERATION,
            kind="operation_failed",
            details=details,
        )
