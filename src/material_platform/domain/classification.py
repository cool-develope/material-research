from datetime import datetime
from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.enums import MaterialType


class MaterialClassification(Contract):
    classification_id: UUID
    material_id: UUID
    material_type: MaterialType
    subtype: str | None
    confidence: float = Field(ge=0, le=1)
    classifier: str
    classifier_version: str
    evidence: tuple[str, ...] = ()
    created_at: datetime
