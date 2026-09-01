from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.process_material import ProcessMaterialService
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import IndexService
from material_platform.infrastructure.object_store import FilesystemObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.helpers.text import numbered_words


def _ingest(session: Session, tmp_path: Path, source: Path):
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    result = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(source)
    session.flush()
    return result, store


def test_process_wide_project_caps_files_skips_tests(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    root = tmp_path / "backend"
    src = root / "src"
    tests = root / "tests"
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='wide'\n")
    (src / "main.py").write_text(numbered_words(3_000, "main"))
    (src / "api.py").write_text("def handle_request():\n    return 1\n")
    (src / "util.py").write_text("def helper():\n    return 0\n")
    for number in range(40):
        (src / f"api_{number:02d}.py").write_text(
            f"def handle_request_{number:02d}():\n    return {number}\n"
        )
    for number in range(25):
        (tests / f"test_{number:02d}.py").write_text(
            f"def test_{number:02d}() -> None:\n    assert True\n"
        )

    ingested, store = _ingest(session, tmp_path, root)
    processed = ProcessMaterialService(session, store, index=index).process(
        ingested.materials[0]
    )
    session.flush()
    units = processed.research.content_units
    paths = {unit.location.path for unit in units}
    assert len(paths) == 20
    assert len(units) > 20
    assert "src/api.py" in paths
    assert "src/main.py" in paths
    assert "src/util.py" not in paths
    assert not any(path.startswith("tests/") for path in paths)
    assert all(
        unit.metadata.get("strategy") in {"code.file", "code.symbol"}
        for unit in units
    )
    assert any(
        unit.location.path == "src/api.py"
        and unit.metadata.get("strategy") == "code.symbol"
        for unit in units
    )
