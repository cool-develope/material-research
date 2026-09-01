from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.analysis.factory import make_analyzer
from material_platform.analysis.llm import ANALYZER as LLM_ANALYZER
from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.process_material import ProcessMaterialService
from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import IndexService
from material_platform.infrastructure.object_store import FilesystemObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.trees import make_mixed_tree, zip_contents
from tests.unit.helpers.analysis import StubLlm


def test_llm_stub_one_summary_per_material_no_extra_units(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    store = FilesystemObjectStore(tmp_path / "store")
    ingested = IngestSourceService.create(
        session,
        store,
        TemporaryWorkspace(tmp_path / "work"),
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(archive)
    session.flush()
    analyzer = make_analyzer(
        Settings(
            _env_file=None, analyzer="llm", llm_base_url="http://example.invalid/v1"
        ),
        client=StubLlm(),
    )
    processor = ProcessMaterialService(session, store, index=index, analyzer=analyzer)
    summaries = []
    for material in ingested.materials:
        result = processor.process(material)
        session.flush()
        summaries.append(result.research.summary)
        assert result.analysis.analyzer == LLM_ANALYZER
        assert result.research.summary == "A survey of alloys for research use."
        assert "topics" in result.research.metadata
        assert len(result.research.content_units) >= 1
    assert len(summaries) == 3
