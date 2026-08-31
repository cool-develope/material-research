from pathlib import Path
from zipfile import ZipFile

import pytest

from material_platform.discovery import PathInspector
from material_platform.domain.enums import NodeKind


def test_inspects_directory(tmp_path: Path) -> None:
    folder = tmp_path / "backend"
    folder.mkdir()

    inspected = PathInspector().inspect(folder)

    assert inspected.is_directory
    assert inspected.node_kind is NodeKind.DIRECTORY
    assert not inspected.is_archive
    assert not inspected.is_file


def test_inspects_regular_file(tmp_path: Path) -> None:
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4")

    inspected = PathInspector().inspect(paper)

    assert inspected.is_file
    assert inspected.node_kind is NodeKind.FILE
    assert inspected.size_bytes == 8
    assert not inspected.is_archive


def test_inspects_zip_as_archive(tmp_path: Path) -> None:
    archive = tmp_path / "research.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("paper.pdf", b"%PDF-1.4")

    inspected = PathInspector().inspect(archive)

    assert inspected.is_archive
    assert inspected.node_kind is NodeKind.ARCHIVE
    assert not inspected.is_file
    assert not inspected.is_directory


def test_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PathInspector().inspect(tmp_path / "missing")
