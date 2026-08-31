from pathlib import Path
from uuid import uuid4

from material_platform.discovery import ArchiveLimits, DiscoveryService, SafeZipExpander
from material_platform.domain.discovery import DiscoveryManifest, DiscoveryNode
from material_platform.domain.enums import DiscoveryRole, NodeKind
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.trees import (
    make_mixed_tree,
    make_python_project,
    zip_contents,
    zip_named,
)


def _service(tmp_path: Path) -> DiscoveryService:
    return DiscoveryService.default(
        expander=SafeZipExpander(ArchiveLimits()),
        workspace=TemporaryWorkspace(tmp_path),
    )


def _discover(service: DiscoveryService, path: Path) -> DiscoveryManifest:
    return service.discover(
        path,
        source_id=uuid4(),
        discovery_run_id=uuid4(),
    )


def _materials(manifest: DiscoveryManifest) -> list[DiscoveryNode]:
    return [node for node in manifest.nodes if node.role is DiscoveryRole.MATERIAL]


def test_standalone_pdf_is_one_material(tmp_path: Path) -> None:
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4")
    manifest = _discover(_service(tmp_path), paper)
    materials = _materials(manifest)
    assert len(materials) == 1
    assert materials[0].path == "paper.pdf"
    assert materials[0].node_kind is NodeKind.FILE


def test_python_project_directory_is_one_material(tmp_path: Path) -> None:
    project = make_python_project(tmp_path / "backend")
    manifest = _discover(_service(tmp_path), project)
    materials = _materials(manifest)
    assert len(materials) == 1
    assert materials[0].path == "backend/"
    assert materials[0].metadata["material_hint"] == "python_project"


def test_mixed_directory_yields_three_materials(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    manifest = _discover(_service(tmp_path), mixed)
    materials = _materials(manifest)
    assert sorted(node.path for node in materials) == [
        "backend/",
        "dataset/",
        "paper.pdf",
    ]


def test_zip_of_mixed_tree_zip_is_never_material(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    manifest = _discover(_service(tmp_path), archive)

    archives = [node for node in manifest.nodes if node.node_kind is NodeKind.ARCHIVE]
    assert archives
    assert all(node.role is DiscoveryRole.CONTAINER for node in archives)

    materials = _materials(manifest)
    assert sorted(node.path for node in materials) == [
        "backend/",
        "dataset/",
        "paper.pdf",
    ]


def test_nested_zip_origin_chain(tmp_path: Path) -> None:
    project = make_python_project(tmp_path / "backend")
    inner = zip_named(project, tmp_path / "packages.zip")
    outer_dir = tmp_path / "outer"
    outer_dir.mkdir()
    (outer_dir / "packages.zip").write_bytes(inner.read_bytes())
    archive = zip_contents(outer_dir, tmp_path / "research.zip")

    manifest = _discover(_service(tmp_path), archive)
    materials = _materials(manifest)
    assert len(materials) == 1
    assert materials[0].path == "backend/"
    assert materials[0].metadata["origin_chain"] == [
        "research.zip",
        "packages.zip",
        "backend/",
    ]


def test_project_children_do_not_become_materials(tmp_path: Path) -> None:
    project = make_python_project(tmp_path / "backend")
    manifest = _discover(_service(tmp_path), project)
    paths = [node.path for node in manifest.nodes]
    assert paths == ["backend/"]
    assert "src/" not in paths
    assert "tests/" not in paths
    assert "docs/" not in paths


def test_junk_directories_are_ignored(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    junk = mixed / "node_modules"
    junk.mkdir()
    (junk / "left-pad" / "index.js").parent.mkdir(parents=True)
    (junk / "left-pad" / "index.js").write_text("module.exports = 1\n")

    materials = _materials(_discover(_service(tmp_path), mixed))
    assert sorted(node.path for node in materials) == [
        "backend/",
        "dataset/",
        "paper.pdf",
    ]


def test_nested_marker_does_not_make_parent_a_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("hi")
    src = root / "src"
    src.mkdir()
    (src / "package.json").write_text("{}")

    materials = _materials(_discover(_service(tmp_path), root))
    assert sorted(node.path for node in materials) == ["README.md", "src/"]
