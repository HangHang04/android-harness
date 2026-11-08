from __future__ import annotations

import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from android_harness.actions import execute_action, select, transfer
from android_harness.console import ConsoleServer
from android_harness.errors import OperationError
from android_harness.tasks import TaskManager
from android_harness.ui import parse_hierarchy


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.device = MagicMock()
        self.device.shell_text.return_value = (
            "mResumedActivity: ActivityRecord{ u0 com.example/.Main }"
        )
        self.manager = TaskManager(lambda **_: self.device)
        self.task = self.manager.request(
            dict(
                goal="test",
                serial="ABC",
                packages=["com.example"],
                capabilities=["observe", "interact"],
            )
        )
        self.id = self.task["id"]

    def test_pending_cannot_execute(self):
        with self.assertRaises(OperationError):
            self.manager.perform(self.id, "key", {"key": "back"})
        self.device.press.assert_not_called()

    def test_approved_execution_and_redacted_events(self):
        self.manager.approve(self.id)
        self.manager.perform(self.id, "type", {"text": "private payload"})
        self.device.type_text.assert_called_once_with("private payload")
        self.assertNotIn("private payload", json.dumps(self.manager.snapshot()))

    def test_expiry(self):
        self.manager.approve(self.id)
        self.manager.get(self.id).expires = time.time() - 1
        with self.assertRaises(OperationError):
            self.manager.perform(self.id, "key", {"key": "back"})
        self.assertEqual("expired", self.manager.get(self.id).state)

    def test_stop_between_batch_steps(self):
        self.manager.approve(self.id)
        self.device.press.side_effect = lambda _: self.manager.stop(self.id)
        with self.assertRaises(OperationError):
            self.manager.perform(
                self.id,
                "batch",
                {
                    "steps": [
                        {"action": "key", "args": {"key": "back"}},
                        {"action": "key", "args": {"key": "home"}},
                    ]
                },
            )
        self.assertEqual(1, self.device.press.call_count)

    def test_out_of_scope_app(self):
        self.manager.approve(self.id)
        self.device.shell_text.return_value = (
            "mResumedActivity: ActivityRecord{ u0 other.app/.Main }"
        )
        with self.assertRaises(OperationError):
            self.manager.perform(self.id, "key", {"key": "back"})
        self.device.press.assert_not_called()

    def test_capability_denied(self):
        self.manager.get(self.id).capabilities = ["observe"]
        self.manager.approve(self.id)
        with self.assertRaises(OperationError):
            self.manager.perform(self.id, "type", {"text": "x"})
        self.device.type_text.assert_not_called()

    def test_single_active_task(self):
        self.manager.approve(self.id)
        other = self.manager.request(dict(goal="second", serial="ABC", packages=["com.example"]))
        with self.assertRaises(OperationError):
            self.manager.approve(other["id"])

    def test_concurrent_submission_rejected(self):
        self.manager.approve(self.id)
        self.manager.execution.acquire()
        try:
            with self.assertRaises(OperationError):
                self.manager.perform(self.id, "key", {"key": "back"})
        finally:
            self.manager.execution.release()


class ActionTests(unittest.TestCase):
    def test_password_and_checked(self):
        nodes = parse_hierarchy(
            '<hierarchy><node text="secret" content-desc="secret" '
            'password="true" checked="true" bounds="[0,0][10,10]" '
            'resource-id="id"/></hierarchy>'
        )
        self.assertEqual("", nodes[0].text)
        self.assertEqual("", nodes[0].to_dict()["content_desc"])
        self.assertTrue(nodes[0].checked)
        self.assertEqual(1, len(select(nodes, {"resource_id": "id"})))

    def test_ambiguous_tap(self):
        device = MagicMock()
        device.ui_nodes.return_value = [MagicMock(), MagicMock()]
        with self.assertRaises(OperationError):
            execute_action(device, "tap-element", {"selector": {"text": "same"}})
        device.tap.assert_not_called()

    def test_reject_non_http_url(self):
        with self.assertRaises(OperationError):
            execute_action(MagicMock(), "open-url", {"url": "intent://x", "package": "com.example"})

    def test_file_path_escape(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(OperationError):
                transfer(
                    MagicMock(),
                    "pull",
                    {"local": str(Path(root).parent / "escape"), "remote": "/sdcard/Download/x"},
                    root,
                    "/sdcard/Download",
                )

    def test_adb_timeout_redacts_payload(self):
        import subprocess

        from android_harness.adb import AdbRunner
        from android_harness.errors import HarnessError

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 1)):
            with self.assertRaises(HarnessError) as context:
                AdbRunner("adb").run(["shell", "input", "text", "secret"])
        self.assertNotIn("secret", json.dumps(context.exception.to_dict()))


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = ConsoleServer()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def call(self, path, data=None, ui=False, origin=None):
        headers = {"Authorization": "Bearer " + self.server.agent_token}
        if ui:
            headers["Cookie"] = "harness=" + self.server.ui_token
        if origin:
            headers["Origin"] = origin
        request = Request(
            self.server.origin + path,
            headers=headers,
            data=json.dumps(data).encode() if data is not None else None,
        )
        try:
            response = urlopen(request)
        except HTTPError as exc:
            response = exc
        with response:
            return json.load(response)

    def test_agent_cannot_approve(self):
        task = self.call("/api/tasks", dict(goal="test", serial="ABC", packages=["com.example"]))[
            "result"
        ]
        self.assertFalse(self.call("/api/approve", {"task_id": task["id"]})["ok"])
        self.assertTrue(self.call("/api/approve", {"task_id": task["id"]}, ui=True)["ok"])

    def test_reject_cross_origin(self):
        self.assertFalse(self.call("/api/tasks", origin="https://example.com")["ok"])

    def test_no_arbitrary_files(self):
        self.assertFalse(self.call("/../../pyproject.toml")["ok"])

    def test_body_limit(self):
        import http.client

        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.putrequest("POST", "/api/tasks")
        connection.putheader("Content-Length", str(1024 * 1024 + 1))
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(400, response.status)
        response.read()
        connection.close()


if __name__ == "__main__":
    unittest.main()
