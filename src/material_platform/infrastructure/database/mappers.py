from material_platform.domain import (
    BoundaryEvidence,
    DiscoveryNode,
    DiscoveryRun,
    Material,
    ProcessingRun,
    Source,
)
from material_platform.domain.enums import (
    DiscoveryRole,
    DiscoveryRunStatus,
    MaterialStatus,
    MaterialType,
    NodeKind,
    ProcessingRunStatus,
    SourceStatus,
    SourceType,
)
from material_platform.infrastructure.database.models import (
    DiscoveryNodeRow,
    DiscoveryRunRow,
    MaterialRow,
    ProcessingRunRow,
    SourceRow,
)


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _object_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            result.append({str(key): inner for key, inner in item.items()})
    return result


def source_to_row(source: Source) -> SourceRow:
    return SourceRow(
        source_id=source.source_id,
        source_type=source.source_type.value,
        original_name=source.original_name,
        raw_uri=source.raw_uri,
        sha256=source.sha256,
        size_bytes=source.size_bytes,
        status=source.status.value,
        metadata_=dict(source.metadata),
        created_at=source.created_at,
    )


def source_from_row(row: SourceRow) -> Source:
    return Source(
        source_id=row.source_id,
        source_type=SourceType(row.source_type),
        original_name=row.original_name,
        raw_uri=row.raw_uri,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
        status=SourceStatus(row.status),
        metadata=_object_dict(row.metadata_),
    )


def discovery_run_to_row(run: DiscoveryRun) -> DiscoveryRunRow:
    return DiscoveryRunRow(
        discovery_run_id=run.discovery_run_id,
        source_id=run.source_id,
        discovery_version=run.discovery_version,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


def discovery_run_from_row(row: DiscoveryRunRow) -> DiscoveryRun:
    return DiscoveryRun(
        discovery_run_id=row.discovery_run_id,
        source_id=row.source_id,
        discovery_version=row.discovery_version,
        status=DiscoveryRunStatus(row.status),
        started_at=row.started_at,
        finished_at=row.finished_at,
        error=row.error,
    )


def _evidence_to_json(
    evidence: tuple[BoundaryEvidence, ...],
) -> list[dict[str, object]]:
    return [
        {"rule": item.rule, "value": item.value, "weight": item.weight}
        for item in evidence
    ]


def _evidence_from_json(value: object) -> tuple[BoundaryEvidence, ...]:
    items: list[BoundaryEvidence] = []
    for raw in _object_dicts(value):
        weight_raw = raw["weight"]
        if isinstance(weight_raw, bool) or not isinstance(weight_raw, int | float):
            raise TypeError("evidence weight must be a number")
        items.append(
            BoundaryEvidence(
                rule=str(raw["rule"]),
                value=str(raw["value"]),
                weight=float(weight_raw),
            )
        )
    return tuple(items)


def discovery_node_to_row(node: DiscoveryNode) -> DiscoveryNodeRow:
    return DiscoveryNodeRow(
        node_id=node.node_id,
        discovery_run_id=node.discovery_run_id,
        source_id=node.source_id,
        parent_node_id=node.parent_node_id,
        path=node.path,
        node_kind=node.node_kind.value,
        role=node.role.value,
        depth=node.depth,
        confidence=node.confidence,
        evidence=_evidence_to_json(node.evidence),
        metadata_=dict(node.metadata),
    )


def discovery_node_from_row(row: DiscoveryNodeRow) -> DiscoveryNode:
    return DiscoveryNode(
        node_id=row.node_id,
        source_id=row.source_id,
        discovery_run_id=row.discovery_run_id,
        parent_node_id=row.parent_node_id,
        path=row.path,
        node_kind=NodeKind(row.node_kind),
        role=DiscoveryRole(row.role),
        depth=row.depth,
        confidence=row.confidence,
        evidence=_evidence_from_json(row.evidence),
        metadata=_object_dict(row.metadata_),
    )


def material_to_row(material: Material) -> MaterialRow:
    return MaterialRow(
        material_id=material.material_id,
        source_id=material.source_id,
        discovery_node_id=material.discovery_node_id,
        discovery_version=material.discovery_version,
        name=material.name,
        root_path=material.root_path,
        content_root_uri=material.content_root_uri,
        content_digest=material.content_digest,
        status=material.status.value,
        material_type=material.material_type.value,
        material_subtype=material.material_subtype,
        metadata_=dict(material.metadata),
        created_at=material.created_at,
    )


def material_from_row(row: MaterialRow) -> Material:
    return Material(
        material_id=row.material_id,
        source_id=row.source_id,
        discovery_node_id=row.discovery_node_id,
        discovery_version=row.discovery_version,
        name=row.name,
        root_path=row.root_path,
        content_root_uri=row.content_root_uri,
        content_digest=row.content_digest,
        status=MaterialStatus(row.status),
        created_at=row.created_at,
        material_type=MaterialType(row.material_type),
        material_subtype=row.material_subtype,
        metadata=_object_dict(row.metadata_),
    )


def processing_run_to_row(run: ProcessingRun) -> ProcessingRunRow:
    return ProcessingRunRow(
        processing_run_id=run.processing_run_id,
        material_id=run.material_id,
        stage=run.stage,
        processor_version=run.processor_version,
        status=run.status.value,
        dagster_run_id=run.dagster_run_id,
        claimed_at=run.claimed_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


def processing_run_from_row(row: ProcessingRunRow) -> ProcessingRun:
    return ProcessingRun(
        processing_run_id=row.processing_run_id,
        material_id=row.material_id,
        stage=row.stage,
        processor_version=row.processor_version,
        status=ProcessingRunStatus(row.status),
        claimed_at=row.claimed_at,
        dagster_run_id=row.dagster_run_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error=row.error,
    )
