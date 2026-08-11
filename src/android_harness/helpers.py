"""Python workflow surface preloaded by ``android-harness run``."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Callable, Hashable, TypeVar

from .device import AndroidDevice, create_device
from .models import UiNode
from .ui import find_nodes

T = TypeVar("T")

_DEVICE: AndroidDevice | None = None
_SERIAL: str | None = None
_ADB_PATH: str | None = None


def configure(*, serial: str | None = None, adb_path: str | None = None) -> None:
    """Configure the device used by subsequent helpers in this process."""
    global _DEVICE, _SERIAL, _ADB_PATH
    _DEVICE = None
    _SERIAL = serial
    _ADB_PATH = adb_path


def device() -> AndroidDevice:
    global _DEVICE
    if _DEVICE is None:
        _DEVICE = create_device(serial=_SERIAL, adb_path=_ADB_PATH)
        _DEVICE.ensure_ready()
    return _DEVICE


def screen_info() -> dict[str, Any]:
    return device().screen_info()


def screenshot(path: str | Path | None = None) -> str:
    return str(device().screenshot(path))


def ui() -> list[dict[str, Any]]:
    return [node.to_dict() for node in device().ui_nodes()]


def find(
    query: str,
    *,
    exact: bool = False,
    resource_id: str | None = None,
    class_name: str | None = None,
    clickable: bool | None = None,
) -> list[dict[str, Any]]:
    return [
        node.to_dict()
        for node in find_nodes(
            device().ui_nodes(),
            query,
            exact=exact,
            resource_id=resource_id,
            class_name=class_name,
            clickable=clickable,
        )
    ]


def tap(x: int, y: int, *, wait: bool = False) -> bool | None:
    device().tap(x, y)
    return device().wait_stable() if wait else None


def tap_text(
    query: str,
    *,
    index: int | None = None,
    exact: bool = False,
    wait: bool = True,
) -> dict[str, Any]:
    return device().tap_text(query, index=index, exact=exact, wait=wait)


def long_press(x: int, y: int, duration_ms: int = 800, *, wait: bool = True) -> bool | None:
    device().long_press(x, y, duration_ms)
    return device().wait_stable() if wait else None


def swipe(
    direction: str,
    distance: float = 0.55,
    duration_ms: int = 220,
    *,
    wait: bool = True,
) -> bool | None:
    device().swipe(direction, distance, duration_ms)
    return device().wait_stable() if wait else None


def scroll(direction: str = "up", distance: float = 0.6) -> dict[str, Any]:
    return device().scroll_screen(direction, distance=distance)


def press(key: str, *, wait: bool = True) -> bool | None:
    device().press(key)
    return device().wait_stable() if wait else None


def type_text(text: str, *, wait: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = dict(device().type_text(text))
    result["stable"] = device().wait_stable() if wait else None
    return result


def open_app(package_or_alias: str, *, wait: bool = True) -> dict[str, Any]:
    return device().open_app(package_or_alias, wait=wait)


def wait_stable(timeout: float = 6.0) -> bool:
    return device().wait_stable(timeout=timeout)


def scroll_until(
    done: Callable[[list[dict[str, Any]]], T | None],
    *,
    direction: str = "up",
    distance: float = 0.6,
    max_scrolls: int = 60,
) -> T | None:
    current = ui()
    hit = done(current)
    if hit:
        return hit
    stale = 0
    for _ in range(max_scrolls):
        result = device().scroll_screen(direction, distance=distance)
        current = result["nodes"]
        hit = done(current)
        if hit:
            return hit
        stale = 0 if result["moved"] else stale + 1
        if stale >= 2:
            return None
    return None


def scroll_collect(
    extract: Callable[[list[dict[str, Any]]], list[T]] | None = None,
    *,
    key: Callable[[T], Hashable] | None = None,
    direction: str = "up",
    distance: float = 0.6,
    max_scrolls: int = 400,
    end_after: int = 3,
) -> dict[str, Any]:
    if extract is None:
        extract = lambda rows: [  # type: ignore[assignment]
            str(row.get("text") or row.get("content_desc") or "").strip()
            for row in rows
            if str(row.get("text") or row.get("content_desc") or "").strip()
        ]
    key = key or (lambda item: item)  # type: ignore[return-value]
    seen: set[Hashable] = set()
    ordered: list[T] = []

    def ingest(rows: list[dict[str, Any]]) -> int:
        added = 0
        assert extract is not None
        for item in extract(rows):
            item_key = key(item)
            if item_key in seen:
                continue
            seen.add(item_key)
            ordered.append(item)
            added += 1
        return added

    ingest(ui())
    stale = 0
    for scroll_number in range(1, max_scrolls + 1):
        result = device().scroll_screen(direction, distance=distance)
        ingest(result["nodes"])
        stale = 0 if result["moved"] else stale + 1
        if stale >= end_after:
            return {"items": ordered, "stop": "reached-end", "scrolls": scroll_number}
    return {"items": ordered, "stop": "max-scrolls", "scrolls": max_scrolls}


def _load_agent_helpers(namespace: dict[str, Any]) -> None:
    explicit = os.environ.get("ANDROID_HARNESS_AGENT_HELPERS")
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(Path.cwd() / "agent-workspace" / "agent_helpers.py")
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return
    spec = importlib.util.spec_from_file_location("android_harness_agent_helpers", path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace.update(
        {name: value for name, value in vars(module).items() if not name.startswith("_")}
    )


def workflow_namespace() -> dict[str, Any]:
    public_names = (
        "screen_info",
        "screenshot",
        "ui",
        "find",
        "tap",
        "tap_text",
        "long_press",
        "swipe",
        "scroll",
        "press",
        "type_text",
        "open_app",
        "wait_stable",
        "scroll_until",
        "scroll_collect",
    )
    namespace = {name: globals()[name] for name in public_names}
    _load_agent_helpers(namespace)
    return namespace
