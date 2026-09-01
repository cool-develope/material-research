from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from py7zr import SevenZipFile
from py7zr.exceptions import Bad7zFile, PasswordRequired

from material_platform.discovery.archive import ArchiveLimits, UnsafeArchiveError
from material_platform.discovery.archive_common import (
    check_deadline,
    deadline_for,
    is_junk_name,
    target_path,
)


class Safe7zExpander:
    def __init__(self, limits: ArchiveLimits) -> None:
        self._limits = limits

    def expand(self, archive_path: Path, destination: Path) -> Path:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        try:
            self._expand(archive_path, destination)
        except Exception:
            rmtree(destination, ignore_errors=True)
            raise
        return destination

    def _expand(self, archive_path: Path, destination: Path) -> None:
        deadline = deadline_for(self._limits)
        try:
            archive = SevenZipFile(archive_path, mode="r")
        except Bad7zFile as exc:
            raise UnsafeArchiveError("invalid 7z archive") from exc
        with archive:
            if archive.needs_password():
                raise UnsafeArchiveError("encrypted member not allowed")
            infos = archive.list()
            if len(infos) > self._limits.max_files:
                raise UnsafeArchiveError("archive contains too many files")
            files: list[str] = []
            total = 0
            for info in infos:
                check_deadline(deadline)
                name = info.filename
                if info.is_symlink:
                    raise UnsafeArchiveError(f"symlink not allowed: {name}")
                if info.is_directory or is_junk_name(name):
                    continue
                target_path(destination, name)
                if info.uncompressed > self._limits.max_member_bytes:
                    raise UnsafeArchiveError(f"member too large: {name}")
                total += info.uncompressed
                if total > self._limits.max_total_bytes:
                    raise UnsafeArchiveError("archive expanded size exceeds limit")
                files.append(name)
            try:
                archive.extract(path=destination, targets=files)
            except PasswordRequired as exc:
                raise UnsafeArchiveError("encrypted member not allowed") from exc
