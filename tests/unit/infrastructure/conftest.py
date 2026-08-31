from collections.abc import Iterator
from sqlite3 import Connection as SQLiteConnection

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from material_platform.infrastructure.database.models import Base


def _enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _: object,
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        yield session
        session.rollback()
