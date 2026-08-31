from __future__ import annotations

import stat
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from shutil import rmtree
from zipfile import BadZipFile, ZipFile, ZipInfo

from material_platform.config import Settings

_CHUNK = 64 * 1024
_JUNK_DIRS = frozenset({"__MACOSX"})
_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db"})


class UnsafeArchiveError(Exception):
    pass


@dataclass(frozen=True)
class ArchiveLimits:
    max_files: int = 10_000
    max_total_bytes: int = 2 * 1024**3
    max_member_bytes: int = 512 * 1024**2
    max_ratio: float = 200.0
    timeout_seconds: int = 60

    @classmethod
    def from_settings(cls, settings: Settings) -> ArchiveLimits:
        return cls(
            max_files=settings.max_archive_files,
            max_total_bytes=settings.max_expanded_bytes,
            max_member_bytes=settings.max_member_bytes,
            max_ratio=settings.max_compression_ratio,
            timeout_seconds=settings.max_archive_timeout_seconds,
        )


class SafeZipExpander:
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
        deadline = (
            None
            if self._limits.timeout_seconds <= 0
            else time.monotonic() + self._limits.timeout_seconds
        )
        total_written = 0
        declared_total = 0

        try:
            archive = ZipFile(archive_path)
        except BadZipFile as exc:
            raise UnsafeArchiveError("invalid zip archive") from exc

        with archive:
            infos = archive.infolist()
            if len(infos) > self._limits.max_files:
                raise UnsafeArchiveError("archive contains too many files")

            for info in infos:
                self._check_deadline(deadline)
                self._validate_name(info.filename)

                if self._is_junk(info.filename):
                    continue

                self._validate_member(info)
                declared_total += info.file_size
                if declared_total > self._limits.max_total_bytes:
                    raise UnsafeArchiveError("archive expanded size exceeds limit")

                if info.is_dir():
                    continue

                target = self._target_path(destination, info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                written = self._copy_member(archive, info, target, deadline)
                total_written += written
                if total_written > self._limits.max_total_bytes:
                    raise UnsafeArchiveError("archive expanded size exceeds limit")

    def _copy_member(
        self,
        archive: ZipFile,
        info: ZipInfo,
        target: Path,
        deadline: float | None,
    ) -> int:
        written = 0
        try:
            with archive.open(info) as src, target.open("xb") as dst:
                while chunk := src.read(_CHUNK):
                    self._check_deadline(deadline)
                    written += len(chunk)
                    if written > self._limits.max_member_bytes:
                        raise UnsafeArchiveError(f"member too large: {info.filename}")
                    dst.write(chunk)
        except RuntimeError as exc:
            raise UnsafeArchiveError(
                f"encrypted member not allowed: {info.filename}"
            ) from exc
        except FileExistsError as exc:
            raise UnsafeArchiveError(
                f"duplicate archive member: {info.filename}"
            ) from exc
        return written

    def _validate_name(self, name: str) -> None:
        if "\x00" in name:
            raise UnsafeArchiveError("NUL in archive path")

        normalized = name.replace("\\", "/")
        path = PurePosixPath(normalized)

        if path.is_absolute() or path.anchor:
            raise UnsafeArchiveError(f"absolute archive path: {name}")

        if ".." in path.parts:
            raise UnsafeArchiveError(f"path traversal: {name}")

    def _validate_member(self, info: ZipInfo) -> None:
        if info.flag_bits & 0x1:
            raise UnsafeArchiveError(f"encrypted member not allowed: {info.filename}")

        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise UnsafeArchiveError(f"symlink not allowed: {info.filename}")

        if info.file_size > self._limits.max_member_bytes:
            raise UnsafeArchiveError(f"member too large: {info.filename}")

        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > self._limits.max_ratio:
                raise UnsafeArchiveError(
                    f"suspicious compression ratio: {info.filename}"
                )

    def _is_junk(self, name: str) -> bool:
        parts = PurePosixPath(name.replace("\\", "/")).parts
        if any(part in _JUNK_DIRS for part in parts):
            return True
        return bool(parts) and parts[-1] in _JUNK_FILES

    def _target_path(self, destination: Path, member_name: str) -> Path:
        relative = PurePosixPath(member_name.replace("\\", "/"))
        target = destination.joinpath(*relative.parts).resolve()
        if not target.is_relative_to(destination):
            raise UnsafeArchiveError(f"path escaped destination: {member_name}")
        return target

    def _check_deadline(self, deadline: float | None) -> None:
        if deadline is not None and time.monotonic() > deadline:
            raise UnsafeArchiveError("archive expansion timed out")
