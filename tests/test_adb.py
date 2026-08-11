from __future__ import annotations

import unittest

from android_harness.adb import parse_devices


class ParseDevicesTests(unittest.TestCase):
    def test_parses_online_and_unauthorized_devices(self) -> None:
        output = """List of devices attached
ABC123\tdevice product:panther model:Pixel_7 device:panther transport_id:1
10.0.0.8:5555\tunauthorized transport_id:2

"""
        devices = parse_devices(output)
        self.assertEqual(2, len(devices))
        self.assertEqual("ABC123", devices[0].serial)
        self.assertEqual("Pixel_7", devices[0].model)
        self.assertEqual("unauthorized", devices[1].state)

    def test_ignores_daemon_noise(self) -> None:
        output = """* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached

"""
        self.assertEqual([], parse_devices(output))


if __name__ == "__main__":
    unittest.main()
