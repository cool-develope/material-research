from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from material_platform.discovery.archive import ArchiveLimits, UnsafeArchiveError

_CHUNK = 64 * 1024
_JUNK_DIRS = frozenset({"__MACOSX"})
_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db"})


def check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise UnsafeArchiveError("archive expansion timed out")


def deadline_for(limits: ArchiveLimits) -> float | None:
    if limits.timeout_seconds <= 0:
        return None
    return time.monotonic() + limits.timeout_seconds


def validate_member_name(name: str) -> PurePosixPath:
    if "\x00" in name:
        raise UnsafeArchiveError("NUL in archive path")
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or path.anchor:
        raise UnsafeArchiveError(f"absolute archive path: {name}")
    if ".." in path.parts:
        raise UnsafeArchiveError(f"path traversal: {name}")
    return path


def is_junk_name(name: str) -> bool:
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if any(part in _JUNK_DIRS for part in parts):
        return True
    return bool(parts) and parts[-1] in _JUNK_FILES


def target_path(destination: Path, member_name: str) -> Path:
    relative = validate_member_name(member_name)
    target = destination.joinpath(*relative.parts).resolve()
    if not target.is_relative_to(destination):
        raise UnsafeArchiveError(f"path escaped destination: {member_name}")
    return target


def write_limited(
    source: Callable[[int], bytes],
    target: Path,
    *,
    limits: ArchiveLimits,
    deadline: float | None,
    name: str,
) -> int:
    written = 0
    with target.open("xb") as dst:
        while chunk := source(_CHUNK):
            check_deadline(deadline)
            written += len(chunk)
            if written > limits.max_member_bytes:
                raise UnsafeArchiveError(f"member too large: {name}")
            dst.write(chunk)
    return written
