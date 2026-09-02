from __future__ import annotations

import re

from material_platform.analysis.group import content_tokens, group_units
from material_platform.analysis.keywords import from_text, unique
from material_platform.domain.research_material import ContentUnit

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def extractive_leaf(group: tuple[ContentUnit, ...]) -> dict[str, object]:
    text = "\n".join(unit.content for unit in group if unit.content.strip())
    head = "\n".join(unit.content for unit in group[:2] if unit.content.strip())
    headings = tuple(match.strip() for match in _HEADING.findall(text) if match.strip())
    pages = [unit.location.page for unit in group if unit.location.page is not None]
    paths = [unit.location.path for unit in group if unit.location.path]
    covered: dict[str, object] = {}
    if pages:
        covered = {"page_start": min(pages), "page_end": max(pages)}
    elif paths:
        covered = {"path_start": paths[0], "path_end": paths[-1]}
    return {
        "summary": _summary(head or text),
        "main_points": list(headings[:8]),
        "topics": list(from_text(text, limit=12)),
        "candidate_keywords": list(from_text(text, limit=20)),
        "section_titles": list(headings[:8]),
        "covered_locations": covered,
        "units": len(group),
        "tokens": content_tokens(group),
    }


def merge_leaves(leaves: tuple[dict[str, object], ...]) -> dict[str, object]:
    summaries: list[str] = []
    points: list[str] = []
    topics: list[str] = []
    keywords: list[str] = []
    titles: list[str] = []
    pages: list[int] = []
    for leaf in leaves:
        summary = leaf.get("summary")
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())
        for key, bucket in (
            ("main_points", points),
            ("topics", topics),
            ("candidate_keywords", keywords),
            ("section_titles", titles),
        ):
            value = leaf.get(key)
            if isinstance(value, list):
                bucket.extend(str(item) for item in value if item)
        covered = leaf.get("covered_locations")
        if isinstance(covered, dict):
            for field in ("page_start", "page_end"):
                raw = covered.get(field)
                if isinstance(raw, int):
                    pages.append(raw)
    covered_out: dict[str, object] = {}
    if pages:
        covered_out = {"page_start": min(pages), "page_end": max(pages)}
    return {
        "summary": " ".join(summaries)[:800],
        "main_points": list(unique(points, limit=12)),
        "topics": list(unique(topics, limit=12)),
        "candidate_keywords": list(unique(keywords, limit=40)),
        "section_titles": list(unique(titles, limit=12)),
        "covered_locations": covered_out,
        "units": sum(int(leaf.get("units") or 0) for leaf in leaves),
    }


def reduce_leaves(
    leaves: tuple[dict[str, object], ...],
    *,
    fan_in: int,
) -> tuple[dict[str, object], ...]:
    size = max(fan_in, 2)
    if len(leaves) <= 1:
        return leaves
    merged: list[dict[str, object]] = []
    for start in range(0, len(leaves), size):
        merged.append(merge_leaves(leaves[start : start + size]))
    return tuple(merged)


def hierarchical_digests(
    units: tuple[ContentUnit, ...],
    *,
    leaf_tokens: int,
    fan_in: int,
) -> tuple[dict[str, object], ...]:
    groups = group_units(units, target_tokens=leaf_tokens)
    leaves = tuple(extractive_leaf(group) for group in groups)
    while len(leaves) > 1:
        leaves = reduce_leaves(leaves, fan_in=fan_in)
    return leaves


def _summary(text: str) -> str:
    parts = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    if parts:
        return " ".join(parts[:2])[:400]
    return text.strip()[:400]
