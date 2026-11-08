"""Safe subprocess boundary for Android Debug Bridge."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from .errors import AdbNotFoundError, ExitCode, HarnessError
from .models import CommandResult, DeviceInfo


def _adb_filename() -> str:
    return "adb.exe" if os.name == "nt" else "adb"


def adb_candidates() -> list[Path]:
    name = _adb_filename()
    candidates: list[Path] = []
    explicit = os.environ.get("ANDROID_HARNESS_ADB")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    on_path = shutil.which("adb")
    if on_path:
        candidates.append(Path(on_path))
    for env_name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        root = os.environ.get(env_name)
        if root:
            candidates.append(Path(root) / "platform-tools" / name)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / name)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate.resolve(strict=False)))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def find_adb() -> Path:
    for candidate in adb_candidates():
        if candidate.is_file():
            return candidate.resolve()
    checked = [str(path) for path in adb_candidates()]
    raise AdbNotFoundError(
        "ADB was not found. Install Android SDK Platform Tools or set "
        "ANDROID_HARNESS_ADB to adb.exe." + (f" Checked: {checked}" if checked else "")
    )


class AdbRunner:
    def __init__(
        self,
        adb_path: str | Path | None = None,
        *,
        serial: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.adb_path = Path(adb_path).resolve() if adb_path else find_adb()
        self.serial = serial
        self.timeout = timeout

    def with_serial(self, serial: str) -> AdbRunner:
        return AdbRunner(self.adb_path, serial=serial, timeout=self.timeout)

    def run(
        self,
        args: Iterable[str],
        *,
        use_serial: bool = True,
        check: bool = True,
        binary: bool = False,
        input_data: str | bytes | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        arg_list = [str(arg) for arg in args]
        command = [str(self.adb_path)]
        if use_serial and self.serial:
            command.extend(["-s", self.serial])
        command.extend(arg_list)
        kwargs: dict[str, object] = {
            "capture_output": True,
            "timeout": timeout if timeout is not None else self.timeout,
            "check": False,
            "shell": False,
        }
        if binary:
            if isinstance(input_data, str):
                input_data = input_data.encode("utf-8")
            kwargs["input"] = input_data
        else:
            if isinstance(input_data, bytes):
                input_data = input_data.decode("utf-8")
            kwargs.update({"text": True, "encoding": "utf-8", "errors": "replace"})
            kwargs["input"] = input_data
        try:
            process = subprocess.run(command, **kwargs)  # type: ignore[arg-type]
        except subprocess.TimeoutExpired as exc:
            raise HarnessError(
                f"ADB command timed out after {kwargs['timeout']} seconds.",
                code=ExitCode.TIMEOUT,
                kind="adb_timeout",
                details={"operation": arg_list[0] if arg_list else "adb"},
            ) from exc
        except OSError as exc:
            raise AdbNotFoundError(f"Could not execute ADB at {self.adb_path}: {exc}") from exc

        raw_stdout = process.stdout
        raw_stderr = process.stderr
        if binary:
            stdout: str | bytes = bytes(raw_stdout or b"")
            stderr = bytes(raw_stderr or b"").decode("utf-8", errors="replace")
        else:
            stdout = str(raw_stdout or "")
            stderr = str(raw_stderr or "")
        result = CommandResult(tuple(arg_list), process.returncode, stdout, stderr)
        if check and process.returncode != 0:
            message = stderr.strip()
            if not message and isinstance(stdout, str):
                message = stdout.strip()
            raise HarnessError(
                f"ADB command failed ({process.returncode}). Check the device connection.",
                code=ExitCode.OPERATION,
                kind="adb_command_failed",
                details={
                    "operation": arg_list[0] if arg_list else "adb",
                    "returncode": process.returncode,
                },
            )
        return result

    def devices(self) -> list[DeviceInfo]:
        result = self.run(["devices", "-l"], use_serial=False)
        assert isinstance(result.stdout, str)
        return parse_devices(result.stdout)


def parse_devices(output: str) -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    for raw_line in output.replace("\r", "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        attributes: dict[str, str] = {}
        for part in parts[2:]:
            if ":" in part:
                key, value = part.split(":", 1)
                attributes[key] = value
        devices.append(
            DeviceInfo(
                serial=serial,
                state=state,
                product=attributes.get("product"),
                model=attributes.get("model"),
                device=attributes.get("device"),
                transport_id=attributes.get("transport_id"),
                attributes=attributes,
            )
        )
    return devices
