from datetime import datetime
from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.enums import SourceStatus, SourceType

_SHA256 = r"^[a-fA-F0-9]{64}$"


class Source(Contract):
    source_id: UUID
    source_type: SourceType
    original_name: str
    raw_uri: str
    sha256: str = Field(min_length=64, max_length=64, pattern=_SHA256)
    size_bytes: int = Field(ge=0)
    created_at: datetime
    status: SourceStatus = SourceStatus.REGISTERED
    metadata: dict[str, object] = Field(default_factory=dict)
