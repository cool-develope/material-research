from __future__ import annotations

import hashlib
from pathlib import Path

from material_platform.discovery.formats import FormatAction, suffix_match
from material_platform.discovery.skips import is_skipped_name


def list_source_archives(directory: Path) -> list[Path]:
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))
    found: list[Path] = []
    for item in directory.iterdir():
        if not item.is_file() or is_skipped_name(item.name):
            continue
        matched = suffix_match(item.name)
        if matched is None:
            continue
        action, _kind = matched
        if action is FormatAction.EXPAND:
            found.append(item.resolve())
    return sorted(found)


def archive_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def ingest_run_key(path: Path, fingerprint: str) -> str:
    digest = hashlib.sha256(f"{path.resolve()}:{fingerprint}".encode()).hexdigest()
    return f"ingest:{path.name}:{digest[:16]}"


def ingest_source_run_config(path: Path) -> dict[str, object]:
    return {"ops": {"ingest_source": {"config": {"path": str(path.resolve())}}}}
