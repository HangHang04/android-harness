from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from android_harness.config import load_config
from android_harness.errors import HarnessError


class ConfigTests(unittest.TestCase):
    def test_loads_aliases_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "default_serial": "ABC",
                        "app_aliases": {"Weather": "com.example.weather"},
                        "command_timeout": 20,
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(path)
        self.assertEqual("ABC", config.default_serial)
        self.assertEqual("com.example.weather", config.resolve_app("weather"))
        self.assertEqual(20.0, config.command_timeout)

    def test_rejects_invalid_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"command_timeout": 0}', encoding="utf-8")
            with self.assertRaises(HarnessError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
