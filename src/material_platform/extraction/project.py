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
    {"tests", "test", "__pycache__", "node_modules", "dist", "build", ".git"}
)
_PROJECT_NAMES = frozenset({"go.mod", "Pipfile"})
_PROJECT_SUFFIXES = CODE_SUFFIXES | TEXT_SUFFIXES | frozenset(
    {".toml", ".json", ".xml", ".gradle", ".mod"}
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
        "requirements.txt",
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


def extract_project(
    files: tuple[MaterialFile, ...],
    *,
    max_units: int = DEFAULT_MAX_UNITS,
) -> tuple[ContentUnit, ...]:
    ranked = sorted(
        ((rank, item) for item in files if (rank := _rank(item)) is not None),
        key=lambda pair: (pair[0], pair[1].path.lower()),
    )
    chosen = ranked[:max_units]
    units = tuple(
        extract_text(item).model_copy(update={"type": "file"})
        for _rank, item in chosen
    )
    return merge_unit_metadata(units, project_identity(files))


def _rank(item: MaterialFile) -> int | None:
    path = Path(item.path)
    if any(part in _SKIP_DIRS for part in path.parts):
        return None
    name = path.name
    if name in _SKIP_NAMES or name.startswith("test_"):
        return None
    suffix = path.suffix.lower()
    if name not in _PROJECT_NAMES and suffix not in _PROJECT_SUFFIXES:
        return None
    lower = name.lower()
    if lower in _IDENTITY:
        return 0
    if lower in _ENTRY or path.parts[0] == "cmd":
        return 1
    stem = path.stem.lower()
    if stem == "api" or stem.startswith("api_") or stem.startswith("routes"):
        return 2
    data = item.data
    if b"handle_request" in data or b"HandleRequest" in data:
        return 2
    return None
