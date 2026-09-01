from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from material_platform.domain.discovery import BoundaryEvidence, DiscoveryNode
from material_platform.domain.enums import DiscoveryRole, NodeKind


class DiscoveryContext:
    def __init__(
        self,
        *,
        source_id: UUID,
        discovery_run_id: UUID,
        parent_node_id: UUID | None = None,
        depth: int = 0,
        archive_depth: int = 0,
        origin_chain: tuple[str, ...] = (),
        logical_prefix: str = "",
    ) -> None:
        self.source_id = source_id
        self.discovery_run_id = discovery_run_id
        self.parent_node_id = parent_node_id
        self.depth = depth
        self.archive_depth = archive_depth
        self.origin_chain = origin_chain
        self.logical_prefix = logical_prefix
        self.nodes: list[DiscoveryNode] = []

    def child(
        self,
        parent: DiscoveryNode,
        *,
        logical_prefix: str | None = None,
        origin_chain: tuple[str, ...] | None = None,
        archive_depth: int | None = None,
    ) -> DiscoveryContext:
        next_context = DiscoveryContext(
            source_id=self.source_id,
            discovery_run_id=self.discovery_run_id,
            parent_node_id=parent.node_id,
            depth=self.depth + 1,
            archive_depth=(
                self.archive_depth if archive_depth is None else archive_depth
            ),
            origin_chain=(self.origin_chain if origin_chain is None else origin_chain),
            logical_prefix=(
                self.logical_prefix if logical_prefix is None else logical_prefix
            ),
        )
        next_context.nodes = self.nodes
        return next_context

    def logical_path(self, name: str, *, is_directory: bool) -> str:
        leaf = f"{name.rstrip('/')}/" if is_directory else name
        if not self.logical_prefix:
            return leaf
        return f"{self.logical_prefix}{leaf}"

    def record(
        self,
        *,
        path: str,
        node_kind: NodeKind,
        role: DiscoveryRole,
        confidence: float | None = None,
        evidence: tuple[BoundaryEvidence, ...] = (),
        material_hint: str | None = None,
        include_path_in_origin: bool = True,
        local_path: Path | None = None,
        extra: dict[str, object] | None = None,
    ) -> DiscoveryNode:
        origin = self.origin_chain + ((path,) if include_path_in_origin else ())
        metadata: dict[str, object] = {"origin_chain": list(origin)}
        if material_hint is not None:
            metadata["material_hint"] = material_hint
        if local_path is not None:
            metadata["local_path"] = str(local_path.resolve())
        if extra:
            metadata.update(extra)
        node = DiscoveryNode(
            node_id=uuid4(),
            source_id=self.source_id,
            discovery_run_id=self.discovery_run_id,
            parent_node_id=self.parent_node_id,
            path=path,
            node_kind=node_kind,
            role=role,
            depth=self.depth,
            confidence=confidence,
            evidence=evidence,
            metadata=metadata,
        )
        self.nodes.append(node)
        return node
