"""Command-line interface for Android Harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adb import AdbRunner
from .config import load_config
from .device import create_device
from .doctor import run_doctor
from .errors import ExitCode, HarnessError
from .skill_bundle import install_skill, skill_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="android-harness",
        description="Control a real Android phone over ADB with an agent-friendly interface.",
    )
    parser.add_argument("--serial", help="ADB device serial; required when multiple devices attach")
    parser.add_argument("--adb", help="Explicit path to adb.exe")
    parser.add_argument("--json", action="store_true", help="Emit a stable JSON envelope")
    sub = parser.add_subparsers(dest="command", required=True)

    console = sub.add_parser("console", help="Open the local control console")
    console.add_argument("--port", type=int, default=0)
    console.add_argument("--no-open", action="store_true")
    for name in ("capabilities", "observe", "find", "tap-element", "wait-for", "batch", "open-url"):
        command = sub.add_parser(name, help="Structured device operation")
        command.add_argument("--stdin", action="store_true", help="Read JSON arguments from stdin")
        command.add_argument("--screenshot", action="store_true")
    files_parser = sub.add_parser("files", help="Transfer a file under an approved task")
    files_sub = files_parser.add_subparsers(dest="direction", required=True)
    for direction in ("push", "pull"):
        transfer_parser = files_sub.add_parser(direction)
        transfer_parser.add_argument("--task", required=True)
        transfer_parser.add_argument("--stdin", action="store_true", required=True)
    task = sub.add_parser("task", help="Request and use a console-approved task")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_sub.add_parser("list")
    task_sub.add_parser("request").add_argument("--stdin", action="store_true", required=True)
    for name in ("stop", "complete"):
        task_sub.add_parser(name).add_argument("task_id")
    task_action = task_sub.add_parser("action")
    task_action.add_argument("task_id")
    task_action.add_argument("action")
    task_action.add_argument("--stdin", action="store_true")

    sub.add_parser("devices", help="List attached ADB devices")
    sub.add_parser("doctor", help="Run read-only setup and device diagnostics")
    sub.add_parser("screen-info", help="Describe the selected device and display")

    screenshot = sub.add_parser("screenshot", help="Capture the device screen as PNG")
    screenshot.add_argument("-o", "--output", help="Output path; defaults to a stable temp file")
    sub.add_parser("ui", help="Dump the visible UI hierarchy")

    tap = sub.add_parser("tap", help="Tap device pixel coordinates")
    tap.add_argument("x", type=int)
    tap.add_argument("y", type=int)
    tap.add_argument("--no-wait", action="store_true")

    tap_text = sub.add_parser("tap-text", help="Find visible text/content description and tap it")
    tap_text.add_argument("query")
    tap_text.add_argument("--index", type=int)
    tap_text.add_argument("--exact", action="store_true")
    tap_text.add_argument("--no-wait", action="store_true")

    long_press = sub.add_parser("long-press", help="Long-press device pixel coordinates")
    long_press.add_argument("x", type=int)
    long_press.add_argument("y", type=int)
    long_press.add_argument("--duration-ms", type=int, default=800)
    long_press.add_argument("--no-wait", action="store_true")

    swipe = sub.add_parser("swipe", help="Swipe in a cardinal direction")
    swipe.add_argument("direction", choices=("up", "down", "left", "right"))
    swipe.add_argument("--distance", type=float, default=0.55)
    swipe.add_argument("--duration-ms", type=int, default=220)
    swipe.add_argument("--no-wait", action="store_true")

    scroll = sub.add_parser("scroll", help="Scroll and report whether content moved")
    scroll.add_argument("direction", choices=("up", "down"), nargs="?", default="up")
    scroll.add_argument("--distance", type=float, default=0.6)

    key = sub.add_parser("key", help="Press a named Android key")
    key.add_argument("key")
    key.add_argument("--no-wait", action="store_true")

    type_parser = sub.add_parser("type", help="Type UTF-8 text read from stdin")
    type_parser.add_argument("--stdin", action="store_true", required=True)
    type_parser.add_argument("--no-wait", action="store_true")

    apps = sub.add_parser("apps", help="List installed package names")
    apps.add_argument("--third-party", action="store_true")

    open_app = sub.add_parser("open-app", help="Open a package name or configured alias")
    open_app.add_argument("package_or_alias")
    open_app.add_argument("--no-wait", action="store_true")

    stable = sub.add_parser("wait-stable", help="Wait until the visible UI stops changing")
    stable.add_argument("--timeout", type=float, default=6.0)

    run = sub.add_parser("run", help="Execute an explicit Python workflow file with helpers")
    run.add_argument("file")

    helper = sub.add_parser("helper", help="Manage the optional Unicode companion IME")
    helper_sub = helper.add_subparsers(dest="helper_command", required=True)
    helper_sub.add_parser("status")
    install = helper_sub.add_parser("install")
    install.add_argument("apk")
    install.add_argument("--confirm", action="store_true")
    enable = helper_sub.add_parser("enable")
    enable.add_argument("--confirm", action="store_true")
    disable = helper_sub.add_parser("disable")
    disable.add_argument("--confirm", action="store_true")

    skill = sub.add_parser("skill", help="Print or install the bundled Codex Skill")
    skill.add_argument("--install", action="store_true", help="Install the complete Skill")
    skill.add_argument("--destination", help="Alternate android-harness Skill directory")
    return parser


def _emit(value: Any, *, json_mode: bool, success: bool = True) -> None:
    if json_mode:
        print(json.dumps({"ok": success, "result": value}, ensure_ascii=False, indent=2))
    elif isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def _configure_console_stream(stream: Any) -> None:
    """Keep Windows console encoding gaps from aborting structured output."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="backslashreplace")


