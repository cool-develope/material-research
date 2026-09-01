from __future__ import annotations

from uuid import UUID, uuid5

from qdrant_client.http import models

from material_platform.domain.research_material import ContentUnit, ResearchMaterial
from material_platform.infrastructure.embedding.protocol import EmbeddedText
from material_platform.infrastructure.qdrant.store import DENSE_NAME, SPARSE_NAME

INDEX_VERSION = "v2"
_NAMESPACE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def point_id(material_id: UUID, unit_id: str) -> str:
    return str(uuid5(_NAMESPACE, f"{material_id}:{unit_id}:{INDEX_VERSION}"))


def unit_text(research: ResearchMaterial, unit: ContentUnit) -> str:
    extra = _meta_text(research.metadata, unit.metadata)
    return f"{research.title} {extra} {unit.content}".strip()


def make_point(
    research: ResearchMaterial,
    unit: ContentUnit,
    embedded: EmbeddedText,
) -> models.PointStruct:
    location = unit.location
    return models.PointStruct(
        id=point_id(research.material_id, unit.unit_id),
        vector={
            DENSE_NAME: list(embedded.dense),
            SPARSE_NAME: models.SparseVector(
                indices=list(embedded.sparse_indices),
                values=list(embedded.sparse_values),
            ),
        },
        payload=_payload(research, unit, location.path),
    )


def _payload(
    research: ResearchMaterial,
    unit: ContentUnit,
    path: str | None,
) -> dict[str, object]:
    location = unit.location
    payload: dict[str, object] = {
        "level": "content_unit",
        "material_id": str(research.material_id),
        "source_id": str(research.provenance.source_id),
        "unit_id": unit.unit_id,
        "index_version": INDEX_VERSION,
        "material_type": research.material_type.value,
        "unit_type": unit.type,
        "title": research.title,
        "content": unit.content,
    }
    if research.material_subtype:
        payload["material_subtype"] = research.material_subtype
    if path:
        payload["path"] = path
    if location.page is not None:
        payload["page"] = location.page
    if location.line_start is not None:
        payload["line_start"] = location.line_start
    if location.line_end is not None:
        payload["line_end"] = location.line_end
    if location.section:
        payload["section"] = location.section
    language = research.metadata.get("language")
    if isinstance(language, str) and language:
        payload["language"] = language
    strategy = unit.metadata.get("strategy")
    if isinstance(strategy, str) and strategy:
        payload["strategy"] = strategy
    chunk_index = unit.metadata.get("chunk_index")
    if isinstance(chunk_index, int):
        payload["chunk_index"] = chunk_index
    return payload


_META_KEYS = ("title", "author", "package", "version", "language", "summary")


def _meta_text(*sources: dict[str, object]) -> str:
    parts: list[str] = []
    for source in sources:
        for key in _META_KEYS:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        for key in ("dependencies", "modules", "columns"):
            value = source.get(key)
            if isinstance(value, list):
                parts.extend(str(item) for item in value[:24] if item)
    return " ".join(parts)
