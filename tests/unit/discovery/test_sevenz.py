from pathlib import Path
from uuid import uuid4

import pytest

from material_platform.discovery import (
    ArchiveLimits,
    DiscoveryService,
    SafeZipExpander,
)
from material_platform.discovery.archive import UnsafeArchiveError
from material_platform.discovery.archive_sevenz import Safe7zExpander
from material_platform.domain.enums import DiscoveryRole, NodeKind
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.artifacts import write_7z
from tests.unit.discovery.trees import make_mixed_tree


def test_7z_mixed_tree_matches_zip(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    entries = {
        file.relative_to(mixed).as_posix(): file.read_bytes()
        for file in mixed.rglob("*")
        if file.is_file()
    }
    archive = write_7z(tmp_path / "research.7z", entries)
    service = DiscoveryService.default(
        expander=SafeZipExpander(ArchiveLimits()),
        workspace=TemporaryWorkspace(tmp_path / "work"),
    )
    try:
        manifest = service.discover(
            archive, source_id=uuid4(), discovery_run_id=uuid4()
        )
    finally:
        service.cleanup()
    materials = [node for node in manifest.nodes if node.role is DiscoveryRole.MATERIAL]
    archives = [node for node in manifest.nodes if node.node_kind is NodeKind.ARCHIVE]
    assert sorted(node.path for node in materials) == [
        "backend/",
        "dataset/",
        "paper.pdf",
    ]
    assert archives[0].path == "research.7z"
    assert archives[0].role is DiscoveryRole.CONTAINER


def test_7z_rejects_path_traversal(tmp_path: Path) -> None:
    archive = write_7z(tmp_path / "evil.7z", {"../evil.txt": b"nope"})
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError, match="path traversal"):
        Safe7zExpander(ArchiveLimits()).expand(archive, dest)
    assert not dest.exists()


def test_7z_rejects_too_many_files(tmp_path: Path) -> None:
    archive = write_7z(
        tmp_path / "many.7z",
        {f"f{index}.txt": b"x" for index in range(3)},
    )
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError, match="too many files"):
        Safe7zExpander(ArchiveLimits(max_files=2)).expand(archive, dest)
    assert not dest.exists()
