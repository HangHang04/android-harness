"""Discovery and safe installation of the bundled Codex Skill."""

from __future__ import annotations

import os
import shutil
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from .errors import ExitCode, HarnessError

SKILL_NAME = "android-harness"


def skill_root() -> Any:
    """Return the importlib resource containing the bundled Skill."""

    return resources.files("android_harness").joinpath("skills", SKILL_NAME)


def skill_text() -> str:
    """Read the bundled Skill instructions."""

    return skill_root().joinpath("SKILL.md").read_text(encoding="utf-8")


def default_skill_destination() -> Path:
    """Return the Codex auto-discovery directory for this Skill."""

    configured_root = os.environ.get("CODEX_HOME")
    codex_root = Path(configured_root).expanduser() if configured_root else Path.home() / ".codex"
    return codex_root / "skills" / SKILL_NAME


def _bundled_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    def visit(node: Any, prefix: PurePosixPath) -> None:
        for child in sorted(node.iterdir(), key=lambda item: item.name):
            relative = prefix / child.name
            if child.is_file():
                files[relative.as_posix()] = child.read_bytes()
            elif child.is_dir():
                visit(child, relative)

    visit(skill_root(), PurePosixPath())
    return files


def _installed_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def install_skill(destination: str | Path | None = None) -> dict[str, Any]:
    """Install the complete bundled Skill without overwriting a different copy."""

    target = Path(destination).expanduser() if destination else default_skill_destination()
    target = target.resolve(strict=False)
    if target.name != SKILL_NAME:
        raise HarnessError(
            f"Skill destination must end with '{SKILL_NAME}': {target}",
            code=ExitCode.USAGE,
            kind="invalid_skill_destination",
        )

    bundled = _bundled_files()
    required = {
        "SKILL.md",
        "agents/openai.yaml",
        "references/wireless-debugging.md",
        "scripts/invoke-android-harness.ps1",
    }
    missing = sorted(required.difference(bundled))
    if missing:
        raise HarnessError(
            "Bundled Skill is incomplete.",
            code=ExitCode.CONFIG,
            kind="invalid_skill_bundle",
            details={"missing": missing},
        )

    if target.exists():
        if target.is_dir() and _installed_files(target) == bundled:
            return {
                "name": SKILL_NAME,
                "status": "unchanged",
                "destination": str(target),
                "files": sorted(bundled),
            }
        raise HarnessError(
            f"A different Skill already exists at {target}. Review it before replacing it.",
            code=ExitCode.CONFIG,
            kind="skill_destination_exists",
            details={"destination": str(target)},
        )

    parent = target.parent
    staging = parent / f".{SKILL_NAME}.install-{uuid4().hex}"
    try:
        parent.mkdir(parents=True, exist_ok=True)
        staging.mkdir()
        for relative, payload in bundled.items():
            output = staging.joinpath(*PurePosixPath(relative).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
        staging.replace(target)
    except OSError as exc:
        if staging.exists() and staging.parent == parent and staging.name.startswith(
            f".{SKILL_NAME}.install-"
        ):
            shutil.rmtree(staging)
        raise HarnessError(
            f"Could not install the Skill at {target}: {exc}",
            code=ExitCode.CONFIG,
            kind="skill_install_failed",
            details={"destination": str(target)},
        ) from exc

    return {
        "name": SKILL_NAME,
        "status": "installed",
        "destination": str(target),
        "files": sorted(bundled),
    }
