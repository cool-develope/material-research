from datetime import UTC, datetime
from uuid import uuid4

from material_platform.classification.deterministic import ClassificationDecision
from material_platform.domain.enums import MaterialStatus, MaterialType
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentLocation, ContentUnit


def fake_material(name: str = "paper.pdf") -> Material:
    return Material(
        material_id=uuid4(),
        source_id=uuid4(),
        discovery_node_id=uuid4(),
        discovery_version="boundary-v1",
        name=name,
        root_path=name,
        content_root_uri="materials/m1/content",
        content_digest="a" * 64,
        status=MaterialStatus.DISCOVERED,
        created_at=datetime.now(UTC),
    )


def page_unit(page: int, content: str) -> ContentUnit:
    return ContentUnit(
        unit_id=f"paper.pdf:page:{page}",
        type="page",
        content=content,
        location=ContentLocation(path="paper.pdf", page=page),
        digest="a" * 64,
        metadata={"strategy": "document.pages", "chunk_index": page - 1},
    )


def file_unit(path: str, content: str) -> ContentUnit:
    return ContentUnit(
        unit_id=path,
        type="file",
        content=content,
        location=ContentLocation(path=path, line_start=1, line_end=2),
        digest="b" * 64,
        metadata={"strategy": "code.file", "chunk_index": 0},
    )


def document_decision() -> ClassificationDecision:
    return ClassificationDecision(MaterialType.DOCUMENT, "pdf", 1.0, ())


def project_decision() -> ClassificationDecision:
    return ClassificationDecision(MaterialType.PROJECT, "python", 1.0, ())


class StubLlm:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {
            "title": "ignored title",
            "summary": "A survey of alloys for research use.",
            "purpose": "document for research reading",
            "topics": ["alloys", "materials"],
            "technologies": [],
            "research_relevance": 0.8,
        }
        self.error = error
        self.prompts: list[str] = []

    def complete_json(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.payload
