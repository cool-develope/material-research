from __future__ import annotations

from pathlib import Path

from material_platform.discovery.formats import (
    FormatAction,
    FormatDecision,
    suffix_match,
    type_from_hint,
)
from material_platform.discovery.peek import (
    ArtifactPeek,
    peek_jar,
    peek_npm_tarball,
    peek_nuget,
    peek_wheel,
)
from material_platform.domain.enums import NodeKind

_MAGIC_FILE = {
    "pe": "binary",
    "elf": "binary",
    "macho": "binary",
    "ole": "installer",
}
_ARTIFACT_PEEK = {
    "python_wheel": peek_wheel,
    "python_egg": peek_wheel,
    "java_jar": peek_jar,
    "java_war": peek_jar,
    "nuget": peek_nuget,
}


def classify_path(path: Path, *, sniffed: str | None) -> FormatDecision:
    matched = suffix_match(path.name)
    if matched is not None:
        return _from_suffix(path, matched[0], matched[1])
    if sniffed == "zip":
        return FormatDecision(FormatAction.EXPAND, NodeKind.ARCHIVE, "zip")
    if sniffed in {"gzip", "tar", "7z"}:
        return FormatDecision(FormatAction.EXPAND, NodeKind.ARCHIVE, sniffed)
    if sniffed in _MAGIC_FILE:
        kind = _MAGIC_FILE[sniffed]
        return FormatDecision(
            FormatAction.FILE, NodeKind.FILE, kind, material_hint=kind
        )
    return FormatDecision(FormatAction.FILE, NodeKind.FILE, "file")


def _from_suffix(path: Path, action: FormatAction, kind: str) -> FormatDecision:
    if path.name.lower().endswith(".tgz"):
        npm = peek_npm_tarball(path)
        if npm is not None:
            return _artifact("node_tarball", npm)
    if action is FormatAction.ARTIFACT:
        peeker = _ARTIFACT_PEEK.get(kind, peek_nuget)
        return _artifact(kind, peeker(path))
    if action is FormatAction.EXPAND:
        return FormatDecision(
            action=action, node_kind=NodeKind.ARCHIVE, format=kind
        )
    hint = kind if type_from_hint(kind) is not None else None
    return FormatDecision(
        action=FormatAction.FILE,
        node_kind=NodeKind.FILE,
        format=kind,
        material_hint=hint,
    )


def _artifact(kind: str, peek: ArtifactPeek) -> FormatDecision:
    return FormatDecision(
        action=FormatAction.ARTIFACT,
        node_kind=NodeKind.FILE,
        format=kind,
        material_hint=kind,
        peek={
            "artifact_title": peek.title,
            "artifact_summary": peek.summary,
            "artifact_evidence": list(peek.evidence),
            **peek.metadata,
        },
    )
