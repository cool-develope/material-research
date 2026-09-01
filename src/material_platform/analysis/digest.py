from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from material_platform.classification.deterministic import ClassificationDecision
from material_platform.domain.enums import MaterialType
from material_platform.domain.research_material import ContentUnit
from material_platform.index.tokens import tokenize

DIGEST_TOKENS = 8192
SNIPPET_TOKENS = 256
IDENTITY_TOKENS = 512
DOC_SNIPPETS = 8
PROJECT_BODIES = 8

_IDENTITY_NAMES = frozenset(
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


@dataclass(frozen=True)
class MaterialDigest:
    text: str
    unit_count: int
    token_count: int
    omitted_units: int


def build_digest(
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    *,
    digest_tokens: int = DIGEST_TOKENS,
    snippet_tokens: int = SNIPPET_TOKENS,
) -> MaterialDigest:
    header = _header(decision, units)
    chosen = _choose(decision, units)
    parts = [header]
    used = 0
    for unit in chosen:
        limit = IDENTITY_TOKENS if _is_identity(unit) else snippet_tokens
        snippet = _clip(unit.content, limit)
        label = _label(unit)
        block = f"[{label}]\n{snippet}"
        size = _tokens(block)
        if parts and used + size > digest_tokens:
            break
        parts.append(block)
        used += size
    text = "\n\n".join(parts)
    return MaterialDigest(
        text=text,
        unit_count=len(chosen),
        token_count=_tokens(text),
        omitted_units=max(0, len(units) - len(chosen)),
    )


def _choose(
    decision: ClassificationDecision, units: tuple[ContentUnit, ...]
) -> tuple[ContentUnit, ...]:
    if decision.material_type is MaterialType.DOCUMENT:
        return _document_sample(units)
    if decision.material_type is MaterialType.PROJECT:
        return _project_sample(units)
    if not units:
        return ()
    return (units[0],)


def _document_sample(units: tuple[ContentUnit, ...]) -> tuple[ContentUnit, ...]:
    pages = [unit for unit in units if unit.location.page is not None]
    pages.sort(
        key=lambda unit: (
            unit.location.page or 0,
            _chunk_index(unit),
        )
    )
    pool = pages or list(units)
    return tuple(pool[index] for index in _spread_indexes(len(pool), DOC_SNIPPETS))


def _project_sample(units: tuple[ContentUnit, ...]) -> tuple[ContentUnit, ...]:
    first: dict[str, ContentUnit] = {}
    order: list[str] = []
    for unit in units:
        path = unit.location.path or unit.unit_id
        current = first.get(path)
        if current is None:
            first[path] = unit
            order.append(path)
            continue
        if _chunk_index(unit) < _chunk_index(current):
            first[path] = unit
    identity = [first[path] for path in order if _is_identity(first[path])]
    bodies = [first[path] for path in order if not _is_identity(first[path])]
    return tuple(identity + bodies[:PROJECT_BODIES])


def _spread_indexes(count: int, take: int) -> list[int]:
    if count <= take:
        return list(range(count))
    first, last = 3, 2
    mid = take - first - last
    indexes = list(range(first))
    inner = count - first - last
    for step in range(1, mid + 1):
        indexes.append(first + (step * inner) // (mid + 1))
    indexes.extend(count - last + offset for offset in range(last))
    seen: set[int] = set()
    out: list[int] = []
    for index in indexes:
        if index in seen or index < 0 or index >= count:
            continue
        seen.add(index)
        out.append(index)
    return out


def _header(decision: ClassificationDecision, units: tuple[ContentUnit, ...]) -> str:
    lines = [
        f"type: {decision.material_type.value}",
        f"subtype: {decision.subtype or '-'}",
        f"units: {len(units)}",
    ]
    if units:
        title = units[0].metadata.get("title")
        package = units[0].metadata.get("package")
        if isinstance(title, str) and title.strip():
            lines.append(f"extracted_title: {title.strip()}")
        if isinstance(package, str) and package.strip():
            lines.append(f"package: {package.strip()}")
        columns = units[0].metadata.get("columns")
        if isinstance(columns, list) and columns:
            lines.append("columns: " + ", ".join(str(item) for item in columns[:24]))
    return "\n".join(lines)


def _label(unit: ContentUnit) -> str:
    path = unit.location.path or unit.unit_id
    if unit.location.page is not None:
        return f"{path} page {unit.location.page}"
    return path


def _is_identity(unit: ContentUnit) -> bool:
    name = Path(unit.location.path or "").name.lower()
    return name in _IDENTITY_NAMES or name.startswith("readme")


def _chunk_index(unit: ContentUnit) -> int:
    value = unit.metadata.get("chunk_index")
    return value if isinstance(value, int) else 0


def _clip(text: str, limit: int) -> str:
    tokens = tokenize(text)
    if len(tokens) <= limit:
        return text.strip()
    return " ".join(tokens[:limit])


def _tokens(text: str) -> int:
    return len(tokenize(text))
