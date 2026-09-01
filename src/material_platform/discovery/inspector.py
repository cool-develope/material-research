from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from material_platform.discovery.classify import classify_path
from material_platform.discovery.formats import FormatAction
from material_platform.discovery.magic import sniff_magic
from material_platform.domain.enums import NodeKind


@dataclass(frozen=True)
class PathInspection:
    path: Path
    node_kind: NodeKind
    size_bytes: int
    format: str = "file"
    material_hint: str | None = None
    peek: dict[str, object] = field(default_factory=dict)

    @property
    def is_archive(self) -> bool:
        return self.node_kind is NodeKind.ARCHIVE

    @property
    def is_file(self) -> bool:
        return self.node_kind is NodeKind.FILE

    @property
    def is_directory(self) -> bool:
        return self.node_kind is NodeKind.DIRECTORY


class PathInspector:
    def inspect(self, path: Path) -> PathInspection:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            return PathInspection(path, NodeKind.DIRECTORY, 0, format="directory")
        if not path.is_file():
            raise ValueError(f"unsupported path: {path}")
        sniffed = sniff_magic(path)
        decision = classify_path(path, sniffed=sniffed)
        size = path.stat().st_size
        if decision.action is FormatAction.EXPAND:
            return PathInspection(
                path, NodeKind.ARCHIVE, size, format=decision.format
            )
        return PathInspection(
            path,
            NodeKind.FILE,
            size,
            format=decision.format,
            material_hint=decision.material_hint,
            peek=dict(decision.peek),
        )
