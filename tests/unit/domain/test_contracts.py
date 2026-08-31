from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from material_platform.domain import (
    BoundaryEvidence,
    ContentLocation,
    ContentUnit,
    DiscoveryManifest,
    DiscoveryNode,
    DiscoveryRole,
    DiscoveryRun,
    DiscoveryRunStatus,
    Material,
    MaterialClassification,
    MaterialProvenance,
    MaterialStatus,
    MaterialType,
    NodeKind,
    ResearchMaterial,
    Source,
    SourceStatus,
    SourceType,
)

SHA256 = "a" * 64


def test_source_type_uses_archive_not_zip() -> None:
    assert SourceType.ARCHIVE == "archive"
    assert not hasattr(SourceType, "ZIP")


def test_material_status_includes_processing() -> None:
    assert list(MaterialStatus) == [
        MaterialStatus.DISCOVERED,
        MaterialStatus.PROCESSING,
        MaterialStatus.CLASSIFIED,
        MaterialStatus.EXTRACTED,
        MaterialStatus.ANALYZED,
        MaterialStatus.INDEXED,
        MaterialStatus.READY,
        MaterialStatus.FAILED,
    ]


def test_contracts_are_frozen() -> None:
    source = Source(
        source_id=uuid4(),
        source_type=SourceType.ARCHIVE,
        original_name="research.zip",
        raw_uri="raw/s1/original",
        sha256=SHA256,
        size_bytes=12,
        created_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        source.original_name = "other.zip"  # type: ignore[misc]


def test_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Source(
            source_id=uuid4(),
            source_type=SourceType.FILE,
            original_name="paper.pdf",
            raw_uri="raw/s1/original",
            sha256=SHA256,
            size_bytes=1,
            created_at=datetime.now(UTC),
            extra_field="nope",  # type: ignore[call-arg]
        )


def test_source_defaults_to_registered() -> None:
    source = Source(
        source_id=uuid4(),
        source_type=SourceType.FILE,
        original_name="paper.pdf",
        raw_uri="raw/s1/original",
        sha256=SHA256,
        size_bytes=1,
        created_at=datetime.now(UTC),
    )
    assert source.status is SourceStatus.REGISTERED
    with pytest.raises(ValidationError):
        Source(
            source_id=uuid4(),
            source_type=SourceType.FILE,
            original_name="paper.pdf",
            raw_uri="raw/s1/original",
            sha256="not-a-hash",
            size_bytes=1,
            created_at=datetime.now(UTC),
        )


def test_discovery_node_confidence_is_bounded() -> None:
    ids = {"node_id": uuid4(), "source_id": uuid4(), "discovery_run_id": uuid4()}

    node = DiscoveryNode(
        **ids,
        path="backend/",
        node_kind=NodeKind.DIRECTORY,
        role=DiscoveryRole.MATERIAL,
        confidence=0.98,
        evidence=(
            BoundaryEvidence(rule="root_marker", value="pyproject.toml", weight=1.0),
        ),
    )
    assert node.role is DiscoveryRole.MATERIAL

    with pytest.raises(ValidationError):
        DiscoveryNode(
            **ids,
            path="backend/",
            node_kind=NodeKind.DIRECTORY,
            confidence=1.5,
        )


def test_discovery_manifest_holds_stable_version() -> None:
    source_id = uuid4()
    run_id = uuid4()
    node = DiscoveryNode(
        node_id=uuid4(),
        source_id=source_id,
        discovery_run_id=run_id,
        path="research.zip",
        node_kind=NodeKind.ARCHIVE,
        role=DiscoveryRole.CONTAINER,
    )
    manifest = DiscoveryManifest(
        source_id=source_id,
        discovery_run_id=run_id,
        discovery_version="boundary-v1",
        nodes=(node,),
    )
    assert manifest.discovery_version == "boundary-v1"
    assert len(manifest.nodes) == 1


def test_discovery_run_tracks_lifecycle() -> None:
    run = DiscoveryRun(
        discovery_run_id=uuid4(),
        source_id=uuid4(),
        discovery_version="boundary-v1",
        status=DiscoveryRunStatus.RUNNING,
        started_at=datetime.now(UTC),
    )
    assert run.finished_at is None
    assert run.error is None


def test_material_identity_includes_discovery_version() -> None:
    material = Material(
        material_id=uuid4(),
        source_id=uuid4(),
        discovery_node_id=uuid4(),
        discovery_version="boundary-v1",
        name="backend",
        root_path="backend/",
        content_root_uri="materials/m1/content",
        content_digest=SHA256,
        status=MaterialStatus.DISCOVERED,
        created_at=datetime.now(UTC),
    )

    assert material.material_type is MaterialType.UNKNOWN
    assert material.discovery_version == "boundary-v1"
    assert material.status is MaterialStatus.DISCOVERED


def test_research_material_uses_material_type_and_locations() -> None:
    material_id = uuid4()
    source_id = uuid4()
    research = ResearchMaterial(
        material_id=material_id,
        material_type=MaterialType.DOCUMENT,
        material_subtype="pdf",
        title="paper.pdf",
        summary="1 page PDF",
        content_units=(
            ContentUnit(
                unit_id="paper.pdf:page:1",
                type="page",
                content="Introduction",
                location=ContentLocation(path="paper.pdf", page=1),
                digest=SHA256,
            ),
        ),
        provenance=MaterialProvenance(
            source_id=source_id,
            root_path="paper.pdf",
            origin_chain=("research.zip", "paper.pdf"),
        ),
    )

    assert research.material_type is MaterialType.DOCUMENT
    assert research.content_units[0].location.page == 1

    classification = MaterialClassification(
        classification_id=uuid4(),
        material_id=material_id,
        material_type=MaterialType.PROJECT,
        subtype="python",
        confidence=0.98,
        classifier="deterministic",
        classifier_version="v1",
        evidence=("root marker:pyproject.toml",),
        created_at=datetime.now(UTC),
    )
    assert classification.subtype == "python"

    with pytest.raises(ValidationError):
        ContentLocation(page=0)
