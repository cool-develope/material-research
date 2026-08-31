from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from material_platform.domain import (
    DiscoveryNode,
    DiscoveryRun,
    Material,
    ProcessingRun,
    Source,
)
from material_platform.infrastructure.database.mappers import (
    discovery_node_from_row,
    discovery_node_to_row,
    discovery_run_from_row,
    discovery_run_to_row,
    material_from_row,
    material_to_row,
    processing_run_from_row,
    processing_run_to_row,
    source_from_row,
    source_to_row,
)
from material_platform.infrastructure.database.models import (
    DiscoveryNodeRow,
    DiscoveryRunRow,
    MaterialRow,
    ProcessingRunRow,
    SourceRow,
)


class BaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session


class SourceRepository(BaseRepository):
    def add(self, source: Source) -> None:
        self._session.add(source_to_row(source))

    def get(self, source_id: UUID) -> Source | None:
        row = self._session.get(SourceRow, source_id)
        if row is None:
            return None
        return source_from_row(row)

    def get_by_sha256(self, sha256: str) -> Source | None:
        row = self._session.scalar(select(SourceRow).where(SourceRow.sha256 == sha256))
        if row is None:
            return None
        return source_from_row(row)

    def save(self, source: Source) -> None:
        row = self._session.get(SourceRow, source.source_id)
        if row is None:
            self.add(source)
            return
        row.status = source.status.value
        row.metadata_ = dict(source.metadata)


class DiscoveryRunRepository(BaseRepository):
    def add(self, run: DiscoveryRun) -> None:
        self._session.add(discovery_run_to_row(run))

    def get(self, discovery_run_id: UUID) -> DiscoveryRun | None:
        row = self._session.get(DiscoveryRunRow, discovery_run_id)
        if row is None:
            return None
        return discovery_run_from_row(row)

    def save(self, run: DiscoveryRun) -> None:
        row = self._session.get(DiscoveryRunRow, run.discovery_run_id)
        if row is None:
            self.add(run)
            return
        row.status = run.status.value
        row.finished_at = run.finished_at
        row.error = run.error


class DiscoveryNodeRepository(BaseRepository):
    def add(self, node: DiscoveryNode) -> None:
        self._session.add(discovery_node_to_row(node))

    def add_all(self, nodes: list[DiscoveryNode]) -> None:
        for node in nodes:
            self.add(node)

    def list_for_run(self, discovery_run_id: UUID) -> list[DiscoveryNode]:
        rows = self._session.scalars(
            select(DiscoveryNodeRow).where(
                DiscoveryNodeRow.discovery_run_id == discovery_run_id
            )
        ).all()
        return [discovery_node_from_row(row) for row in rows]


class MaterialRepository(BaseRepository):
    def add(self, material: Material) -> None:
        self._session.add(material_to_row(material))

    def get(self, material_id: UUID) -> Material | None:
        row = self._session.get(MaterialRow, material_id)
        if row is None:
            return None
        return material_from_row(row)

    def get_by_identity(
        self,
        source_id: UUID,
        root_path: str,
        discovery_version: str,
    ) -> Material | None:
        row = self._session.scalar(
            select(MaterialRow).where(
                MaterialRow.source_id == source_id,
                MaterialRow.root_path == root_path,
                MaterialRow.discovery_version == discovery_version,
            )
        )
        if row is None:
            return None
        return material_from_row(row)

    def upsert(self, material: Material) -> Material:
        row = self._session.scalar(
            select(MaterialRow).where(
                MaterialRow.source_id == material.source_id,
                MaterialRow.root_path == material.root_path,
                MaterialRow.discovery_version == material.discovery_version,
            )
        )
        if row is None:
            self.add(material)
            return material
        row.discovery_node_id = material.discovery_node_id
        row.name = material.name
        row.content_root_uri = material.content_root_uri
        row.content_digest = material.content_digest
        row.status = material.status.value
        row.material_type = material.material_type.value
        row.material_subtype = material.material_subtype
        row.metadata_ = dict(material.metadata)
        return material_from_row(row)

    def list_for_source(self, source_id: UUID) -> list[Material]:
        rows = self._session.scalars(
            select(MaterialRow).where(MaterialRow.source_id == source_id)
        ).all()
        return [material_from_row(row) for row in rows]


class ProcessingRunRepository(BaseRepository):
    def add(self, run: ProcessingRun) -> None:
        self._session.add(processing_run_to_row(run))

    def get(self, processing_run_id: UUID) -> ProcessingRun | None:
        row = self._session.get(ProcessingRunRow, processing_run_id)
        if row is None:
            return None
        return processing_run_from_row(row)
