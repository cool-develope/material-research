from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import dagster as dg
from pydantic import PrivateAttr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from material_platform.application.index import IndexService
from material_platform.application.local import sqlite_settings
from material_platform.application.runtime import Runtime
from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.infrastructure.object_store.protocol import ObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace


class PlatformResource(dg.ConfigurableResource):  # type: ignore[type-arg]
    data_dir: str = "/tmp/material-platform"
    use_sqlite: bool = False
    ingest_dir: str = ""
    _runtime: Runtime | None = PrivateAttr(default=None)

    def runtime(self) -> Runtime:
        if self._runtime is None:
            data = Path(self.data_dir)
            settings = Settings()
            if self.use_sqlite:
                settings = sqlite_settings(settings, data)
            else:
                settings = settings.model_copy(update={"workspace_root": data})
            self._runtime = Runtime(settings)
        return self._runtime

    def settings(self) -> Settings:
        return self.runtime().settings

    def engine(self) -> Engine:
        return self.runtime().engine

    def session_factory(self) -> sessionmaker[Session]:
        return self.runtime().sessions

    def store(self) -> ObjectStore:
        return self.runtime().store

    def index(self) -> IndexService:
        return self.runtime().index

    def workspace(self) -> TemporaryWorkspace:
        return self.runtime().workspace

    def archive_limits(self) -> ArchiveLimits:
        return self.runtime().archive_limits()

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.runtime().session() as session:
            yield session
