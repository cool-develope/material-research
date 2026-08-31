from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import is_zipfile

from material_platform.domain.enums import NodeKind


@dataclass(frozen=True)
class PathInspection:
    path: Path
    node_kind: NodeKind
    size_bytes: int

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
            return PathInspection(
                path=path,
                node_kind=NodeKind.DIRECTORY,
                size_bytes=0,
            )

        if not path.is_file():
            raise ValueError(f"unsupported path: {path}")

        size_bytes = path.stat().st_size
        if is_zipfile(path):
            return PathInspection(
                path=path,
                node_kind=NodeKind.ARCHIVE,
                size_bytes=size_bytes,
            )

        return PathInspection(
            path=path,
            node_kind=NodeKind.FILE,
            size_bytes=size_bytes,
        )
