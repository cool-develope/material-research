from datetime import datetime
from uuid import UUID

from material_platform.domain.base import Contract
from material_platform.domain.enums import ProcessingRunStatus


class ProcessingRun(Contract):
    processing_run_id: UUID
    material_id: UUID
    stage: str
    processor_version: str
    status: ProcessingRunStatus
    claimed_at: datetime
    dagster_run_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
