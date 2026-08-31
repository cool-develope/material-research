from datetime import datetime
from uuid import UUID

from material_platform.domain.base import Contract


class MaterialArtifact(Contract):
    artifact_id: UUID
    material_id: UUID
    artifact_type: str
    processor: str
    processor_version: str
    storage_uri: str
    sha256: str
    created_at: datetime
