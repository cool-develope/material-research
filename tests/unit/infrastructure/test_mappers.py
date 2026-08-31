from datetime import UTC, datetime
from uuid import uuid4

from material_platform.domain import (
    BoundaryEvidence,
    DiscoveryNode,
    DiscoveryRole,
    Material,
    MaterialStatus,
    NodeKind,
    Source,
    SourceStatus,
    SourceType,
)
from material_platform.infrastructure.database.mappers import (
    discovery_node_from_row,
    discovery_node_to_row,
    material_from_row,
    material_to_row,
    source_from_row,
    source_to_row,
)

SHA256 = "b" * 64


def test_source_round_trip_preserves_status() -> None:
    source = Source(
        source_id=uuid4(),
        source_type=SourceType.ARCHIVE,
        original_name="research.zip",
        raw_uri="raw/s1/original",
        sha256=SHA256,
        size_bytes=10,
        created_at=datetime.now(UTC),
        status=SourceStatus.REGISTERED,
        metadata={"origin": "upload"},
    )

    restored = source_from_row(source_to_row(source))

    assert restored == source


def test_discovery_node_round_trips_evidence() -> None:
    node = DiscoveryNode(
        node_id=uuid4(),
        source_id=uuid4(),
        discovery_run_id=uuid4(),
        path="backend/",
        node_kind=NodeKind.DIRECTORY,
        role=DiscoveryRole.MATERIAL,
        confidence=0.98,
        evidence=(
            BoundaryEvidence(rule="root_marker", value="pyproject.toml", weight=1.0),
        ),
        metadata={"hint": "python_project"},
    )

    restored = discovery_node_from_row(discovery_node_to_row(node))

    assert restored == node


def test_material_round_trip_includes_discovery_version() -> None:
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

    restored = material_from_row(material_to_row(material))

    assert restored.discovery_version == "boundary-v1"
    assert restored == material
