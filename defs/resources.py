from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import dagster as dg
from sqlalchemy.orm import Session, sessionmaker

from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)
from material_platform.infrastructure.database.models import Base
from material_platform.infrastructure.object_store import FilesystemObjectStore
from material_platform.infrastructure.object_store.protocol import ObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace


class PlatformResource(dg.ConfigurableResource):  # type: ignore[type-arg]
    data_dir: str = "/tmp/material-platform"
    use_sqlite: bool = True

    def settings(self) -> Settings:
        data = Path(self.data_dir)
        data.mkdir(parents=True, exist_ok=True)
        settings = Settings()
        if self.use_sqlite:
            return settings.model_copy(
                update={
                    "database_url": f"sqlite:///{data / 'material.db'}",
                    "workspace_root": data,
                }
            )
        return settings.model_copy(update={"workspace_root": data})

    def session_factory(self) -> sessionmaker[Session]:
        settings = self.settings()
        engine = make_engine(settings)
        Base.metadata.create_all(engine)
        return make_session_factory(engine)

    def store(self) -> ObjectStore:
        return FilesystemObjectStore(Path(self.data_dir) / "store")

    def workspace(self) -> TemporaryWorkspace:
        return TemporaryWorkspace(Path(self.data_dir))

    def archive_limits(self) -> ArchiveLimits:
        return ArchiveLimits.from_settings(self.settings())

    @contextmanager
    def session(self) -> Iterator[Session]:
        factory = self.session_factory()
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.commit()
            raise
        finally:
            session.close()
