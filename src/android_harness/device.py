"""High-level Android device operations built on the ADB boundary."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from .adb import AdbRunner
from .companion import CompanionBridge
from .config import HarnessConfig, load_config
from .errors import DeviceSelectionError, ExitCode, HarnessError, OperationError
from .models import DeviceInfo, UiNode
from .ui import (
    content_labels,
    content_signature,
    jaccard_overlap,
    parse_hierarchy,
    preferred_text_matches,
    visible_labels,
)

_SAFE_ASCII_RE = re.compile(r"^[A-Za-z0-9 _@.+,:/\-]*$")
_SIZE_RE = re.compile(r"(?:Physical|Override) size:\s*(\d+)x(\d+)")
_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")


def select_device(
    runner: AdbRunner,
    *,
    explicit_serial: str | None = None,
    config: HarnessConfig | None = None,
) -> tuple[AdbRunner, DeviceInfo]:
    config = config or load_config()
    requested = (
        explicit_serial
        or os.environ.get("ANDROID_HARNESS_SERIAL")
        or config.default_serial
    )
    devices = runner.devices()
    if requested:
        matches = [device for device in devices if device.serial == requested]
        if not matches:
            raise DeviceSelectionError(
                f"Configured device {requested!r} is not attached.",
                code=ExitCode.NO_DEVICE,
                kind="device_not_found",
                details={"requested": requested, "attached": [d.to_dict() for d in devices]},
            )
        selected = matches[0]
    else:
        if not devices:
            raise DeviceSelectionError(
                "No Android device is attached. Connect by USB or pair wireless debugging first.",
                code=ExitCode.NO_DEVICE,
                kind="no_device",
            )
        if len(devices) > 1:
            raise DeviceSelectionError(
                "Multiple Android devices are attached; pass --serial explicitly.",
                code=ExitCode.MULTIPLE_DEVICES,
                kind="multiple_devices",
                details={"devices": [device.to_dict() for device in devices]},
            )
        selected = devices[0]

    if selected.state == "unauthorized":
        raise DeviceSelectionError(
            "The device has not authorized this computer. Unlock it and approve the RSA prompt.",
            code=ExitCode.UNAUTHORIZED,
            kind="device_unauthorized",
            details={"serial": selected.serial},
        )
    if selected.state != "device":
        raise DeviceSelectionError(
            f"Device {selected.serial} is {selected.state!r}, not online.",
            code=ExitCode.OFFLINE,
            kind="device_offline",
            details={"serial": selected.serial, "state": selected.state},
        )
    return runner.with_serial(selected.serial), selected


def create_device(
    *,
    serial: str | None = None,
    adb_path: str | Path | None = None,
    config: HarnessConfig | None = None,
) -> "AndroidDevice":
    config = config or load_config()
    runner = AdbRunner(adb_path, timeout=config.command_timeout)
    selected_runner, info = select_device(runner, explicit_serial=serial, config=config)
    return AndroidDevice(selected_runner, info=info, config=config)


class AndroidDevice:
    def __init__(
        self,
        runner: AdbRunner,
        *,
        info: DeviceInfo,
        config: HarnessConfig | None = None,
    ) -> None:
        if not runner.serial:
            raise ValueError("AndroidDevice requires a serial-bound AdbRunner")
        self.runner = runner
        self.info = info
        self.config = config or HarnessConfig()
        self.companion = CompanionBridge(runner)

    @property
    def serial(self) -> str:
        return self.info.serial

    def shell_text(self, args: list[str], *, check: bool = True) -> str:
        result = self.runner.run(["shell", *args], check=check)
        assert isinstance(result.stdout, str)
        return result.stdout.strip()

    def getprop(self, name: str) -> str:
        return self.shell_text(["getprop", name])

    def sdk_level(self) -> int:
        raw = self.getprop("ro.build.version.sdk")
        try:
            return int(raw)
        except ValueError as exc:
            raise OperationError("Device returned an invalid SDK level", details={"value": raw}) from exc

    def is_locked(self) -> bool:
        output = self.shell_text(["dumpsys", "window", "policy"], check=False)
        locked_markers = (
            "isStatusBarKeyguard=true",
            "mShowingLockscreen=true",
            "keyguardShowing=true",
            "showing=true, occluded=false",
        )
        return any(marker.casefold() in output.casefold() for marker in locked_markers)

    def ensure_ready(self, *, require_unlocked: bool = True) -> None:
        sdk = self.sdk_level()
        if sdk < 30:
            raise HarnessError(
                f"Android {sdk} is below the supported API level 30.",
                code=ExitCode.UNSUPPORTED,
                kind="unsupported_android",
                details={"sdk": sdk, "minimum": 30},
            )
        if require_unlocked and self.is_locked():
            raise HarnessError(
                "The device is locked. Unlock it yourself, then retry.",
                code=ExitCode.LOCKED,
                kind="device_locked",
            )

    def screen_size(self) -> tuple[int, int]:
        output = self.shell_text(["wm", "size"])
        matches = _SIZE_RE.findall(output)
        if matches:
            width, height = matches[-1]
            return int(width), int(height)
        data = self.capture_bytes()
        return png_size(data)

    def capture_bytes(self) -> bytes:
        result = self.runner.run(["exec-out", "screencap", "-p"], binary=True)
        assert isinstance(result.stdout, bytes)
        if not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
            raise OperationError(
                "Device screenshot was empty or not a PNG. A secure/DRM surface may be visible.",
                details={"bytes": len(result.stdout), "stderr": result.stderr[-300:]},
            )
        png_size(result.stdout)
        return result.stdout

    def screenshot(self, output: str | Path | None = None) -> Path:
        data = self.capture_bytes()
        if output is None:
            safe_serial = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.serial)
            target_dir = Path(tempfile.gettempdir()) / "android-harness"
            target_dir.mkdir(parents=True, exist_ok=True)
            output_path = target_dir / f"screenshot-{safe_serial}.png"
        else:
            output_path = Path(output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return output_path

    def dump_ui_xml(self) -> str:
        remote = f"/data/local/tmp/android-harness-{os.getpid()}-{time.time_ns()}.xml"
        try:
            dumped = self.runner.run(
                ["shell", "uiautomator", "dump", "--compressed", remote], check=False
            )
            if dumped.returncode != 0:
                raise OperationError(
                    "UI Automator could not inspect the current screen.",
                    details={"stderr": dumped.stderr[-500:]},
                )
            result = self.runner.run(["exec-out", "cat", remote], binary=True, check=False)
            if result.returncode != 0 or not isinstance(result.stdout, bytes):
                raise OperationError("Could not read the UI hierarchy from the device.")
            xml_text = result.stdout.decode("utf-8", errors="replace").strip()
            if not xml_text.startswith("<?xml") and not xml_text.startswith("<hierarchy"):
                raise OperationError(
                    "UI hierarchy was empty or malformed.", details={"preview": xml_text[:300]}
                )
            return xml_text
        finally:
            self.runner.run(["shell", "rm", "-f", remote], check=False)

    def ui_nodes(self) -> list[UiNode]:
        return parse_hierarchy(self.dump_ui_xml())

    def screen_info(self) -> dict[str, Any]:
        width, height = self.screen_size()
        return {
            "serial": self.serial,
            "state": self.info.state,
            "model": self.getprop("ro.product.model"),
            "manufacturer": self.getprop("ro.product.manufacturer"),
            "sdk": self.sdk_level(),
            "locked": self.is_locked(),
            "size_px": [width, height],
        }

    def tap(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise OperationError("Tap coordinates must be non-negative")
        self.runner.run(["shell", "input", "tap", str(int(x)), str(int(y))])

    def long_press(self, x: int, y: int, duration_ms: int = 800) -> None:
        if duration_ms < 300:
            raise OperationError("Long press duration must be at least 300 ms")
        self.runner.run(
            [
                "shell",
                "input",
                "swipe",
                str(int(x)),
                str(int(y)),
                str(int(x)),
                str(int(y)),
                str(int(duration_ms)),
            ]
        )

    def swipe(self, direction: str, distance: float = 0.55, duration_ms: int = 220) -> None:
        if direction not in {"up", "down", "left", "right"}:
            raise OperationError(f"Unknown swipe direction: {direction!r}")
        if not 0.1 <= distance <= 0.9:
            raise OperationError("Swipe distance must be between 0.1 and 0.9")
        width, height = self.screen_size()
        cx, cy = width // 2, height // 2
        dx = int(width * distance / 2) if direction in {"left", "right"} else 0
        dy = int(height * distance / 2) if direction in {"up", "down"} else 0
        start_x, end_x = cx, cx
        start_y, end_y = cy, cy
        if direction == "up":
            start_y, end_y = cy + dy, cy - dy
        elif direction == "down":
            start_y, end_y = cy - dy, cy + dy
        elif direction == "left":
            start_x, end_x = cx + dx, cx - dx
        else:
            start_x, end_x = cx - dx, cx + dx
        self.runner.run(
            [
                "shell",
                "input",
                "swipe",
                str(start_x),
                str(start_y),
                str(end_x),
                str(end_y),
                str(duration_ms),
            ]
        )

    def press(self, key: str) -> None:
        keycodes = {
            "home": "KEYCODE_HOME",
            "back": "KEYCODE_BACK",
            "recents": "KEYCODE_APP_SWITCH",
            "enter": "KEYCODE_ENTER",
            "return": "KEYCODE_ENTER",
            "tab": "KEYCODE_TAB",
            "delete": "KEYCODE_DEL",
            "escape": "KEYCODE_ESCAPE",
            "up": "KEYCODE_DPAD_UP",
            "down": "KEYCODE_DPAD_DOWN",
            "left": "KEYCODE_DPAD_LEFT",
            "right": "KEYCODE_DPAD_RIGHT",
        }
        keycode = keycodes.get(key.casefold())
        if not keycode:
            raise OperationError(f"Unsupported key: {key!r}")
        self.runner.run(["shell", "input", "keyevent", keycode])

    def type_text(self, text: str) -> dict[str, str]:
        if not text:
            return {"method": "none"}
        status = self.companion.status()
        if status.installed and status.enabled:
            self.companion.commit_text(text)
            return {"method": "companion-ime"}
        if not text.isascii() or not _SAFE_ASCII_RE.fullmatch(text):
            raise HarnessError(
                "This text needs the optional companion IME. The ADB-only fallback supports "
                "letters, numbers, spaces, and a small safe punctuation set.",
                code=ExitCode.CAPABILITY,
                kind="unicode_input_unavailable",
            )
        encoded = text.replace("%", "%25").replace(" ", "%s")
        self.runner.run(["shell", "input", "text", encoded])
        return {"method": "adb-input-text"}

    def tap_text(
        self,
        query: str,
        *,
        index: int | None = None,
        exact: bool = False,
        wait: bool = True,
    ) -> dict[str, Any]:
        if not query.strip():
            raise OperationError("Text query must not be empty")
        nodes = self.ui_nodes()
        if exact:
            from .ui import find_nodes

            matches = find_nodes(nodes, query, exact=True)
            match_type = "exact"
        else:
            matches, match_type = preferred_text_matches(nodes, query)
        if not matches:
            raise OperationError(
                f"No visible text matches {query!r}.",
                details={"visible": visible_labels(nodes)},
            )
        if index is None and len(matches) > 1:
            raise OperationError(
                f"Text {query!r} is ambiguous; pass an explicit index.",
                details={"match_type": match_type, "matches": [n.to_dict() for n in matches]},
            )
        selected_index = index if index is not None else 0
        if not 0 <= selected_index < len(matches):
            raise OperationError(
                "Text match index is out of range",
                details={"index": selected_index, "count": len(matches)},
            )
        node = matches[selected_index]
        self.tap(*node.center)
        stable = self.wait_stable() if wait else None
        return {"node": node.to_dict(), "match_type": match_type, "stable": stable}

    def wait_stable(
        self,
        *,
        timeout: float = 6.0,
        interval: float = 0.45,
        settle_samples: int = 2,
    ) -> bool:
        if settle_samples < 2:
            raise ValueError("settle_samples must be at least 2")
        _, height = self.screen_size()
        previous: str | None = None
        same = 0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                nodes = self.ui_nodes()
                if not nodes:
                    raise OperationError("UI hierarchy is empty")
                signature = content_signature(nodes, height)
            except HarnessError:
                signature = hashlib.sha256(self.capture_bytes()).hexdigest()
            if signature == previous:
                same += 1
                if same >= settle_samples - 1:
                    return True
            else:
                same = 0
            previous = signature
            time.sleep(interval)
        return False

    def scroll_screen(
        self,
        direction: str = "up",
        *,
        distance: float = 0.6,
        moved_threshold: float = 0.75,
    ) -> dict[str, Any]:
        if direction not in {"up", "down"}:
            raise OperationError("Scrolling supports only 'up' and 'down'")
        _, height = self.screen_size()
        before_nodes = self.ui_nodes()
        before = content_labels(before_nodes, height)
        self.swipe(direction, distance=distance)
        stable = self.wait_stable()
        after_nodes = self.ui_nodes()
        after = content_labels(after_nodes, height)
        overlap = jaccard_overlap(before, after)
        return {
            "moved": overlap < moved_threshold,
            "overlap": round(overlap, 3),
            "stable": stable,
            "nodes": [node.to_dict() for node in after_nodes],
        }

    def list_packages(self, *, third_party: bool = False) -> list[str]:
        args = ["pm", "list", "packages"]
        if third_party:
            args.append("-3")
        output = self.shell_text(args)
        return sorted(
            line.removeprefix("package:").strip()
            for line in output.splitlines()
            if line.startswith("package:")
        )

    def open_app(self, package_or_alias: str, *, wait: bool = True) -> dict[str, Any]:
        package = self.config.resolve_app(package_or_alias)
        if not _PACKAGE_RE.fullmatch(package):
            raise OperationError(
                "open_app requires an Android package name or a configured alias.",
                details={"value": package_or_alias},
            )
        resolved = self.shell_text(
            [
                "cmd",
                "package",
                "resolve-activity",
                "--brief",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LAUNCHER",
                "-p",
                package,
            ],
            check=False,
        )
        component = next(
            (line.strip() for line in reversed(resolved.splitlines()) if "/" in line), None
        )
        if not component:
            raise OperationError(
                f"No launchable activity was found for {package!r}.",
                details={"resolver_output": resolved[-500:]},
            )
        result = self.runner.run(["shell", "am", "start", "-n", component])
        output = result.stdout if isinstance(result.stdout, str) else ""
        if "Error:" in output:
            raise OperationError("Android could not launch the app", details={"output": output})
        stable = self.wait_stable(timeout=10.0) if wait else None
        return {"package": package, "component": component, "stable": stable}


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise OperationError("Invalid PNG data")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise OperationError("PNG reported invalid dimensions")
    return width, height
