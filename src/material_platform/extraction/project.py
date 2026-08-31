from __future__ import annotations

from pathlib import Path

from material_platform.classification.deterministic import (
    CODE_SUFFIXES,
    TEXT_SUFFIXES,
)
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile
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
_PROJECT_SUFFIXES = CODE_SUFFIXES | TEXT_SUFFIXES | frozenset({".toml", ".json"})


def extract_project(files: tuple[MaterialFile, ...]) -> tuple[ContentUnit, ...]:
    units: list[ContentUnit] = []
    for item in files:
        name = Path(item.path).name
        if name in _SKIP_NAMES:
            continue
        if Path(item.path).suffix.lower() not in _PROJECT_SUFFIXES:
            continue
        unit = extract_text(item)
        units.append(
            unit.model_copy(
                update={"type": "file"},
            )
        )
    return tuple(units)
