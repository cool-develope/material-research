from datetime import datetime
from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.enums import MaterialStatus, MaterialType


class Material(Contract):
    material_id: UUID
    source_id: UUID
    discovery_node_id: UUID
    discovery_version: str
    name: str
    root_path: str
    content_root_uri: str
    content_digest: str
    status: MaterialStatus
    created_at: datetime
    material_type: MaterialType = MaterialType.UNKNOWN
    material_subtype: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
