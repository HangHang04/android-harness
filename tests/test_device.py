from __future__ import annotations

import unittest

from android_harness.config import HarnessConfig
from android_harness.device import AndroidDevice, png_size, select_device
from android_harness.errors import HarnessError, OperationError
from android_harness.models import Bounds, CommandResult, DeviceInfo, UiNode


class FakeRunner:
    def __init__(self, devices: list[DeviceInfo] | None = None, serial: str | None = None) -> None:
        self._devices = devices or []
        self.serial = serial
        self.commands: list[list[str]] = []

    def devices(self) -> list[DeviceInfo]:
        return self._devices

    def with_serial(self, serial: str) -> "FakeRunner":
        child = FakeRunner(self._devices, serial)
        child.commands = self.commands
        return child

    def run(self, args, **kwargs):
        args = list(args)
        self.commands.append(args)
        if args[:4] == ["shell", "pm", "path", "dev.androidharness.companion"]:
            return CommandResult(tuple(args), 1, "", "")
        if args[:4] == ["shell", "ime", "list", "-s"]:
            return CommandResult(tuple(args), 0, "", "")
        if args[:5] == ["shell", "settings", "get", "secure", "default_input_method"]:
            return CommandResult(tuple(args), 0, "com.example/.Ime\n", "")
        return CommandResult(tuple(args), 0, "", "")


def node(text: str, top: int, *, content_desc: str = "") -> UiNode:
    return UiNode(
        text=text,
        content_desc=content_desc,
        resource_id="",
        class_name="android.widget.TextView",
        package="com.example",
        bounds=Bounds(10, top, 110, top + 50),
        clickable=True,
        enabled=True,
        scrollable=False,
        selected=False,
        focused=False,
        index=0,
    )


class StubDevice(AndroidDevice):
    def __init__(self, nodes: list[UiNode]) -> None:
        runner = FakeRunner(serial="ABC")
        super().__init__(
            runner,  # type: ignore[arg-type]
            info=DeviceInfo("ABC", "device"),
            config=HarnessConfig(),
        )
        self._nodes = nodes
        self.taps: list[tuple[int, int]] = []

    def ui_nodes(self) -> list[UiNode]:
        return self._nodes

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))

    def wait_stable(self, **kwargs) -> bool:
        return True


class DeviceTests(unittest.TestCase):
    def test_selects_only_online_device(self) -> None:
        runner = FakeRunner([DeviceInfo("ABC", "device")])
        selected, info = select_device(runner, config=HarnessConfig())  # type: ignore[arg-type]
        self.assertEqual("ABC", selected.serial)
        self.assertEqual("ABC", info.serial)

    def test_rejects_multiple_devices_without_serial(self) -> None:
        runner = FakeRunner([DeviceInfo("A", "device"), DeviceInfo("B", "device")])
        with self.assertRaises(HarnessError):
            select_device(runner, config=HarnessConfig())  # type: ignore[arg-type]

    def test_tap_text_taps_unique_exact_match(self) -> None:
        device = StubDevice([node("Weather", 100), node("Weather report", 200)])
        result = device.tap_text("Weather")
        self.assertEqual([(60, 125)], device.taps)
        self.assertEqual("exact", result["match_type"])

    def test_tap_text_requires_index_for_ambiguous_matches(self) -> None:
        device = StubDevice([node("Weather", 100), node("", 200, content_desc="Weather")])
        with self.assertRaises(OperationError):
            device.tap_text("Weather")

    def test_ascii_fallback_encodes_spaces(self) -> None:
        device = StubDevice([])
        result = device.type_text("hello world")
        self.assertEqual("adb-input-text", result["method"])
        self.assertIn(
            ["shell", "input", "text", "hello%sworld"],
            device.runner.commands,  # type: ignore[attr-defined]
        )

    def test_unicode_requires_companion(self) -> None:
        device = StubDevice([])
        with self.assertRaises(HarnessError):
            device.type_text("你好")

    def test_png_size(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (1080).to_bytes(4, "big") + (2400).to_bytes(4, "big")
        self.assertEqual((1080, 2400), png_size(data))


if __name__ == "__main__":
    unittest.main()
