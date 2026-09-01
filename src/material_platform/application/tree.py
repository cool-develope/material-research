from collections import defaultdict
from uuid import UUID

from material_platform.application.process_material import ProcessResult
from material_platform.domain.discovery import DiscoveryManifest, DiscoveryNode
from material_platform.domain.enums import DiscoveryRole
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentLocation, ContentUnit
from material_platform.domain.source import Source

_LOCATION_LIST = 4
_SKIP_LIST = 5


def format_ingest_report(
    source: Source,
    manifest: DiscoveryManifest,
    materials: tuple[Material, ...],
) -> str:
    labels = _assign_labels(manifest.nodes)
    children = _children(manifest.nodes)
    lines = ["SOURCE", f"S1 {source.original_name}", "", "DISCOVERY"]

    roots = children.get(None, [])
    for node in roots:
        lines.extend(_render(node, children, labels, prefix="", is_last=True))

    lines.extend(["", "MATERIALS"])
    material_by_path = {item.root_path: item for item in materials}
    for node in manifest.nodes:
        if node.role is not DiscoveryRole.MATERIAL:
            continue
        material = material_by_path.get(node.path)
        kind = _candidate_kind(node, material)
        lines.append(f"{labels[node.node_id]} {kind} candidate")

    return "\n".join(lines) + "\n"


def format_process_report(
    manifest: DiscoveryManifest,
    results: tuple[ProcessResult, ...],
) -> str:
    labels = _assign_labels(manifest.nodes)
    by_path = {item.material.root_path: item for item in results}
    lines = ["", "RESEARCH"]
    for node in manifest.nodes:
        if node.role is not DiscoveryRole.MATERIAL:
            continue
        result = by_path.get(node.path)
        if result is None:
            continue
        research = result.research
        label = labels[node.node_id]
        count = len(research.content_units)
        noun = "unit" if count == 1 else "units"
        lines.append(
            f"{label} {research.title}  {research.material_type.value}  "
            f"{count} {noun}  {research.summary}"
        )
        keywords = _keywords_line(result.analysis.topics)
        if keywords is not None:
            lines.append(keywords)
        lines.extend(_location_lines(research.content_units))
        skipped = _skipped_line(research.metadata.get("skipped"))
        if skipped is not None:
            lines.append(skipped)
    return "\n".join(lines) + "\n"


def format_location(location: ContentLocation) -> str:
    path = location.path or ""
    if location.page is not None:
        return f"{path} page {location.page}"
    if location.line_start is not None and location.line_end is not None:
        return f"{path} lines {location.line_start}-{location.line_end}"
    return path


def _location_lines(units: tuple[ContentUnit, ...]) -> list[str]:
    if not units:
        return []
    if len(units) <= _LOCATION_LIST:
        return [f"    {format_location(unit.location)}" for unit in units]
    first = format_location(units[0].location)
    last = format_location(units[-1].location)
    return [f"    {first} … {last}"]


def _keywords_line(topics: tuple[str, ...]) -> str | None:
    names = [item.strip() for item in topics if item.strip()]
    if not names:
        return None
    return f"    keywords: {', '.join(names[:12])}"


def _skipped_line(value: object) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    paths = [str(item) for item in value]
    shown = paths[:_SKIP_LIST]
    extra = len(paths) - len(shown)
    text = ", ".join(shown)
    if extra > 0:
        text = f"{text} +{extra} more"
    return f"    skipped: {text}"


def _candidate_kind(node: DiscoveryNode, material: Material | None) -> str:
    if material is not None:
        return material.material_type.value
    hint = node.metadata.get("material_hint")
    if not isinstance(hint, str):
        return "unknown"
    if hint.endswith("_project"):
        return "project"
    if hint == "csv_dataset":
        return "dataset"
    return hint


def _children(
    nodes: tuple[DiscoveryNode, ...],
) -> dict[UUID | None, list[DiscoveryNode]]:
    mapping: dict[UUID | None, list[DiscoveryNode]] = defaultdict(list)
    for node in nodes:
        mapping[node.parent_node_id].append(node)
    return mapping


def _assign_labels(nodes: tuple[DiscoveryNode, ...]) -> dict[UUID, str]:
    labels: dict[UUID, str] = {}
    containers = 0
    materials = 0
    for node in nodes:
        if node.role is DiscoveryRole.MATERIAL:
            materials += 1
            labels[node.node_id] = f"M{materials}"
        else:
            containers += 1
            labels[node.node_id] = f"C{containers}"
    return labels


def _render(
    node: DiscoveryNode,
    children: dict[UUID | None, list[DiscoveryNode]],
    labels: dict[UUID, str],
    *,
    prefix: str,
    is_last: bool,
) -> list[str]:
    label = labels[node.node_id]
    role = node.role.value.upper()
    if prefix == "" and node.parent_node_id is None:
        line = f"{label} {node.path:<28} {role}"
        child_prefix = ""
    else:
        branch = "└── " if is_last else "├── "
        line = f"{prefix}{branch}{label} {node.path:<28} {role}"
        child_prefix = prefix + ("    " if is_last else "│   ")

    lines = [line]
    kids = children.get(node.node_id, [])
    for index, child in enumerate(kids):
        lines.extend(
            _render(
                child,
                children,
                labels,
                prefix=child_prefix,
                is_last=index == len(kids) - 1,
            )
        )
    return lines
