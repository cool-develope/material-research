from __future__ import annotations

from pathlib import Path

from material_platform.discovery.archive import ArchiveLimits, SafeZipExpander
from material_platform.discovery.archive_sevenz import Safe7zExpander
from material_platform.discovery.archive_tar import SafeTarExpander


class ArchiveRouter:
    def __init__(
        self,
        limits: ArchiveLimits,
        *,
        zip_expander: SafeZipExpander | None = None,
    ) -> None:
        self._zip = zip_expander or SafeZipExpander(limits)
        self._tar = SafeTarExpander(limits)
        self._sevenz = Safe7zExpander(limits)

    def expand(self, path: Path, destination: Path, archive_format: str) -> Path:
        if archive_format == "zip":
            return self._zip.expand(path, destination)
        if archive_format == "7z":
            return self._sevenz.expand(path, destination)
        return self._tar.expand(path, destination)
