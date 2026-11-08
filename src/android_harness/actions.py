"""Shared, bounded operations for the CLI and managed console tasks."""

from __future__ import annotations

import base64
import re
import shlex
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .errors import OperationError


def foreground(device):
    output = device.shell_text(["dumpsys", "activity", "activities"])
    for line in output.splitlines():
        if "mResumedActivity" in line or "topResumedActivity" in line:
            match = re.search(r" ([a-zA-Z][\w.]*)/", line)
            if match:
                return match.group(1)
    raise OperationError("无法确定前台应用，请重新观察。")


def select(nodes, selector):
    keys = {"text", "resource_id", "content_desc", "class_name"}
    if not isinstance(selector, dict) or not keys.intersection(selector):
        raise OperationError("请提供文本、描述或资源 ID。")
    if set(selector) - keys - {"exact"}:
        raise OperationError("不支持的元素选择条件。")
    return [
        n
        for n in nodes
        if all(
            (
                getattr(n, key) == value
                if key != "text" or selector.get("exact", True)
                else str(value).casefold() in getattr(n, key).casefold()
            )
            for key, value in selector.items()
            if key in keys
        )
    ]


def observe(device, screenshot=False):
    device.ensure_ready()
    info = device.screen_info()
    result = {
        "observation_id": uuid.uuid4().hex,
        "captured_at": datetime.now(UTC).isoformat(),
        "device": info,
        "package": foreground(device),
        "nodes": [n.to_dict() for n in device.ui_nodes()],
    }
    if screenshot:
        result["image_base64"] = base64.b64encode(device.capture_bytes()).decode("ascii")
    return result


def capabilities(device):
    device.ensure_ready()
    status = device.companion.status()
    return [
        {"name": name, "available": available, "reason": reason, "setup_action": setup}
        for name, available, reason, setup in (
            ("observe", True, "ADB 已就绪", ""),
            ("interact", True, "ADB 已就绪，操作能力受厂商设置影响", ""),
            ("files", True, "限 ADB 可访问且已授权的目录", ""),
            (
                "unicode",
                status.installed and status.enabled,
                "需要已启用的输入辅助组件",
                "helper status / 在手机启用输入法",
            ),
        )
    ]


def execute_action(device, action, args, checkpoint=lambda: None):
    checkpoint()
    if action == "observe":
        return observe(device, bool(args.get("screenshot")))
    if action == "capabilities":
        return capabilities(device)
    if action in {"find", "tap-element", "wait-for"}:
        timeout = float(args.get("timeout", 6))
        if not 0 <= timeout <= 60:
            raise OperationError("等待时间应为 0–60 秒。")
        deadline = time.monotonic() + timeout
        while True:
            checkpoint()
            matches = select(device.ui_nodes(), args.get("selector", {}))
            if action != "wait-for":
                break
            if bool(matches) != bool(args.get("absent", False)):
                return {"matched": True, "nodes": [n.to_dict() for n in matches]}
            if time.monotonic() >= deadline:
                raise OperationError("等待目标元素超时。")
            time.sleep(0.2)
        if action == "find":
            return [n.to_dict() for n in matches]
        if len(matches) != 1:
            raise OperationError(
                "元素不存在或存在多个候选，请细化条件。",
                details={"matches": [n.to_dict() for n in matches]},
            )
        node = matches[0]
        if not node.enabled:
            raise OperationError("目标元素不可用。")
        checkpoint()
        device.tap(*node.center)
        return {"clicked": True}
    if action == "tap":
        x, y = int(args["x"]), int(args["y"])
        width, height = device.screen_size()
        if not 0 <= x < width or not 0 <= y < height:
            raise OperationError("坐标超出屏幕范围。")
        device.tap(x, y)
    elif action == "type":
        return device.type_text(str(args["text"]))
    elif action == "swipe":
        device.swipe(args.get("direction", "up"))
    elif action == "key":
        device.press(args["key"])
    elif action == "open-app":
        return device.open_app(args["package"], wait=False)
    elif action == "open-url":
        url, package = str(args["url"]), str(args["package"])
        if urlsplit(url).scheme not in {"https", "http"} or not urlsplit(url).hostname:
            raise OperationError("页面跳转仅接受有效的 HTTP/HTTPS 地址。")
        if not re.fullmatch(r"[A-Za-z][\w]*(?:\.[\w]+)+", package):
            raise OperationError("应用包名无效。")
        output = device.shell_text(
            [
                "am",
                "start",
                "-W",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                shlex.quote(url),
                "-p",
                package,
            ]
        )
        if "Error:" in output or "Exception" in output:
            raise OperationError("目标应用未能打开该页面。")

    else:
        raise OperationError("不支持的操作。")
    return {"completed": True}


def transfer(device, direction, args, local_root, remote_root):
    root = Path(local_root).resolve(strict=True)
    local = Path(args["local"]).resolve()
    remote = PurePosixPath(str(args["remote"]))
    remote_base = PurePosixPath(remote_root)
    if (
        not local.is_relative_to(root)
        or local == root
        or not remote.is_absolute()
        or ".." in remote.parts
        or not remote.is_relative_to(remote_base)
        or remote == remote_base
        or "\x00" in str(remote)
    ):
        raise OperationError("文件路径超出授权目录。")
    # Reject remote symlinks and canonicalize the parent before either direction.
    canonical_root = device.shell_text(["readlink", "-f", shlex.quote(str(remote_base))])
    resolved = device.shell_text(["readlink", "-f", shlex.quote(str(remote.parent))])
    if (
        not canonical_root
        or not resolved
        or not PurePosixPath(resolved).is_relative_to(canonical_root)
    ):
        raise OperationError("手机目标目录不可用或包含越界链接。")
    if (
        device.shell_text(
            ["test", "-L", shlex.quote(str(remote)), "&&", "echo", "link"], check=False
        )
        == "link"
    ):
        raise OperationError("文件传输不接受符号链接。")
    if direction == "push":
        if not local.is_file():
            raise OperationError("电脑源文件不存在。")
        exists = device.shell_text(
            ["test", "-e", shlex.quote(str(remote)), "&&", "echo", "yes"], check=False
        )
        if exists == "yes":
            raise OperationError("手机目标文件已经存在。")
        device.runner.run(["push", str(local), str(remote)])
    else:
        if local.exists() or not local.parent.is_dir():
            raise OperationError("电脑目标已经存在或其目录不存在。")
        if (
            device.shell_text(
                ["test", "-f", shlex.quote(str(remote)), "&&", "echo", "yes"], check=False
            )
            != "yes"
        ):
            raise OperationError("手机源文件不是普通文件。")
        device.runner.run(["pull", str(remote), str(local)])
    return {"completed": True}
