from __future__ import annotations

from material_platform.config import Settings
from material_platform.infrastructure.qdrant.client import make_qdrant_client
from material_platform.infrastructure.qdrant.store import ensure_hybrid_collection


def libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def ensure_langgraph(settings: Settings) -> None:
    ensure_checkpoint(settings.langgraph_database_url)
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
