from __future__ import annotations

from pathlib import Path

from material_platform.config import Settings
from material_platform.infrastructure.langgraph_backends import (
    ensure_checkpoint,
    ensure_store,
    libpq_url,
)
from material_platform.infrastructure.qdrant.client import (
    close_path_clients,
    make_qdrant_client,
)


def test_libpq_url_strips_sqlalchemy_dialect() -> None:
    assert (
        libpq_url("postgresql+psycopg://material:material@localhost:5432/langgraph")
        == "postgresql://material:material@localhost:5432/langgraph"
    )
    assert libpq_url(
        "postgresql://material:material@localhost:5432/langgraph"
    ).endswith("/langgraph")


def test_ensure_store_creates_langgraph_collection(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        qdrant_url=None,
        qdrant_path=tmp_path / "qdrant",
        langgraph_qdrant_collection="langgraph",
    )
    try:
        ensure_store(settings)
        client = make_qdrant_client(settings)
        assert client.collection_exists("langgraph")
        ensure_store(settings)
    finally:
        close_path_clients()


def test_ensure_checkpoint_runs_setup(monkeypatch) -> None:
    calls: list[str] = []

    class Saver:
        def setup(self) -> None:
            calls.append("setup")

        def __enter__(self) -> Saver:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    class PostgresSaver:
        @staticmethod
        def from_conn_string(url: str) -> Saver:
            assert url == "postgresql://material:material@localhost:5432/langgraph"
            return Saver()

    import langgraph.checkpoint.postgres as postgres

    monkeypatch.setattr(postgres, "PostgresSaver", PostgresSaver)
    ensure_checkpoint("postgresql+psycopg://material:material@localhost:5432/langgraph")
    assert calls == ["setup"]


def test_make_store_sqlite_roundtrip(tmp_path: Path) -> None:
    from material_platform.infrastructure.langgraph_backends import make_store

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'material.db'}",
        workspace_root=tmp_path,
    )
    store, _ref = make_store(settings)
    store.put(("thread-1",), "request", {"kind": "request", "text": "auth"})
    found = store.get(("thread-1",), "request")
    assert found is not None
    assert found.value["text"] == "auth"
