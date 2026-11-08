"""Optional companion IME bridge for reliable Unicode input."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from .adb import AdbRunner
from .errors import CapabilityError, OperationError

PACKAGE = "dev.androidharness.companion"
IME_ID = f"{PACKAGE}/.HarnessImeService"
RECEIVER = f"{PACKAGE}/.CommitTextReceiver"
ACTION_COMMIT_TEXT = "dev.androidharness.action.COMMIT_TEXT"


@dataclass(frozen=True, slots=True)
class CompanionStatus:
    installed: bool
    enabled: bool
    current: bool
    current_ime: str

    def to_dict(self) -> dict[str, object]:
        return {
            "package": PACKAGE,
            "ime_id": IME_ID,
            "installed": self.installed,
            "enabled": self.enabled,
            "current": self.current,
            "current_ime": self.current_ime,
        }


class CompanionBridge:
    def __init__(self, runner: AdbRunner) -> None:
        self.runner = runner

    def status(self) -> CompanionStatus:
        package = self.runner.run(["shell", "pm", "path", PACKAGE], check=False)
        enabled_result = self.runner.run(["shell", "ime", "list", "-s"], check=False)
        current_result = self.runner.run(
            ["shell", "settings", "get", "secure", "default_input_method"], check=False
        )
        package_text = package.stdout if isinstance(package.stdout, str) else ""
        enabled_text = enabled_result.stdout if isinstance(enabled_result.stdout, str) else ""
        current_text = current_result.stdout if isinstance(current_result.stdout, str) else ""
        current_ime = current_text.strip()
        return CompanionStatus(
            installed=package.returncode == 0 and "package:" in package_text,
            enabled=IME_ID in {line.strip() for line in enabled_text.splitlines()},
            current=current_ime == IME_ID,
            current_ime=current_ime,
        )

    def _current_ime(self) -> str:
        result = self.runner.run(
            ["shell", "settings", "get", "secure", "default_input_method"],
            check=False,
        )
        output = result.stdout if isinstance(result.stdout, str) else ""
        return output.strip()

    def install(self, apk: Path) -> None:
        if not apk.is_file():
            raise OperationError("Companion APK does not exist", details={"path": str(apk)})
        self.runner.run(["install", "-r", str(apk)])

    def enable(self) -> None:
        status = self.status()
        if not status.installed:
            raise CapabilityError("Companion APK is not installed")
        self.runner.run(["shell", "ime", "enable", IME_ID])

    def disable(self) -> None:
        status = self.status()
        if status.current:
            raise OperationError(
                "Companion IME is currently selected. Select another keyboard before disabling it."
            )
        self.runner.run(["shell", "ime", "disable", IME_ID])

    def commit_text(self, text: str) -> None:
        status = self.status()
        if not status.installed:
            raise CapabilityError(
                "Unicode input needs the optional companion APK; it is not installed."
            )
        if not status.enabled:
            raise CapabilityError(
                "The companion IME is installed but not enabled. Ask the user to enable it first."
            )

        previous = status.current_ime
        changed = previous != IME_ID
        if changed:
            self.runner.run(["shell", "ime", "set", IME_ID])
        encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")
        try:
            result = self.runner.run(
                [
                    "shell",
                    "am",
                    "broadcast",
                    "-a",
                    ACTION_COMMIT_TEXT,
                    "-n",
                    RECEIVER,
                    "--es",
                    "text_b64",
                    encoded,
                ],
                check=False,
            )
            output = "\n".join(
                part
                for part in (
                    result.stdout if isinstance(result.stdout, str) else "",
                    result.stderr,
                )
                if part
            )
            if result.returncode != 0 or "result=-1" not in output:
                raise OperationError(
                    "Companion IME did not accept the text. Ensure a text field is focused.",
                    details={"returncode": result.returncode},
                )
        finally:
            if changed and previous and previous != "null":
                restore = self.runner.run(["shell", "ime", "set", previous], check=False)
                if restore.returncode != 0 or self._current_ime() != previous:
                    raise OperationError(
                        "The previous input method could not be restored. Ask the user to "
                        "select their keyboard in Android settings.",
                        details={"expected_ime": previous},
                    )
            elif changed:
                restore = self.runner.run(["shell", "ime", "reset"], check=False)
                if restore.returncode != 0 or self._current_ime() == IME_ID:
                    raise OperationError(
                        "The default input method could not be restored. Ask the user to "
                        "select their keyboard in Android settings."
                    )
