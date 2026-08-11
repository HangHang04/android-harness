"""Read-only diagnostic ladder for host, ADB, device, capture, and UI access."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .adb import AdbRunner, find_adb
from .config import HarnessConfig, load_config
from .device import AndroidDevice, select_device
from .errors import HarnessError
from .models import DoctorCheck


def run_doctor(
    *,
    serial: str | None = None,
    adb_path: str | Path | None = None,
    config: HarnessConfig | None = None,
) -> dict[str, Any]:
    checks: list[DoctorCheck] = []
    checks.append(
        DoctorCheck(
            "python",
            sys.version_info >= (3, 11),
            detail=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )
    config = config or load_config()
    try:
        resolved_adb = Path(adb_path).resolve() if adb_path else find_adb()
        runner = AdbRunner(resolved_adb, timeout=config.command_timeout)
        version_result = runner.run(["version"], use_serial=False)
        version = version_result.stdout if isinstance(version_result.stdout, str) else ""
        checks.append(DoctorCheck("adb", True, detail=version.splitlines()[0] if version else str(resolved_adb)))
    except HarnessError as exc:
        checks.append(DoctorCheck("adb", False, detail=exc.message))
        return _report(checks, serial=None)

    devices = runner.devices()
    checks.append(
        DoctorCheck(
            "attached-device",
            bool(devices),
            detail=", ".join(f"{d.serial} ({d.state})" for d in devices) or "none",
        )
    )
    try:
        selected_runner, info = select_device(
            runner, explicit_serial=serial, config=config
        )
    except HarnessError as exc:
        checks.append(DoctorCheck("device-selection", False, detail=exc.message))
        return _report(checks, serial=None)

    device = AndroidDevice(selected_runner, info=info, config=config)
    checks.append(DoctorCheck("device-online", True, detail=info.serial))
    try:
        sdk = device.sdk_level()
        checks.append(DoctorCheck("android-api", sdk >= 30, detail=f"API {sdk}; minimum 30"))
    except HarnessError as exc:
        checks.append(DoctorCheck("android-api", False, detail=exc.message))

    try:
        locked = device.is_locked()
        checks.append(
            DoctorCheck(
                "device-unlocked",
                not locked,
                detail="unlock the device yourself" if locked else "unlocked",
            )
        )
    except HarnessError as exc:
        checks.append(DoctorCheck("device-unlocked", False, detail=exc.message))

    try:
        screenshot = device.capture_bytes()
        checks.append(DoctorCheck("screenshot", True, detail=f"{len(screenshot)} bytes"))
    except HarnessError as exc:
        checks.append(DoctorCheck("screenshot", False, detail=exc.message))

    try:
        nodes = device.ui_nodes()
        checks.append(DoctorCheck("ui-hierarchy", bool(nodes), detail=f"{len(nodes)} nodes"))
    except HarnessError as exc:
        checks.append(DoctorCheck("ui-hierarchy", False, detail=exc.message))

    try:
        companion = device.companion.status()
        checks.append(
            DoctorCheck(
                "unicode-companion",
                companion.installed and companion.enabled,
                required=False,
                detail=(
                    "installed and enabled"
                    if companion.installed and companion.enabled
                    else "optional; not installed or not enabled"
                ),
            )
        )
    except HarnessError as exc:
        checks.append(DoctorCheck("unicode-companion", False, required=False, detail=exc.message))

    return _report(checks, serial=info.serial)


def _report(checks: list[DoctorCheck], serial: str | None) -> dict[str, Any]:
    ok = all(check.ok for check in checks if check.required)
    return {"ok": ok, "serial": serial, "checks": [check.to_dict() for check in checks]}
