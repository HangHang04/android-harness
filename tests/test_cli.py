from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from android_harness.cli import _emit, build_parser, execute, main


class CliTests(unittest.TestCase):
    def test_global_options_and_tap_text(self) -> None:
        args = build_parser().parse_args(
            ["--serial", "ABC", "--json", "tap-text", "Weather", "--index", "1"]
        )
        self.assertEqual("ABC", args.serial)
        self.assertTrue(args.json)
        self.assertEqual("tap-text", args.command)
        self.assertEqual(1, args.index)

    def test_helper_install_requires_explicit_confirm_flag_shape(self) -> None:
        args = build_parser().parse_args(["helper", "install", "helper.apk"])
        self.assertFalse(args.confirm)
        self.assertEqual("install", args.helper_command)

    def test_json_envelope_reflects_non_success_result(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            _emit({"ok": False}, json_mode=True, success=False)
        self.assertIn('"ok": false', output.getvalue())

    def test_skill_install_accepts_an_explicit_destination(self) -> None:
        args = build_parser().parse_args(
            ["--json", "skill", "--install", "--destination", "android-harness"]
        )
        self.assertEqual("skill", args.command)
        self.assertTrue(args.install)
        self.assertEqual("android-harness", args.destination)

    def test_skill_command_does_not_load_device_configuration(self) -> None:
        args = build_parser().parse_args(["skill"])
        with patch(
            "android_harness.cli.load_config",
            side_effect=AssertionError("Skill command must not load device config"),
        ):
            result, code = execute(args)

        self.assertEqual(0, code)
        self.assertIn("name: android-harness", result)

    def test_skill_install_without_json_prints_a_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "android-harness"
            output = StringIO()
            with redirect_stdout(output):
                code = main(["skill", "--install", "--destination", str(destination)])

        self.assertEqual(0, code)
        self.assertEqual("installed", json.loads(output.getvalue())["status"])


if __name__ == "__main__":
    unittest.main()
