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


class DiscoveryRunRepository(BaseRepository):
    def add(self, run: DiscoveryRun) -> None:
        self._session.add(discovery_run_to_row(run))

    def get(self, discovery_run_id: UUID) -> DiscoveryRun | None:
        row = self._session.get(DiscoveryRunRow, discovery_run_id)
        if row is None:
            return None
        return discovery_run_from_row(row)


class DiscoveryNodeRepository(BaseRepository):
    def add(self, node: DiscoveryNode) -> None:
        self._session.add(discovery_node_to_row(node))

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


class ProcessingRunRepository(BaseRepository):
    def add(self, run: ProcessingRun) -> None:
        self._session.add(processing_run_to_row(run))

    def get(self, processing_run_id: UUID) -> ProcessingRun | None:
        row = self._session.get(ProcessingRunRow, processing_run_id)
        if row is None:
            return None
        return processing_run_from_row(row)
