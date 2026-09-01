from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo
from uuid import uuid4

import pytest

from material_platform.discovery import (
    ArchiveLimits,
    DiscoveryService,
    PathInspector,
    SafeZipExpander,
)
from material_platform.discovery.archive import UnsafeArchiveError
from material_platform.discovery.archive_tar import SafeTarExpander
from material_platform.domain.enums import DiscoveryRole, NodeKind
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.artifacts import write_docx, write_jar, write_pe, write_wheel
from tests.unit.discovery.trees import (
    COMPLEX_MATERIALS,
    make_complex_tree,
    make_mixed_tree,
    tar_gz_contents,
    zip_contents,
)


def _discover(tmp_path: Path, source: Path):
    service = DiscoveryService.default(
        expander=SafeZipExpander(ArchiveLimits()),
        workspace=TemporaryWorkspace(tmp_path / "work"),
    )
    try:
        return service.discover(
            source, source_id=uuid4(), discovery_run_id=uuid4()
        )
    finally:
        service.cleanup()


def _materials(manifest):
    return [node for node in manifest.nodes if node.role is DiscoveryRole.MATERIAL]


def test_wheel_is_one_file_material(tmp_path: Path) -> None:
    wheel = write_wheel(tmp_path / "requests-2.32.3-py3-none-any.whl")
    inspected = PathInspector().inspect(wheel)
    assert inspected.is_file
    assert not inspected.is_archive
    assert inspected.material_hint == "python_wheel"
    assert inspected.peek.get("package") == "requests"

    materials = _materials(_discover(tmp_path, wheel))
    assert len(materials) == 1
    assert materials[0].path.endswith(".whl")
    assert not any(node.path.endswith(".py") for node in materials)


def test_jar_is_one_file_material(tmp_path: Path) -> None:
    jar = write_jar(tmp_path / "guava.jar")
    materials = _materials(_discover(tmp_path, jar))
    assert len(materials) == 1
    assert materials[0].metadata.get("package") == "guava"
    assert not any(".class" in node.path for node in materials)


def test_docx_is_not_expanded(tmp_path: Path) -> None:
    docx = write_docx(tmp_path / "notes.docx")
    inspected = PathInspector().inspect(docx)
    assert inspected.is_file
    assert not inspected.is_archive
    materials = _materials(_discover(tmp_path, docx))
    assert len(materials) == 1
    assert materials[0].path == "notes.docx"


def test_pe_exe_is_file_material(tmp_path: Path) -> None:
    exe = write_pe(tmp_path / "AndroidStudio-setup.exe")
    inspected = PathInspector().inspect(exe)
    assert inspected.is_file
    assert inspected.material_hint == "installer"
    materials = _materials(_discover(tmp_path, exe))
    assert len(materials) == 1


def test_tar_gz_mixed_tree_matches_zip(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = tar_gz_contents(mixed, tmp_path / "research.tar.gz")
    manifest = _discover(tmp_path, archive)
    materials = _materials(manifest)
    archives = [node for node in manifest.nodes if node.node_kind is NodeKind.ARCHIVE]
    assert sorted(node.path for node in materials) == [
        "backend/",
        "dataset/",
        "paper.pdf",
    ]
    assert all(node.role is DiscoveryRole.CONTAINER for node in archives)
    assert archives[0].path == "research.tar.gz"


def test_nested_tar_in_zip_grows_origin(tmp_path: Path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    (inner / "notes.txt").write_text("hi\n")
    tar_gz_contents(inner, tmp_path / "notes.tar.gz")
    wrapper = tmp_path / "wrap"
    wrapper.mkdir()
    (wrapper / "notes.tar.gz").write_bytes((tmp_path / "notes.tar.gz").read_bytes())
    archive = zip_contents(wrapper, tmp_path / "outer.zip")
    notes = next(
        node
        for node in _materials(_discover(tmp_path, archive))
        if node.path.endswith("notes.txt")
    )
    chain = notes.metadata.get("origin_chain")
    assert isinstance(chain, list)
    assert "outer.zip" in chain
    assert "notes.tar.gz" in chain


def test_tar_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.tar"
    with TarFile.open(archive, "w") as tar:
        info = TarInfo("../evil.txt")
        payload = b"nope"
        info.size = len(payload)
        tar.addfile(info, fileobj=BytesIO(payload))
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError, match="path traversal"):
        SafeTarExpander(ArchiveLimits()).expand(archive, dest)
    assert not dest.exists()


def test_tar_rejects_too_many_files(tmp_path: Path) -> None:
    archive = tmp_path / "many.tar"
    with TarFile.open(archive, "w") as tar:
        for index in range(3):
            info = TarInfo(f"f{index}.txt")
            info.size = 1
            tar.addfile(info, fileobj=BytesIO(b"x"))
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError, match="too many files"):
        SafeTarExpander(ArchiveLimits(max_files=2)).expand(archive, dest)
    assert not dest.exists()


def test_complex_tar_gz_finds_same_materials(tmp_path: Path) -> None:
    tree = make_complex_tree(tmp_path / "complex")
    archive = tar_gz_contents(tree, tmp_path / "research.tar.gz")
    materials = _materials(_discover(tmp_path, archive))
    assert sorted(node.path for node in materials) == list(COMPLEX_MATERIALS)
