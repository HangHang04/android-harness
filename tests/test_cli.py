from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO

from android_harness.cli import _emit, build_parser


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



if __name__ == "__main__":
    unittest.main()
