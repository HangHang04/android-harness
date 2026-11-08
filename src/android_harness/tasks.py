"""In-memory task grants, serialized execution and cancellation."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from .actions import execute_action, foreground, transfer
from .device import create_device
from .errors import OperationError


@dataclass
class Task:
    id: str
    goal: str
    serial: str
    packages: list[str]
    capabilities: list[str]
    ttl: int = 1800
    local_root: str = ""
    remote_root: str = ""
    state: str = "pending"
    expires: float = 0
    busy: bool = False
    events: list = field(default_factory=list)


class TaskManager:
    def __init__(self, factory=create_device):
        self.tasks = {}
        self.lock = threading.RLock()
        self.execution = threading.Lock()
        self.factory = factory

    def request(self, spec):
        with self.lock:
            if len(self.tasks) >= 100:
                raise OperationError("任务数量已达上限，请重启控制台。")
            if not spec.get("goal") or not spec.get("serial") or not spec.get("packages"):
                raise OperationError("请填写任务目标、设备和允许的应用包名。")
            caps = spec.get("capabilities", ["observe"])
            packages = spec["packages"]
            if (
                not isinstance(packages, list)
                or not all(isinstance(p, str) for p in packages)
                or not isinstance(caps, list)
                or not caps
                or set(caps) - {"observe", "interact", "files"}
            ):
                raise OperationError("任务应用或能力格式无效。")
            ttl = int(spec.get("ttl", 1800))
            if not 60 <= ttl <= 1800:
                raise OperationError("授权时长应为 60–1800 秒。")
            task = Task(
                uuid.uuid4().hex,
                str(spec["goal"])[:500],
                str(spec["serial"]),
                packages[:50],
                caps,
                ttl,
                str(spec.get("local_root", "")),
                str(spec.get("remote_root", "")),
            )
            if "files" in caps:
                from pathlib import Path, PurePosixPath

                remote = PurePosixPath(task.remote_root)
                if (
                    not Path(task.local_root).is_dir()
                    or not remote.is_absolute()
                    or ".." in remote.parts
                    or not remote.is_relative_to("/sdcard")
                    or str(remote) == "/sdcard"
                ):
                    raise OperationError("请指定现有电脑目录和 /sdcard 下的手机目录。")
            self.tasks[task.id] = task
            return asdict(task)

    def get(self, task_id):
        if task_id not in self.tasks:
            raise OperationError("任务不存在。")
        return self.tasks[task_id]

    def snapshot(self):
        with self.lock:
            for task in self.tasks.values():
                if task.state == "active" and time.time() >= task.expires:
                    task.state = "expired"
            return [asdict(t) for t in self.tasks.values()]

    def approve(self, task_id):
        with self.lock:
            self.snapshot()
            if any(t.state == "active" or t.busy for t in self.tasks.values()):
                raise OperationError("请先结束当前任务。")
            task = self.get(task_id)
            if task.state != "pending":
                raise OperationError("只能批准待审批任务。")
            task.state, task.expires = "active", time.time() + task.ttl
            return asdict(task)

    def stop(self, task_id, complete=False):
        with self.lock:
            task = self.get(task_id)
            if task.state in {"pending", "active"}:
                task.state = "completed" if complete else "cancelled"
            return asdict(task)

    def check(self, task):
        with self.lock:
            if task.state == "active" and time.time() >= task.expires:
                task.state = "expired"
            if task.state != "active":
                raise OperationError("任务未获批准、已结束或授权过期。")

    def perform(self, task_id, action, args):
        if not self.execution.acquire(blocking=False):
            raise OperationError("当前操作正在执行，请等待结果。")
        task = None
        started = time.monotonic()
        try:
            task = self.get(task_id)
            self.check(task)
            task.busy = True
            device = self.factory(serial=task.serial)

            def checkpoint():
                self.check(task)
                device.ensure_ready()
                if foreground(device) not in task.packages:
                    raise OperationError("当前应用超出任务范围，请停止后重新授权。")

            def step(name, values):
                cap = (
                    "observe"
                    if name in {"observe", "find", "wait-for", "capabilities"}
                    else "files"
                    if name in {"push", "pull"}
                    else "interact"
                )
                if cap not in task.capabilities:
                    raise OperationError("该能力尚未获得授权。")
                if name in {"open-app", "open-url"}:
                    if values.get("package") not in task.packages:
                        raise OperationError("目标应用超出授权范围。")
                    self.check(task)
                    device.ensure_ready()
                else:
                    checkpoint()
                if name in {"push", "pull"}:
                    result = transfer(device, name, values, task.local_root, task.remote_root)
                else:
                    result = execute_action(
                        device,
                        name,
                        values,
                        (lambda: self.check(task))
                        if name in {"open-app", "open-url"}
                        else checkpoint,
                    )
                self.check(task)
                if foreground(device) not in task.packages:
                    raise OperationError("操作已跳转至范围外应用，任务已停止。")
                return result

            if action == "batch":
                steps = args.get("steps", [])
                if not isinstance(steps, list) or not 1 <= len(steps) <= 50:
                    raise OperationError("批次需要 1–50 个步骤。")
                result = []
                for entry in steps:
                    if entry["action"] == "batch":
                        raise OperationError("批次不能嵌套。")
                    if entry.get("before"):
                        step("wait-for", entry["before"])
                    result.append(step(entry["action"], entry.get("args", {})))
                    if entry.get("after"):
                        step("wait-for", entry["after"])
            else:
                result = step(action, args)
            task.events.append(
                {"action": action, "ok": True, "duration": round(time.monotonic() - started, 2)}
            )
            return result
        except Exception:
            if task:
                if task.state == "active":
                    task.state = "failed"
                task.events.append(
                    {
                        "action": action,
                        "ok": False,
                        "duration": round(time.monotonic() - started, 2),
                    }
                )
            raise
        finally:
            if task:
                task.busy = False
                task.events[:] = task.events[-200:]
            self.execution.release()
