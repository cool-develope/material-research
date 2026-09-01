from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from material_platform.index import IndexService
from material_platform.infrastructure.database.engine import enable_sqlite_foreign_keys
from material_platform.infrastructure.database.models import Base
from tests.unit.helpers.index import make_test_index


@pytest.fixture
def engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def index() -> IndexService:
    return make_test_index()
