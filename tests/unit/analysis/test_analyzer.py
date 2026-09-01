from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from material_platform.analysis import ANALYZER, analyze_units
from material_platform.classification import classify_files
from material_platform.domain.enums import MaterialStatus, MaterialType
from material_platform.domain.material import Material
from material_platform.extraction import MaterialFile, extract_units
from tests.unit.discovery.trees import make_python_project
from tests.unit.helpers.pdf import build_text_pdf


def _material(name: str) -> Material:
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


def test_analyze_pdf_extracts_topics() -> None:
    files = (
        MaterialFile(
            path="paper.pdf",
            data=build_text_pdf(["Introduction to materials"]),
        ),
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    analysis = analyze_units(_material("paper.pdf"), decision, units)
    topics = {topic.lower() for topic in analysis.topics}
    assert analysis.analyzer == ANALYZER
    assert "materials" in topics
    assert "introduction" in topics
    assert "Introduction to materials" in analysis.summary


def test_analyze_python_project_finds_handle_request(tmp_path: Path) -> None:
    project = make_python_project(tmp_path / "backend")
    files = tuple(
        MaterialFile(
            path=path.relative_to(project).as_posix(),
            data=path.read_bytes(),
        )
        for path in sorted(project.rglob("*"))
        if path.is_file()
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    analysis = analyze_units(_material("backend"), decision, units)
    by_name = {entity.name: entity for entity in analysis.entities}
    assert decision.material_type is MaterialType.PROJECT
    assert "handle_request" in by_name
    entity = by_name["handle_request"]
    assert entity.kind == "function"
    assert entity.location is not None
    assert entity.location.path == "src/api.py"
