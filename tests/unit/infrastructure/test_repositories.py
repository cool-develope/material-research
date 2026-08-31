from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from material_platform.domain import (
    DiscoveryNode,
    DiscoveryRole,
    DiscoveryRun,
    DiscoveryRunStatus,
    Material,
    MaterialStatus,
    NodeKind,
    Source,
    SourceType,
)
from material_platform.infrastructure.database.repositories import (
    DiscoveryNodeRepository,
    DiscoveryRunRepository,
    MaterialRepository,
    SourceRepository,
)

SHA256 = "c" * 64


def _source() -> Source:
    return Source(
        source_id=uuid4(),
        source_type=SourceType.ARCHIVE,
        original_name="research.zip",
        raw_uri="raw/s1/original",
        sha256=SHA256,
        size_bytes=10,
        created_at=datetime.now(UTC),
    )


def _seed_material_graph(session: Session) -> tuple[Source, DiscoveryNode]:
    source = _source()
    run = DiscoveryRun(
        discovery_run_id=uuid4(),
        source_id=source.source_id,
        discovery_version="boundary-v1",
        status=DiscoveryRunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    node = DiscoveryNode(
        node_id=uuid4(),
        source_id=source.source_id,
        discovery_run_id=run.discovery_run_id,
        path="backend/",
        node_kind=NodeKind.DIRECTORY,
        role=DiscoveryRole.MATERIAL,
    )
    SourceRepository(session).add(source)
    DiscoveryRunRepository(session).add(run)
    DiscoveryNodeRepository(session).add(node)
    session.flush()
    return source, node


def test_source_repository_round_trip(session: Session) -> None:
    source = _source()
    repo = SourceRepository(session)

    repo.add(source)
    session.flush()

    loaded = repo.get(source.source_id)
    assert loaded is not None
    assert loaded.source_id == source.source_id
    assert loaded.original_name == "research.zip"


def test_material_identity_is_unique(session: Session) -> None:
    source, node = _seed_material_graph(session)
    other_node = DiscoveryNode(
        node_id=uuid4(),
        source_id=source.source_id,
        discovery_run_id=node.discovery_run_id,
        path="backend/",
        node_kind=NodeKind.DIRECTORY,
        role=DiscoveryRole.MATERIAL,
    )
    DiscoveryNodeRepository(session).add(other_node)
    session.flush()

    repo = MaterialRepository(session)
    created_at = datetime.now(UTC)
    repo.add(
        Material(
            material_id=uuid4(),
            source_id=source.source_id,
            discovery_node_id=node.node_id,
            discovery_version="boundary-v1",
            name="backend",
            root_path="backend/",
            content_root_uri="materials/m1/content",
            content_digest=SHA256,
            status=MaterialStatus.DISCOVERED,
            created_at=created_at,
        )
    )
    session.flush()

    repo.add(
        Material(
            material_id=uuid4(),
            source_id=source.source_id,
            discovery_node_id=other_node.node_id,
            discovery_version="boundary-v1",
            name="backend",
            root_path="backend/",
            content_root_uri="materials/m2/content",
            content_digest=SHA256,
            status=MaterialStatus.DISCOVERED,
            created_at=created_at,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_material_get_by_identity(session: Session) -> None:
    source, node = _seed_material_graph(session)
    material = Material(
        material_id=uuid4(),
        source_id=source.source_id,
        discovery_node_id=node.node_id,
        discovery_version="boundary-v1",
        name="backend",
        root_path="backend/",
        content_root_uri="materials/m1/content",
        content_digest=SHA256,
        status=MaterialStatus.DISCOVERED,
        created_at=datetime.now(UTC),
    )
    repo = MaterialRepository(session)
    repo.add(material)
    session.flush()

    loaded = repo.get_by_identity(
        source.source_id,
        "backend/",
        "boundary-v1",
    )
    assert loaded is not None
    assert loaded.material_id == material.material_id
