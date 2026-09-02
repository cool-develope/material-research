"""Production-like path: compose + BGE + reranker + LLM + Langfuse.

Postgres, MinIO, Qdrant, and Langfuse come from docker compose. `.env`
supplies URLs, Langfuse keys, and LLM_BASE_URL. EMBEDDER / RERANKER /
ANALYZER in `.env` are ignored: this script always uses BGE-M3, the
v2-m3 reranker, and LLM analysis. Vectors go to collection research_e2e
so they are not mixed with the hashed fake embedder.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from material_platform.application.prod import (
    E2E_COLLECTION,
    REPO,
    apply_prod_knobs,
    migrate_head,
    preflight_prod,
    prod_env,
)
from material_platform.config import Settings

DEFAULT_SOURCE = REPO / "tests/fixtures/simple_mix/research.zip"
DEFAULT_QUERY = "How does handle_request work and where is it defined?"
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

    settings = apply_prod_knobs(Settings(), collection=E2E_COLLECTION)
    env = prod_env(settings, collection=E2E_COLLECTION)
    errors = preflight_prod(
        settings, env, source=args.source, skip_ingest=args.skip_ingest
    )
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1

    os.chdir(REPO)
    migrate_head()
    py = sys.executable
    if not args.skip_ingest:
        _run(
            [
                py,
                str(REPO / "scripts/ingest_local.py"),
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
                str(REPO / "scripts/research_query.py"),
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
            str(REPO / "scripts/research_agent.py"),
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


def _run(argv: list[str], env: dict[str, str]) -> None:
    print("+ " + " ".join(argv), file=sys.stderr)
    subprocess.run(argv, env=env, check=True, cwd=REPO)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
