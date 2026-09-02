from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from material_platform.config import Settings
from material_platform.infrastructure.qdrant.client import make_qdrant_client
from material_platform.infrastructure.qdrant.store import ensure_hybrid_collection


def libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def make_checkpointer(settings: Settings) -> tuple[Any, Any]:
    if settings.database_url.startswith("postgresql"):
        return _postgres_checkpointer(settings.langgraph_database_url)
    path = settings.workspace_root / "langgraph.sqlite"
    return _sqlite_checkpointer(path)


def make_store(settings: Settings) -> tuple[Any, Any]:
    if settings.database_url.startswith("postgresql"):
        return _postgres_store(settings.langgraph_database_url)
    path = settings.workspace_root / "langgraph_store.sqlite"
    return _sqlite_store(path)


def ensure_langgraph(settings: Settings) -> None:
    make_checkpointer(settings)
    make_store(settings)
    if settings.qdrant_url:
        ensure_store(settings)


def ensure_checkpoint(database_url: str) -> None:
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(libpq_url(database_url)) as saver:
        saver.setup()


def ensure_store(settings: Settings) -> None:
    client = make_qdrant_client(settings)
    ensure_hybrid_collection(
        client,
        settings.langgraph_qdrant_collection,
        payload_indexes=False,
    )


def _postgres_checkpointer(database_url: str) -> tuple[Any, Any]:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=libpq_url(database_url),
        min_size=1,
        max_size=4,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    saver = PostgresSaver(pool)
    saver.setup()
    return saver, pool


def _sqlite_checkpointer(path: Path) -> tuple[Any, Any]:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver, conn


def _postgres_store(database_url: str) -> tuple[Any, Any]:
    from langgraph.store.postgres import PostgresStore
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=libpq_url(database_url),
        min_size=1,
        max_size=4,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    store = PostgresStore(pool)
    store.setup()
    return store, pool


def _sqlite_store(path: Path) -> tuple[Any, Any]:
    from langgraph.store.sqlite import SqliteStore

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.isolation_level = None
    store = SqliteStore(conn)
    store.setup()
    return store, conn
