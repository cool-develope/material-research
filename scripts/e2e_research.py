"""Production-like path: compose + BGE + reranker + LLM + Langfuse.

Postgres, MinIO, Qdrant, and Langfuse come from docker compose. Embeddings
are BGE-M3, hop-2 uses the v2-m3 reranker, ingest analysis and the agent
use LLM_BASE_URL. Vectors go to collection research_e2e so they are not
mixed with the hashed fake embedder.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from alembic import command
from alembic.config import Config

from material_platform.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "tests/fixtures/simple_mix/research.zip"
DEFAULT_QUERY = "How does handle_request work and where is it defined?"
COLLECTION = "research_e2e"
SCRATCH = Path("/tmp/mp-e2e")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a source on compose, then run the Deep Research agent."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--data-dir", type=Path, default=SCRATCH)
    parser.add_argument("--skip-ingest", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings()
    env = _prod_env(settings)
    errors = _preflight(settings, env, args.source, skip_ingest=args.skip_ingest)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1

    os.chdir(ROOT)
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    py = sys.executable
    if not args.skip_ingest:
        _run(
            [
                py,
                str(ROOT / "scripts/ingest_local.py"),
                str(args.source.resolve()),
                "--postgres",
                "--process",
                "--data-dir",
                str(args.data_dir.resolve()),
            ],
            env,
        )
        _run(
            [
                py,
                str(ROOT / "scripts/research_query.py"),
                args.query,
                "--postgres",
                "--limit",
                "5",
            ],
            env,
        )
    _run(
        [
            py,
            str(ROOT / "scripts/research_agent.py"),
            args.query,
            "--postgres",
            "--llm",
            "--trace",
        ],
        env,
    )
    print(
        f"langfuse ui: {env.get('LANGFUSE_HOST', settings.langfuse_host)}",
        file=sys.stderr,
    )
    return 0


def _prod_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env["EMBEDDER"] = "bge-m3"
    env["RERANKER"] = "bge-v2-m3"
    env["ANALYZER"] = "llm"
    env["QDRANT_COLLECTION"] = COLLECTION
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


def _preflight(
    settings: Settings,
    env: dict[str, str],
    source: Path,
    *,
    skip_ingest: bool,
) -> list[str]:
    errors: list[str] = []
    if not skip_ingest and not source.exists():
        errors.append(f"source not found: {source}")
    for port, name in ((5432, "postgres"), (9000, "minio"), (6333, "qdrant")):
        if not _listening(port):
            errors.append(f"{name} is not on 127.0.0.1:{port} (docker compose up -d)")
    host = settings.langfuse_host
    parsed = urlparse(host)
    langfuse_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.hostname in {"localhost", "127.0.0.1"} and not _listening(langfuse_port):
        errors.append(f"langfuse is not on {host}")
    if not env.get("LANGFUSE_PUBLIC_KEY") or not env.get("LANGFUSE_SECRET_KEY"):
        errors.append("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required")
    if not settings.llm_base_url:
        errors.append(
            "LLM_BASE_URL is required (Ollama or any OpenAI-compatible server)"
        )
    elif not _llm_ok(settings):
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
        "e2e: embedder=bge-m3 reranker=bge-v2-m3 analyzer=llm "
        f"collection={COLLECTION} langfuse={host} llm={settings.llm_model}",
        file=sys.stderr,
    )
    return errors


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _llm_ok(settings: Settings) -> bool:
    url = settings.llm_base_url.rstrip("/") + "/models"
    request = Request(url, headers={"Authorization": f"Bearer {settings.llm_api_key}"})
    try:
        with urlopen(request, timeout=5) as response:
            return 200 <= response.status < 500
    except OSError:
        return False


def _run(argv: list[str], env: dict[str, str]) -> None:
    print("+ " + " ".join(argv), file=sys.stderr)
    subprocess.run(argv, env=env, check=True, cwd=ROOT)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
