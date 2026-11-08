"""Parse and query Android UI Automator hierarchy dumps."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable

from .errors import OperationError
from .models import Bounds, UiNode

_BOUNDS_RE = re.compile(r"^\[(-?\d+),(-?\d+)]\[(-?\d+),(-?\d+)]$")


def _as_bool(value: str | None) -> bool:
    return (value or "").casefold() == "true"


def parse_bounds(value: str) -> Bounds:
    match = _BOUNDS_RE.match(value)
    if not match:
        raise OperationError("Invalid bounds in UI hierarchy", details={"bounds": value})
    left, top, right, bottom = (int(item) for item in match.groups())
    if right < left or bottom < top:
        raise OperationError("Inverted bounds in UI hierarchy", details={"bounds": value})
    return Bounds(left, top, right, bottom)


def parse_hierarchy(xml_text: str) -> list[UiNode]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise OperationError(
            f"UI Automator returned invalid XML: {exc}",
            details={"preview": xml_text[:300]},
        ) from exc

    nodes: list[UiNode] = []
    for fallback_index, element in enumerate(root.iter("node")):
        attrs = element.attrib
        bounds_text = attrs.get("bounds", "")
        if not bounds_text:
            continue
        try:
            bounds = parse_bounds(bounds_text)
        except OperationError:
            continue
        try:
            index = int(attrs.get("index", fallback_index))
        except ValueError:
            index = fallback_index
        nodes.append(
            UiNode(
                text="" if _as_bool(attrs.get("password")) else attrs.get("text", ""),
                content_desc=""
                if _as_bool(attrs.get("password"))
                else attrs.get("content-desc", ""),
                resource_id=attrs.get("resource-id", ""),
                class_name=attrs.get("class", ""),
                package=attrs.get("package", ""),
                bounds=bounds,
                clickable=_as_bool(attrs.get("clickable")),
                enabled=_as_bool(attrs.get("enabled")),
                scrollable=_as_bool(attrs.get("scrollable")),
                selected=_as_bool(attrs.get("selected")),
                focused=_as_bool(attrs.get("focused")),
                index=index,
                password=_as_bool(attrs.get("password")),
                checkable=_as_bool(attrs.get("checkable")),
                checked=_as_bool(attrs.get("checked")),
            )
        )
    return nodes


def find_nodes(
    nodes: Iterable[UiNode],
    query: str,
    *,
    exact: bool = False,
    resource_id: str | None = None,
    class_name: str | None = None,
    clickable: bool | None = None,
) -> list[UiNode]:
    query_folded = query.casefold().strip()
    if not query_folded:
        return []
    filtered: list[UiNode] = []
    for node in nodes:
        if resource_id and node.resource_id != resource_id:
            continue
        if class_name and node.class_name != class_name:
            continue
        if clickable is not None and node.clickable is not clickable:
            continue
        labels = (node.text.casefold(), node.content_desc.casefold())
        matched = (
            any(label == query_folded for label in labels)
            if exact
            else any(query_folded in label for label in labels if label)
        )
        if matched:
            filtered.append(node)
    return filtered


def preferred_text_matches(nodes: Iterable[UiNode], query: str) -> tuple[list[UiNode], str]:
    materialized = list(nodes)
    exact = find_nodes(materialized, query, exact=True)
    if exact:
        return exact, "exact"
    return find_nodes(materialized, query, exact=False), "substring"


def visible_labels(nodes: Iterable[UiNode], limit: int = 30) -> list[str]:
    labels: list[str] = []
    for node in nodes:
        label = node.label.strip()
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def content_signature(nodes: Iterable[UiNode], screen_height: int) -> str:
    top = screen_height * 0.06
    bottom = screen_height * 0.94
    rows = []
    for node in nodes:
        _, center_y = node.center
        if not top < center_y < bottom:
            continue
        rows.append(
            (
                node.text,
                node.content_desc,
                node.resource_id,
                node.class_name,
                node.bounds.to_list(),
                node.enabled,
                node.selected,
                node.checked,
            )
        )
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def content_labels(nodes: Iterable[UiNode], screen_height: int) -> frozenset[str]:
    top = screen_height * 0.06
    bottom = screen_height * 0.94
    labels = {
        node.label.strip() for node in nodes if top < node.center[1] < bottom and node.label.strip()
    }
    return frozenset(labels)


def jaccard_overlap(before: frozenset[str], after: frozenset[str]) -> float:
    if not before and not after:
        return 1.0
    if not before or not after:
        return 0.0
    return len(before & after) / len(before | after)
