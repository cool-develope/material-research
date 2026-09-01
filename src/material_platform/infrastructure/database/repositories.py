from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Select

from material_platform.domain import (
    DiscoveryNode,
    DiscoveryRun,
    Material,
    MaterialArtifact,
    MaterialClassification,
    MaterialStatus,
    ProcessingRun,
    Source,
)
from material_platform.infrastructure.database.mappers import (
    artifact_from_row,
    artifact_to_row,
    classification_from_row,
    classification_to_row,
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
    MaterialArtifactRow,
    MaterialClassificationRow,
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

    def list_by_status(self, status: MaterialStatus) -> list[Material]:
        rows = self._session.scalars(
            select(MaterialRow).where(MaterialRow.status == status.value)
        ).all()
        return [material_from_row(row) for row in rows]

    def claim_pending(self, *, limit: int) -> list[Material]:
        stmt: Select[tuple[MaterialRow]] = (
            select(MaterialRow)
            .where(MaterialRow.status == MaterialStatus.DISCOVERED.value)
            .order_by(MaterialRow.created_at.asc())
            .limit(limit)
        )
        stmt = self._lock(stmt)
        rows = list(self._session.scalars(stmt).all())
        claimed: list[Material] = []
        for row in rows:
            row.status = MaterialStatus.PROCESSING.value
            claimed.append(material_from_row(row))
        self._session.flush()
        return claimed

    def claim(self, material_id: UUID) -> Material | None:
        stmt: Select[tuple[MaterialRow]] = select(MaterialRow).where(
            MaterialRow.material_id == material_id
        )
        stmt = self._lock(stmt)
        row = self._session.scalar(stmt)
        if row is None:
            return None
        if row.status == MaterialStatus.PROCESSING.value:
            return material_from_row(row)
        if row.status not in {
            MaterialStatus.DISCOVERED.value,
            MaterialStatus.FAILED.value,
            MaterialStatus.READY.value,
        }:
            return None
        row.status = MaterialStatus.PROCESSING.value
        self._session.flush()
        return material_from_row(row)

    def _lock(self, stmt: Select[tuple[MaterialRow]]) -> Select[tuple[MaterialRow]]:
        bind = self._session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            return stmt.with_for_update(skip_locked=True)
        return stmt

    def save(self, material: Material) -> None:
        row = self._session.get(MaterialRow, material.material_id)
        if row is None:
            self.add(material)
            return
        row.status = material.status.value
        row.material_type = material.material_type.value
        row.material_subtype = material.material_subtype
        row.metadata_ = dict(material.metadata)


class ClassificationRepository(BaseRepository):
    def add(self, classification: MaterialClassification) -> None:
        self._session.add(classification_to_row(classification))

    def upsert(self, classification: MaterialClassification) -> MaterialClassification:
        row = self._session.scalar(
            select(MaterialClassificationRow).where(
                MaterialClassificationRow.material_id == classification.material_id,
                MaterialClassificationRow.classifier == classification.classifier,
                MaterialClassificationRow.classifier_version
                == classification.classifier_version,
            )
        )
        if row is None:
            self.add(classification)
            return classification
        row.material_type = classification.material_type.value
        row.material_subtype = classification.subtype
        row.confidence = classification.confidence
        row.evidence = list(classification.evidence)
        row.created_at = classification.created_at
        return classification_from_row(row)

    def get_latest(self, material_id: UUID) -> MaterialClassification | None:
        row = self._session.scalar(
            select(MaterialClassificationRow)
            .where(MaterialClassificationRow.material_id == material_id)
            .order_by(MaterialClassificationRow.created_at.desc())
        )
        if row is None:
            return None
        return classification_from_row(row)


class ArtifactRepository(BaseRepository):
    def add(self, artifact: MaterialArtifact) -> None:
        self._session.add(artifact_to_row(artifact))

    def upsert(self, artifact: MaterialArtifact) -> MaterialArtifact:
        row = self._session.scalar(
            select(MaterialArtifactRow).where(
                MaterialArtifactRow.material_id == artifact.material_id,
                MaterialArtifactRow.artifact_type == artifact.artifact_type,
                MaterialArtifactRow.processor == artifact.processor,
                MaterialArtifactRow.processor_version == artifact.processor_version,
            )
        )
        if row is None:
            self.add(artifact)
            return artifact
        row.storage_uri = artifact.storage_uri
        row.sha256 = artifact.sha256
        row.created_at = artifact.created_at
        return artifact_from_row(row)

    def get_by_identity(
        self,
        material_id: UUID,
        artifact_type: str,
        processor: str,
        processor_version: str,
    ) -> MaterialArtifact | None:
        row = self._session.scalar(
            select(MaterialArtifactRow).where(
                MaterialArtifactRow.material_id == material_id,
                MaterialArtifactRow.artifact_type == artifact_type,
                MaterialArtifactRow.processor == processor,
                MaterialArtifactRow.processor_version == processor_version,
            )
        )
        if row is None:
            return None
        return artifact_from_row(row)


class ProcessingRunRepository(BaseRepository):
    def add(self, run: ProcessingRun) -> None:
        self._session.add(processing_run_to_row(run))

    def get(self, processing_run_id: UUID) -> ProcessingRun | None:
        row = self._session.get(ProcessingRunRow, processing_run_id)
        if row is None:
            return None
        return processing_run_from_row(row)

    def save(self, run: ProcessingRun) -> None:
        row = self._session.get(ProcessingRunRow, run.processing_run_id)
        if row is None:
            self.add(run)
            return
        row.status = run.status.value
        row.dagster_run_id = run.dagster_run_id
        row.started_at = run.started_at
        row.finished_at = run.finished_at
        row.error = run.error

    def get_latest(self, material_id: UUID) -> ProcessingRun | None:
        row = self._session.scalar(
            select(ProcessingRunRow)
            .where(ProcessingRunRow.material_id == material_id)
            .order_by(ProcessingRunRow.claimed_at.desc())
        )
        if row is None:
            return None
        return processing_run_from_row(row)

