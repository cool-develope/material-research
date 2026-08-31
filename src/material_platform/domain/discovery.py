from datetime import datetime
from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.enums import (
    DiscoveryRole,
    DiscoveryRunStatus,
    NodeKind,
)


class BoundaryEvidence(Contract):
    rule: str
    value: str
    weight: float = Field(ge=0, le=1)


class DiscoveryNode(Contract):
    node_id: UUID
    source_id: UUID
    discovery_run_id: UUID
    path: str
    node_kind: NodeKind
    parent_node_id: UUID | None = None
    role: DiscoveryRole = DiscoveryRole.UNKNOWN
    depth: int = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: tuple[BoundaryEvidence, ...] = ()
    metadata: dict[str, object] = Field(default_factory=dict)


class DiscoveryRun(Contract):
    discovery_run_id: UUID
    source_id: UUID
    discovery_version: str
    status: DiscoveryRunStatus
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class DiscoveryManifest(Contract):
    source_id: UUID
    discovery_run_id: UUID
    discovery_version: str
    nodes: tuple[DiscoveryNode, ...]
