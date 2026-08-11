from __future__ import annotations

import unittest

from android_harness.companion import CompanionBridge, IME_ID
from android_harness.errors import OperationError
from android_harness.models import CommandResult


class FakeRunner:
    def __init__(
        self,
        *,
        broadcast_ok: bool = True,
        previous: str = "com.example/.Ime",
        restore_ok: bool = True,
    ) -> None:
        self.broadcast_ok = broadcast_ok
        self.previous = previous
        self.restore_ok = restore_ok
        self.current = previous
        self.commands: list[list[str]] = []

    def run(self, args, **kwargs):
        args = list(args)
        self.commands.append(args)
        if args[:4] == ["shell", "pm", "path", "dev.androidharness.companion"]:
            return CommandResult(tuple(args), 0, "package:/data/app/helper.apk\n", "")
        if args[:4] == ["shell", "ime", "list", "-s"]:
            return CommandResult(tuple(args), 0, f"{IME_ID}\n", "")
        if args[:5] == ["shell", "settings", "get", "secure", "default_input_method"]:
            return CommandResult(tuple(args), 0, f"{self.current}\n", "")
        if args[:3] == ["shell", "ime", "set"]:
            if args[3] == self.previous and not self.restore_ok:
                return CommandResult(tuple(args), 1, "", "restore failed")
            self.current = args[3]
            return CommandResult(tuple(args), 0, "Input method selected\n", "")
        if args[:3] == ["shell", "ime", "reset"]:
            self.current = "com.default/.Ime"
            return CommandResult(tuple(args), 0, "Reset current and enabled IMEs\n", "")
        if args[:3] == ["shell", "am", "broadcast"]:
            output = (
                'Broadcast completed: result=-1, data="ok"\n'
                if self.broadcast_ok
                else 'Broadcast completed: result=0, data="no-input-connection"\n'
            )
            return CommandResult(tuple(args), 0, output, "")
        return CommandResult(tuple(args), 0, "", "")


class CompanionTests(unittest.TestCase):
    def test_commits_unicode_and_restores_previous_ime(self) -> None:
        runner = FakeRunner()
        bridge = CompanionBridge(runner)  # type: ignore[arg-type]
        bridge.commit_text("你好 👋")
        self.assertIn(["shell", "ime", "set", IME_ID], runner.commands)
        self.assertIn(["shell", "ime", "set", "com.example/.Ime"], runner.commands)
        self.assertEqual("com.example/.Ime", runner.current)

    def test_restores_previous_ime_when_commit_fails(self) -> None:
        runner = FakeRunner(broadcast_ok=False)
        bridge = CompanionBridge(runner)  # type: ignore[arg-type]
        with self.assertRaises(OperationError):
            bridge.commit_text("失败")
        self.assertIn(["shell", "ime", "set", "com.example/.Ime"], runner.commands)
        self.assertEqual("com.example/.Ime", runner.current)

    def test_resets_ime_when_device_reported_no_previous_value(self) -> None:
        runner = FakeRunner(previous="null")
        bridge = CompanionBridge(runner)  # type: ignore[arg-type]
        bridge.commit_text("text")
        self.assertIn(["shell", "ime", "reset"], runner.commands)
        self.assertEqual("com.default/.Ime", runner.current)

    def test_surfaces_restore_failure(self) -> None:
        runner = FakeRunner(restore_ok=False)
        bridge = CompanionBridge(runner)  # type: ignore[arg-type]
        with self.assertRaisesRegex(OperationError, "could not be restored"):
            bridge.commit_text("text")
        self.assertEqual(IME_ID, runner.current)


if __name__ == "__main__":
    unittest.main()
