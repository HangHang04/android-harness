"""Loopback-only console. UI approval and agent execution use separate credentials."""

from __future__ import annotations

import json
import os
import secrets
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from .adb import AdbRunner
from .config import load_config
from .errors import HarnessError, OperationError
from .tasks import TaskManager


def runtime_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "android-harness/runtime.json"


def agent_call(path, payload=None):
    try:
        config = json.loads(runtime_path().read_text(encoding="utf-8"))
        from urllib.parse import urlsplit

        url = urlsplit(config["url"])
        if url.scheme != "http" or url.hostname != "127.0.0.1":
            raise ValueError("invalid endpoint")
        request = Request(
            config["url"] + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": "Bearer " + config["agent_token"],
                "Content-Type": "application/json",
            },
        )
        from urllib.error import HTTPError

        try:
            response = build_opener(ProxyHandler({})).open(request, timeout=180)
        except HTTPError as exc:
            response = exc
        with response:
            value = json.load(response)
        if not value["ok"]:
            raise OperationError(value["error"]["message"])
        return value["result"]
    except (OSError, ValueError, KeyError) as exc:
        raise OperationError("控制台尚未启动，请先运行 console。") from exc


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=0, manager=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.manager = manager or TaskManager()
        self.agent_token = secrets.token_urlsafe(32)
        self.ui_token = secrets.token_urlsafe(32)
        self.bootstrap = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, value, status=200, content_type="application/json; charset=utf-8", cookie=None):
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        )
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, post):
        try:
            self.connection.settimeout(10)
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                raise OperationError("请求来源无效。")
            origin = self.headers.get("Origin")
            if origin and origin != self.server.origin:
                raise OperationError("请求来源无效。")
            path = self.path
            if not post and path in {"/", "/app.js", "/style.css"}:
                name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                mime = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}[
                    path
                ]
                self.reply(
                    files("android_harness").joinpath("web", name).read_bytes(), content_type=mime
                )
                return
            payload = {}
            if post:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 1024 * 1024 or self.headers.get("Transfer-Encoding"):
                    raise OperationError("请求大小无效。")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise OperationError("请求必须是对象。")
            if path == "/api/bootstrap" and post:
                if not secrets.compare_digest(str(payload.get("token", "")), self.server.bootstrap):
                    raise OperationError("请从启动控制台时打开的页面进入。")
                self.server.bootstrap = secrets.token_urlsafe(32)
                self.reply(
                    {"ok": True, "result": {}},
                    cookie=f"harness={self.server.ui_token}; HttpOnly; SameSite=Strict; Path=/",
                )
                return
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            ui = secrets.compare_digest(
                cookie.get("harness").value if cookie.get("harness") else "", self.server.ui_token
            )
            agent = secrets.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + self.server.agent_token
            )
            if not ui and not agent:
                raise OperationError("需要有效的控制台会话。")
            manager = self.server.manager
            if path == "/api/tasks" and not post:
                result = manager.snapshot()
            elif path == "/api/tasks" and post:
                result = manager.request(payload)
            elif path == "/api/action" and post:
                result = manager.perform(
                    payload["task_id"], payload["action"], payload.get("args", {})
                )
            elif path in {"/api/approve", "/api/stop", "/api/complete"} and post:
                if path == "/api/approve":
                    if not ui:
                        raise OperationError("请在控制台中由用户批准。")
                    result = manager.approve(payload["task_id"])
                else:
                    result = manager.stop(payload["task_id"], complete=path == "/api/complete")
            elif path == "/api/devices" and not post:
                result = [d.to_dict() for d in AdbRunner().devices()]
            elif path == "/api/config" and not post:
                config = load_config()
                result = {
                    "app_aliases": config.app_aliases,
                    "command_timeout": config.command_timeout,
                }
            elif path == "/api/connect" and post and ui:
                import ipaddress

                host = str(ipaddress.ip_address(payload["host"]))
                port = int(payload["port"])
                if not 1 <= port <= 65535:
                    raise OperationError("端口应为 1–65535。")
                endpoint = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
                if payload.get("pair"):
                    code = str(payload["code"])
                    if len(code) != 6 or not code.isdecimal():
                        raise OperationError("请输入手机当前显示的六位配对码。")
                    AdbRunner().run(["pair", endpoint], input_data=code + "\n", use_serial=False)
                else:
                    AdbRunner().run(["connect", endpoint], use_serial=False)
                result = {"message": "请求已完成，请刷新设备列表确认。"}
            else:
                raise OperationError("接口不存在或操作不允许。")
            self.reply({"ok": True, "result": result})
        except HarnessError as exc:
            self.reply(exc.to_dict(), 400)
        except Exception:
            self.reply(
                {"ok": False, "error": {"message": "请求格式错误或操作失败，请检查参数与设备。"}},
                400,
            )


def serve(port=0, open_browser=True):
    server = ConsoleServer(port)
    runtime = runtime_path()
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(
        json.dumps({"url": server.origin, "agent_token": server.agent_token}), encoding="utf-8"
    )
    url = server.origin + "/#" + server.bootstrap
    if open_browser:
        webbrowser.open(url)
        print(f"控制台已启动：{server.origin}（保持此进程运行）", flush=True)
    else:
        print(f"控制台访问地址（仅在本机使用）：{url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            if json.loads(runtime.read_text(encoding="utf-8"))["agent_token"] == server.agent_token:
                runtime.unlink()
        except (OSError, ValueError, KeyError):
            pass