def _require_confirmation(args: argparse.Namespace, action: str) -> None:
    if not getattr(args, "confirm", False):
        raise HarnessError(
            f"{action} changes software or input-method settings on the phone. "
            "Ask the user, then repeat with --confirm.",
            code=ExitCode.USAGE,
            kind="confirmation_required",
        )


def execute(args: argparse.Namespace) -> tuple[Any, int]:
    if args.command == "files":
        from .console import agent_call

        return agent_call(
            "/api/action",
            {"task_id": args.task, "action": args.direction, "args": json.loads(sys.stdin.read())},
        ), ExitCode.OK
    if args.command == "console":
        from .console import serve

        serve(args.port, not args.no_open)
        return {"stopped": True}, ExitCode.OK
    if args.command == "task":
        from .console import agent_call

        if args.task_command == "list":
            return agent_call("/api/tasks"), ExitCode.OK
        if args.task_command == "request":
            return agent_call("/api/tasks", json.loads(sys.stdin.read())), ExitCode.OK
        payload = {"task_id": args.task_id}
        if args.task_command == "action":
            payload.update(
                action=args.action, args=json.loads(sys.stdin.read()) if args.stdin else {}
            )
            return agent_call("/api/action", payload), ExitCode.OK
        return agent_call("/api/" + args.task_command, payload), ExitCode.OK
    if args.command == "skill":
        if args.destination and not args.install:
            raise HarnessError(
                "--destination requires --install.",
                code=ExitCode.USAGE,
                kind="invalid_skill_arguments",
            )
        if args.install:
            return install_skill(args.destination), ExitCode.OK
        return skill_text(), ExitCode.OK

    config = load_config()
    if args.command == "devices":
        runner = AdbRunner(args.adb, timeout=config.command_timeout)
        return [device.to_dict() for device in runner.devices()], ExitCode.OK
    if args.command == "doctor":
        report = run_doctor(serial=args.serial, adb_path=args.adb, config=config)
        return report, ExitCode.OK if report["ok"] else ExitCode.GENERAL

    device = create_device(serial=args.serial, adb_path=args.adb, config=config)
    if args.command != "helper":
        device.ensure_ready()

    if args.command in {
        "capabilities",
        "observe",
        "find",
        "tap-element",
        "wait-for",
        "batch",
        "open-url",
    }:
        from .actions import execute_action

        payload = json.loads(sys.stdin.read()) if args.stdin else {}
        if args.screenshot:
            payload["screenshot"] = True
        if args.command == "batch":
            raise HarnessError(
                "Batch execution requires an approved task; use task action ID batch --stdin."
            )
        return execute_action(device, args.command, payload), ExitCode.OK
    if args.command == "screen-info":
        return device.screen_info(), ExitCode.OK
    if args.command == "screenshot":
        return {"path": str(device.screenshot(args.output))}, ExitCode.OK
    if args.command == "ui":
        return [node.to_dict() for node in device.ui_nodes()], ExitCode.OK
    if args.command == "tap":
        device.tap(args.x, args.y)
        stable = device.wait_stable() if not args.no_wait else None
        return {"x": args.x, "y": args.y, "stable": stable}, ExitCode.OK
    if args.command == "tap-text":
        return (
            device.tap_text(
                args.query,
                index=args.index,
                exact=args.exact,
                wait=not args.no_wait,
            ),
            ExitCode.OK,
        )
    if args.command == "long-press":
        device.long_press(args.x, args.y, args.duration_ms)
        stable = device.wait_stable() if not args.no_wait else None
        return {"x": args.x, "y": args.y, "stable": stable}, ExitCode.OK
    if args.command == "swipe":
        device.swipe(args.direction, args.distance, args.duration_ms)
        stable = device.wait_stable() if not args.no_wait else None
        return {"direction": args.direction, "stable": stable}, ExitCode.OK
    if args.command == "scroll":
        return device.scroll_screen(args.direction, distance=args.distance), ExitCode.OK
    if args.command == "key":
        device.press(args.key)
        stable = device.wait_stable() if not args.no_wait else None
        return {"key": args.key, "stable": stable}, ExitCode.OK
    if args.command == "type":
        text = sys.stdin.read().rstrip("\r\n")
        result: dict[str, Any] = dict(device.type_text(text))
        result["stable"] = device.wait_stable() if not args.no_wait else None
        return result, ExitCode.OK
    if args.command == "apps":
        return device.list_packages(third_party=args.third_party), ExitCode.OK
    if args.command == "open-app":
        return (
            device.open_app(args.package_or_alias, wait=not args.no_wait),
            ExitCode.OK,
        )
    if args.command == "wait-stable":
        stable = device.wait_stable(timeout=args.timeout)
        return {"stable": stable}, ExitCode.OK if stable else ExitCode.OPERATION
    if args.command == "run":
        workflow = Path(args.file).expanduser().resolve()
        if not workflow.is_file():
            raise HarnessError(
                f"Workflow file does not exist: {workflow}",
                code=ExitCode.USAGE,
                kind="workflow_not_found",
            )
        from . import helpers

        helpers.configure(serial=args.serial, adb_path=args.adb)
        namespace = helpers.workflow_namespace()
        namespace["__name__"] = "__main__"
        namespace["__file__"] = str(workflow)
        code = compile(workflow.read_text(encoding="utf-8"), str(workflow), "exec")
        exec(code, namespace)
        return {"workflow": str(workflow), "completed": True}, ExitCode.OK
    if args.command == "helper":
        if args.helper_command == "status":
            return device.companion.status().to_dict(), ExitCode.OK
        if args.helper_command == "install":
            _require_confirmation(args, "Installing the companion APK")
            device.companion.install(Path(args.apk).expanduser().resolve())
            return device.companion.status().to_dict(), ExitCode.OK
        if args.helper_command == "enable":
            _require_confirmation(args, "Enabling the companion IME")
            device.companion.enable()
            return device.companion.status().to_dict(), ExitCode.OK
        if args.helper_command == "disable":
            _require_confirmation(args, "Disabling the companion IME")
            device.companion.disable()
            return device.companion.status().to_dict(), ExitCode.OK

    raise HarnessError(
        f"Unsupported command: {args.command}", code=ExitCode.USAGE, kind="unknown_command"
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    _configure_console_stream(sys.stdout)
    _configure_console_stream(sys.stderr)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result, code = execute(args)
        if args.command == "skill" and not args.install and not args.json:
            print(result, end="" if str(result).endswith("\n") else "\n")
        else:
            _emit(result, json_mode=args.json, success=code == ExitCode.OK)
        return int(code)
    except (ValueError, KeyError, TypeError):
        error = HarnessError("Invalid command arguments or JSON payload.", code=ExitCode.USAGE)
        if args.json:
            print(json.dumps(error.to_dict()))
        else:
            print(error.message, file=sys.stderr)
        return int(error.code)
    except HarnessError as exc:
        if args.json:
            print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"error: {exc.message}", file=sys.stderr)
            if exc.details:
                print(json.dumps(exc.details, ensure_ascii=False, indent=2), file=sys.stderr)
        return int(exc.code)


if __name__ == "__main__":
    raise SystemExit(main())
