from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from material_platform.analysis import make_analyzer
from material_platform.application.process_material import ProcessMaterialService
from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import IndexService, make_index_service
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)
from material_platform.infrastructure.database.models import Base
from material_platform.infrastructure.object_store import make_object_store
from material_platform.infrastructure.object_store.protocol import ObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace


def uses_postgres(settings: Settings) -> bool:
    return settings.database_url.startswith("postgresql")


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        data_dir = settings.workspace_root
        data_dir.mkdir(parents=True, exist_ok=True)
        postgres = uses_postgres(settings)
        self.store: ObjectStore = (
            make_object_store(settings)
            if postgres
            else make_object_store(settings, filesystem_root=data_dir / "store")
        )
        self.engine: Engine = make_engine(settings)
        if not postgres:
            Base.metadata.create_all(self.engine)
        self.sessions: sessionmaker[Session] = make_session_factory(self.engine)
        self.workspace = TemporaryWorkspace(data_dir)
        self._index: IndexService | None = None

    @property
    def index(self) -> IndexService:
        if self._index is None:
            self._index = make_index_service(self.settings)
        return self._index

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def archive_limits(self) -> ArchiveLimits:
        return ArchiveLimits.from_settings(self.settings)

    def processor(
        self, session: Session, *, dagster_run_id: str | None = None
    ) -> ProcessMaterialService:
        settings = self.settings
        return ProcessMaterialService(
            session,
            self.store,
            self.index,
            pipeline_version=settings.pipeline_version,
            dagster_run_id=dagster_run_id,
            max_extract_bytes=settings.max_extract_bytes,
            max_units_per_material=settings.max_units_per_material,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap_tokens=settings.chunk_overlap_tokens,
            analyzer=make_analyzer(settings),
            settings=settings,
        )
