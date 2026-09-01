from __future__ import annotations

import gzip
import tarfile
from pathlib import Path
from shutil import rmtree
from tarfile import TarError, TarFile, TarInfo

from material_platform.discovery.archive import ArchiveLimits, UnsafeArchiveError
from material_platform.discovery.archive_common import (
    check_deadline,
    deadline_for,
    is_junk_name,
    target_path,
    write_limited,
)


class SafeTarExpander:
    def __init__(self, limits: ArchiveLimits) -> None:
        self._limits = limits

    def expand(self, archive_path: Path, destination: Path) -> Path:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        try:
            if not self._expand_tar(archive_path, destination):
                self._expand_gzip_file(archive_path, destination)
        except Exception:
            rmtree(destination, ignore_errors=True)
            raise
        return destination

    def _expand_tar(self, archive_path: Path, destination: Path) -> bool:
        try:
            archive = tarfile.open(archive_path, mode="r:*")
        except (TarError, OSError):
            return False
        deadline = deadline_for(self._limits)
        total = 0
        with archive:
            members = archive.getmembers()
            if len(members) > self._limits.max_files:
                raise UnsafeArchiveError("archive contains too many files")
            for info in members:
                written = self._write_member(archive, info, destination, deadline)
                total += written
                if total > self._limits.max_total_bytes:
                    raise UnsafeArchiveError("archive expanded size exceeds limit")
        return True

    def _write_member(
        self,
        archive: TarFile,
        info: TarInfo,
        destination: Path,
        deadline: float | None,
    ) -> int:
        check_deadline(deadline)
        if is_junk_name(info.name) or not info.isfile():
            if info.issym() or info.islnk():
                raise UnsafeArchiveError(f"symlink not allowed: {info.name}")
            return 0
        if info.size > self._limits.max_member_bytes:
            raise UnsafeArchiveError(f"member too large: {info.name}")
        handle = archive.extractfile(info)
        if handle is None:
            return 0
        target = target_path(destination, info.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with handle:
            return write_limited(
                handle.read,
                target,
                limits=self._limits,
                deadline=deadline,
                name=info.name,
            )

    def _expand_gzip_file(self, archive_path: Path, destination: Path) -> None:
        name = archive_path.name
        out_name = name[:-3] if name.lower().endswith(".gz") else f"{name}.out"
        target = target_path(destination, out_name)
        deadline = deadline_for(self._limits)
        with gzip.open(archive_path, "rb") as src:
            write_limited(
                src.read,
                target,
                limits=self._limits,
                deadline=deadline,
                name=out_name,
            )
