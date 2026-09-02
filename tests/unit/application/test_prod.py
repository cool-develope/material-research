from pathlib import Path

from material_platform.application.local import sqlite_settings, uses_postgres
from material_platform.application.prod import (
    AIML_COLLECTION,
    E2E_COLLECTION,
    apply_prod_knobs,
    preflight_prod,
    prod_env,
    wipe_index,
)
from material_platform.config import Settings


def test_apply_prod_knobs_force_bge_llm_and_remote_qdrant() -> None:
    settings = apply_prod_knobs(
        Settings(
            embedder="fake",
            reranker="off",
            analyzer="deterministic",
            qdrant_url=None,
            qdrant_collection="research",
        ),
        collection=AIML_COLLECTION,
    )
    assert settings.embedder == "bge-m3"
    assert settings.reranker == "bge-v2-m3"
    assert settings.analyzer == "llm"
    assert settings.qdrant_collection == AIML_COLLECTION
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_path is None
    assert settings.max_extract_bytes >= 64 * 1024 * 1024


def test_prod_env_overrides_knobs() -> None:
    settings = apply_prod_knobs(Settings(), collection=E2E_COLLECTION)
    env = prod_env(settings, collection=E2E_COLLECTION)
    assert env["EMBEDDER"] == "bge-m3"
    assert env["RERANKER"] == "bge-v2-m3"
    assert env["ANALYZER"] == "llm"
    assert env["QDRANT_COLLECTION"] == E2E_COLLECTION


def test_preflight_prod_lists_compose_gaps(monkeypatch) -> None:
    import material_platform.application.prod as prod

    monkeypatch.setattr(prod, "listening", lambda port: False)
    monkeypatch.setattr(prod, "llm_ok", lambda settings: False)
    settings = Settings(
        llm_base_url="http://127.0.0.1:11434/v1",
        langfuse_host="http://localhost:3100",
        langfuse_public_key=None,
        langfuse_secret_key=None,
    )
    errors = " ".join(preflight_prod(settings, {}, skip_ingest=True))
    assert "postgres" in errors
    assert "minio" in errors
    assert "qdrant" in errors
    assert "langfuse" in errors
    assert "LANGFUSE_PUBLIC_KEY" in errors
    assert "LLM is not reachable" in errors


def test_wipe_index_recreates_collection(monkeypatch) -> None:
    calls: list[str] = []

    class Fake:
        def wipe(self) -> None:
            calls.append("wipe")

    monkeypatch.setattr(
        "material_platform.index.make_index_service", lambda settings: Fake()
    )
    wipe_index(Settings(_env_file=None, qdrant_collection=AIML_COLLECTION))
    assert calls == ["wipe"]


def test_uses_postgres_follows_database_url(tmp_path: Path) -> None:
    assert uses_postgres(Settings())
    assert not uses_postgres(sqlite_settings(Settings(), tmp_path / "data"))
