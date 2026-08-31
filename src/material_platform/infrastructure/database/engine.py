from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from material_platform.config import Settings


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _: object,
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(settings: Settings) -> Engine:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", enable_sqlite_foreign_keys)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False, class_=Session)
