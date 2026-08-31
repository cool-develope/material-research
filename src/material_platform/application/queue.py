from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from material_platform.domain.enums import ProcessingRunStatus
from material_platform.domain.material import Material
from material_platform.domain.processing import ProcessingRun
from material_platform.infrastructure.database.repositories import (
    MaterialRepository,
    ProcessingRunRepository,
)

_OPEN_RUNS = frozenset(
    {ProcessingRunStatus.CLAIMED, ProcessingRunStatus.RUNNING}
)


def pipeline_run_key(material_id: UUID, pipeline_version: str) -> str:
    return f"{material_id}:{pipeline_version}"


class WorkQueue:
    def __init__(self, session: Session, *, pipeline_version: str) -> None:
        self._session = session
        self._pipeline_version = pipeline_version
        self._materials = MaterialRepository(session)
        self._runs = ProcessingRunRepository(session)

    def claim_pending(self, *, limit: int = 50) -> tuple[Material, ...]:
        claimed = self._materials.claim_pending(limit=limit)
        return tuple(self._ensure_run(item) for item in claimed)

    def claim(self, material_id: UUID) -> Material | None:
        material = self._materials.claim(material_id)
        if material is None:
            return None
        return self._ensure_run(material)

    def _ensure_run(self, material: Material) -> Material:
        latest = self._runs.get_latest(material.material_id)
        if latest is not None and latest.status in _OPEN_RUNS:
            return material
        self._runs.add(
            ProcessingRun(
                processing_run_id=uuid4(),
                material_id=material.material_id,
                stage="pipeline",
                processor_version=self._pipeline_version,
                status=ProcessingRunStatus.CLAIMED,
                claimed_at=datetime.now(UTC),
            )
        )
        self._session.flush()
        return material
