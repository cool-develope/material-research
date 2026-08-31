from pathlib import Path
from uuid import uuid4

from material_platform.discovery import ArchiveLimits, DiscoveryService, SafeZipExpander
from material_platform.domain.enums import DiscoveryRole, NodeKind
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.trees import (
    COMPLEX_MATERIALS,
    FIXTURE_ZIP,
    make_complex_tree,
    zip_contents,
)


def _discover(tmp_path: Path, source: Path):
    service = DiscoveryService.default(
        expander=SafeZipExpander(ArchiveLimits()),
        workspace=TemporaryWorkspace(tmp_path / "work"),
    )
    try:
        return service.discover(
            source,
            source_id=uuid4(),
            discovery_run_id=uuid4(),
        )
    finally:
        service.cleanup()


def test_complex_zip_finds_nested_and_directory_materials(tmp_path: Path) -> None:
    archive = zip_contents(
        make_complex_tree(tmp_path / "complex"),
        tmp_path / "research.zip",
    )
    manifest = _discover(tmp_path, archive)
    materials = [node for node in manifest.nodes if node.role is DiscoveryRole.MATERIAL]
    archives = [node for node in manifest.nodes if node.node_kind is NodeKind.ARCHIVE]

    assert sorted(node.path for node in materials) == list(COMPLEX_MATERIALS)
    assert {node.path for node in archives} == {
        "research.zip",
        "packages.zip",
        "vendor/libs.zip",
        "nested/inner.zip",
        "deeper.zip",
    }
    assert all(node.role is DiscoveryRole.CONTAINER for node in archives)
    assert not any(node.path.endswith("node_modules/") for node in manifest.nodes)
    assert not any("__MACOSX" in node.path for node in manifest.nodes)


def test_complex_zip_nested_origin_chains(tmp_path: Path) -> None:
    archive = zip_contents(
        make_complex_tree(tmp_path / "complex"),
        tmp_path / "research.zip",
    )
    manifest = _discover(tmp_path, archive)
    by_path = {
        node.path: node
        for node in manifest.nodes
        if node.role is DiscoveryRole.MATERIAL
    }

    assert by_path["frontend/"].metadata["origin_chain"] == [
        "research.zip",
        "packages.zip",
        "frontend/",
    ]
    assert by_path["shared.py"].metadata["origin_chain"] == [
        "research.zip",
        "libs.zip",
        "shared.py",
    ]
    assert by_path["snippet.py"].metadata["origin_chain"] == [
        "research.zip",
        "inner.zip",
        "deeper.zip",
        "snippet.py",
    ]
    assert by_path["code/backend/"].metadata["origin_chain"] == [
        "research.zip",
        "code/backend/",
    ]


def test_committed_fixture_matches_complex_tree(tmp_path: Path) -> None:
    generated = zip_contents(
        make_complex_tree(tmp_path / "complex"),
        tmp_path / "generated.zip",
    )
    generated_paths = sorted(
        node.path
        for node in _discover(tmp_path / "gen", generated).nodes
        if node.role is DiscoveryRole.MATERIAL
    )
    fixture_paths = sorted(
        node.path
        for node in _discover(tmp_path / "fix", FIXTURE_ZIP).nodes
        if node.role is DiscoveryRole.MATERIAL
    )
    assert fixture_paths == generated_paths == list(COMPLEX_MATERIALS)
