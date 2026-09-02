from __future__ import annotations

from pathlib import Path

from material_platform.classification.deterministic import (
    CODE_SUFFIXES,
    TEXT_SUFFIXES,
)
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.budget import DEFAULT_MAX_UNITS
from material_platform.extraction.common import MaterialFile, merge_unit_metadata
from material_platform.extraction.manifest import project_identity
from material_platform.extraction.text import extract_text

_SKIP_NAMES = frozenset(
    {
        "package-lock.json",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
        "pnpm-lock.yaml",
    }
)
_SKIP_DIRS = frozenset(
    {
        "tests",
        "test",
        "examples",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".git",
        "docs",
    }
)
_PROJECT_NAMES = frozenset({"go.mod", "Pipfile"})
_PROJECT_SUFFIXES = (
    CODE_SUFFIXES
    | TEXT_SUFFIXES
    | frozenset({".toml", ".json", ".xml", ".gradle", ".mod"})
)
_IDENTITY = frozenset(
    {
        "pyproject.toml",
        "go.mod",
        "package.json",
        "cargo.toml",
        "pom.xml",
        "pipfile",
        "setup.py",
        "build.gradle",
    }
)
_ENTRY = frozenset(
    {
        "main.py",
        "main.go",
        "main.rs",
        "index.js",
        "index.ts",
        "index.mjs",
        "app.js",
        "app.ts",
        "app.jsx",
        "app.tsx",
        "cli.py",
    }
)
_API_STEMS = frozenset({"api", "routes", "router", "handler", "endpoint"})
_BUCKETS = (
    ("identity", 2),
    ("config", 2),
    ("entry", 2),
    ("api", 4),
    ("core", 5),
)
_KIND_RANK = {
    "identity": 0,
    "config": 1,
    "entry": 2,
    "api": 3,
    "core": 4,
    "subsystem": 5,
}
_CORE_NAMES = frozenset({"core", "lib", "service", "internal"})


def extract_project(
    files: tuple[MaterialFile, ...],
    *,
    max_units: int = DEFAULT_MAX_UNITS,
) -> tuple[ContentUnit, ...]:
    chosen = select_deep_files(files, max_units=max_units)
    units = tuple(
        extract_text(item).model_copy(update={"type": "file"}) for item in chosen
    )
    return merge_unit_metadata(units, project_identity(files))


def eligible_project_files(
    files: tuple[MaterialFile, ...],
) -> tuple[MaterialFile, ...]:
    return tuple(item for item in files if _eligible(item))


def select_deep_files(
    files: tuple[MaterialFile, ...],
    *,
    max_units: int,
) -> tuple[MaterialFile, ...]:
    eligible = eligible_project_files(files)
    by_kind: dict[str, list[MaterialFile]] = {name: [] for name, _budget in _BUCKETS}
    for item in eligible:
        by_kind.setdefault(file_kind(item), []).append(item)
    picked: list[MaterialFile] = []
    seen: set[str] = set()
    remaining = max(max_units, 0)
    for kind, budget in _BUCKETS:
        take = min(budget, remaining, len(by_kind[kind]))
        for item in _spread(by_kind[kind], take):
            if item.path in seen:
                continue
            picked.append(item)
            seen.add(item.path)
            remaining -= 1
            if remaining <= 0:
                return tuple(picked)
    leftover = [item for item in eligible if item.path not in seen]
    leftover.sort(key=lambda item: _KIND_RANK.get(file_kind(item), 9))
    for item in leftover:
        if remaining <= 0:
            break
        picked.append(item)
        seen.add(item.path)
        remaining -= 1
    return tuple(picked)


def file_kind(item: MaterialFile) -> str:
    path = Path(item.path)
    lower = path.name.lower()
    if lower in _IDENTITY:
        return "identity"
    if lower in {"setup.cfg", "setup.py", "cargo.toml"}:
        return "config"
    if lower in _ENTRY or (path.parts and path.parts[0] == "cmd"):
        return "entry"
    stem = path.stem.lower()
    if stem in _API_STEMS or stem.startswith("api_") or stem.startswith("routes"):
        return "api"
    data = item.data
    if b"handle_request" in data or b"HandleRequest" in data:
        return "api"
    if stem in _CORE_NAMES or any(
        part.lower() in _CORE_NAMES for part in path.parts[:-1]
    ):
        return "core"
    return "subsystem"


def subsystem_of(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] in {"src", "lib", "pkg"}:
        return parts[1]
    if parts:
        return parts[0]
    return path


def _eligible(item: MaterialFile) -> bool:
    path = Path(item.path)
    if any(part in _SKIP_DIRS for part in path.parts):
        return False
    name = path.name
    if name in _SKIP_NAMES or name.startswith("test_"):
        return False
    suffix = path.suffix.lower()
    return name in _PROJECT_NAMES or suffix in _PROJECT_SUFFIXES


def _spread(items: list[MaterialFile], take: int) -> list[MaterialFile]:
    if take >= len(items):
        return list(items)
    grouped: dict[str, list[MaterialFile]] = {}
    order: list[str] = []
    for item in items:
        key = subsystem_of(item.path)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(item)
    picked: list[MaterialFile] = []
    while len(picked) < take:
        progressed = False
        for key in order:
            bucket = grouped[key]
            if not bucket:
                continue
            picked.append(bucket.pop(0))
            progressed = True
            if len(picked) >= take:
                break
        if not progressed:
            break
    return picked
