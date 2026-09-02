"""Compose production knobs shared by e2e_research and eval_aiml --prod.

Postgres, MinIO, Qdrant, and Langfuse come from docker compose. `.env`
supplies URLs, Langfuse keys, and LLM_BASE_URL. EMBEDDER / RERANKER /
ANALYZER in `.env` are ignored: production scripts always use BGE-M3,
the v2-m3 reranker, and LLM analysis. Each script uses its own Qdrant
collection so BGE vectors are not mixed with the hashed fake embedder.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from material_platform.config import Settings

REPO = Path(__file__).resolve().parents[3]
E2E_COLLECTION = "research_e2e"
AIML_COLLECTION = "research_aiml"
PROD_EMBEDDER = "bge-m3"
PROD_RERANKER = "bge-v2-m3"
PROD_ANALYZER = "llm"
EXTRACT_BYTES = 64 * 1024 * 1024
ARCHIVE_TIMEOUT = 300


def apply_prod_knobs(settings: Settings, *, collection: str) -> Settings:
    return settings.model_copy(
        update={
            "embedder": PROD_EMBEDDER,
            "reranker": PROD_RERANKER,
            "analyzer": PROD_ANALYZER,
            "qdrant_collection": collection,
            "qdrant_url": settings.qdrant_url or "http://localhost:6333",
            "qdrant_path": None,
            "max_extract_bytes": max(settings.max_extract_bytes, EXTRACT_BYTES),
            "max_archive_timeout_seconds": max(
                settings.max_archive_timeout_seconds, ARCHIVE_TIMEOUT
            ),
        }
    )


def prod_env(settings: Settings, *, collection: str) -> dict[str, str]:
    env = os.environ.copy()
    env["EMBEDDER"] = PROD_EMBEDDER
    env["RERANKER"] = PROD_RERANKER
    env["ANALYZER"] = PROD_ANALYZER
    env["QDRANT_COLLECTION"] = collection
    env["LANGFUSE_HOST"] = settings.langfuse_host
    env["LANGFUSE_BASE_URL"] = settings.langfuse_host
    if settings.langfuse_public_key:
        env["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    if settings.langfuse_secret_key:
        env["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    if settings.llm_base_url:
        env["LLM_BASE_URL"] = settings.llm_base_url
    env["LLM_API_KEY"] = settings.llm_api_key
    env["LLM_MODEL"] = settings.llm_model
    return env


def preflight_prod(
    settings: Settings,
    env: dict[str, str],
    *,
    source: Path | None = None,
    skip_ingest: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not skip_ingest and source is not None and not source.exists():
        errors.append(f"source not found: {source}")
    for port, name in ((5432, "postgres"), (9000, "minio"), (6333, "qdrant")):
        if not listening(port):
            errors.append(f"{name} is not on 127.0.0.1:{port} (docker compose up -d)")
    host = settings.langfuse_host
    parsed = urlparse(host)
    langfuse_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.hostname in {"localhost", "127.0.0.1"} and not listening(langfuse_port):
        errors.append(f"langfuse is not on {host}")
    if not env.get("LANGFUSE_PUBLIC_KEY") or not env.get("LANGFUSE_SECRET_KEY"):
        errors.append("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required")
    if not settings.llm_base_url:
        errors.append(
            "LLM_BASE_URL is required (Ollama or any OpenAI-compatible server)"
        )
    elif not llm_ok(settings):
        errors.append(f"LLM is not reachable at {settings.llm_base_url}")
    try:
        import FlagEmbedding  # noqa: F401
    except ImportError:
        errors.append(
            "FlagEmbedding is missing. "
            "uv pip install torch --index-url https://download.pytorch.org/whl/cpu "
            "&& uv pip install FlagEmbedding "
            "&& uv run python scripts/download_bge.py"
        )
    print(
        f"prod: embedder={PROD_EMBEDDER} reranker={PROD_RERANKER} "
        f"analyzer={PROD_ANALYZER} collection={settings.qdrant_collection} "
        f"langfuse={host} llm={settings.llm_model}",
        flush=True,
    )
    return errors


def migrate_head() -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO / "alembic.ini")), "head")


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def llm_ok(settings: Settings) -> bool:
    if not settings.llm_base_url:
        return False
    url = settings.llm_base_url.rstrip("/") + "/models"
    request = Request(url, headers={"Authorization": f"Bearer {settings.llm_api_key}"})
    try:
        with urlopen(request, timeout=5) as response:
            return 200 <= int(response.status) < 500
    except OSError:
        return False
