from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from material_platform.extraction.common import MaterialFile, decode_text
from material_platform.extraction.project import (
    eligible_project_files,
    file_kind,
    subsystem_of,
)

_IMPORT = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)
_FUNC = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.MULTILINE)
_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE)
_LANG = {
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
}


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    language: str
    subsystem: str
    kind: str
    imports: tuple[str, ...]
    symbols: tuple[str, ...]


def scan_project(files: tuple[MaterialFile, ...]) -> tuple[FileRecord, ...]:
    records: list[FileRecord] = []
    for item in eligible_project_files(files):
        path = Path(item.path)
        text = decode_text(item.data)
        imports = tuple(
            (match.group(1) or match.group(2) or "").split(".", maxsplit=1)[0]
            for match in _IMPORT.finditer(text)
            if (match.group(1) or match.group(2))
        )[:12]
        symbols = tuple(
            list(_FUNC.findall(text)[:8]) + list(_CLASS.findall(text)[:8])
        )
        records.append(
            FileRecord(
                path=item.path,
                size=len(item.data),
                language=_LANG.get(path.suffix.lower(), path.suffix.lstrip(".")),
                subsystem=subsystem_of(item.path),
                kind=file_kind(item),
                imports=imports,
                symbols=symbols,
            )
        )
    return tuple(records)
