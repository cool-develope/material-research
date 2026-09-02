from pathlib import Path

import pytest

from material_platform.config import Settings, in_pytest


def test_settings_defaults_match_local_dev() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("/material")
    assert settings.workspace_root == Path("/tmp/material-platform")
    assert settings.discovery_version == "boundary-v1"
    assert settings.pipeline_version == "process-v1"
    assert settings.max_archive_depth == 5
    assert settings.minio_bucket == "material"
    assert settings.max_extract_bytes == 8 * 1024 * 1024
    assert settings.max_units_per_material == 20
    assert settings.chunk_tokens == 512
    assert settings.chunk_overlap_tokens == 64
    assert settings.retry_delay_seconds == 2
    assert settings.qdrant_collection == "research"
    assert settings.embedder == "fake"
    assert settings.bge_model == "BAAI/bge-m3"
    assert settings.bge_reranker == "BAAI/bge-reranker-v2-m3"
    assert settings.reranker == "off"
    assert settings.analyzer == "deterministic"
    assert settings.llm_api_key == "ollama"
    assert settings.llm_model == "llama3.1"
    assert settings.analysis_direct_tokens == 20_000
    assert settings.analysis_leaf_tokens == 10_000
    assert settings.analysis_reduce_fanin == 8
    assert settings.analysis_deep_files == 20
    assert settings.agent_mode == "standard"
    assert settings.langfuse_public_key is None
    assert settings.langfuse_host.startswith("https://")
    assert settings.langgraph_database_url.endswith("/langgraph")
    assert settings.langgraph_qdrant_collection == "langgraph"
    assert "localhost:5173" in settings.cors_origins


def test_pytest_ignores_dotenv() -> None:
    assert in_pytest()
    settings = Settings()
    assert settings.embedder == "fake"
    assert settings.reranker == "off"
    assert settings.analyzer == "deterministic"
    assert settings.agent_mode == "standard"
    assert settings.langfuse_public_key is None
    assert settings.llm_model == "llama3.1"


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:pass@db:5432/app",
    )
    monkeypatch.setenv("MAX_ARCHIVE_DEPTH", "2")
    monkeypatch.setenv("AGENT_MODE", "deep")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"
    assert settings.max_archive_depth == 2
    assert settings.agent_mode == "deep"
