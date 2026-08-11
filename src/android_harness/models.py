"""Shared serializable value objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str | bytes
    stderr: str


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    serial: str
    state: str
    product: str | None = None
    model: str | None = None
    device: str | None = None
    transport_id: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def to_list(self) -> list[int]:
        return [self.left, self.top, self.right, self.bottom]


@dataclass(frozen=True, slots=True)
class UiNode:
    text: str
    content_desc: str
    resource_id: str
    class_name: str
    package: str
    bounds: Bounds
    clickable: bool
    enabled: bool
    scrollable: bool
    selected: bool
    focused: bool
    index: int

    @property
    def center(self) -> tuple[int, int]:
        return self.bounds.center

    @property
    def label(self) -> str:
        return self.text or self.content_desc or self.resource_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "content_desc": self.content_desc,
            "resource_id": self.resource_id,
            "class_name": self.class_name,
            "package": self.package,
            "bounds": self.bounds.to_list(),
            "center": list(self.center),
            "clickable": self.clickable,
            "enabled": self.enabled,
            "scrollable": self.scrollable,
            "selected": self.selected,
            "focused": self.focused,
            "index": self.index,
        }


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    required: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
