from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.api import create_app
from material_platform.application.local import sqlite_settings
from material_platform.config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp serve",
        description="HTTP search and chat over indexed ResearchMaterials.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Local data directory (sqlite under this path). "
        "Must match the directory used at ingest.",
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use DATABASE_URL and QDRANT_URL from the environment "
        "instead of local sqlite.",
    )
    args = parser.parse_args(argv)
    settings = Settings()
    if not args.postgres:
        data_dir = (args.data_dir or settings.workspace_root).resolve()
        settings = sqlite_settings(settings, data_dir)
    print(
        f"serve {'postgres' if args.postgres else 'sqlite'} "
        f"collection={settings.qdrant_collection} "
        f"embedder={settings.embedder} reranker={settings.reranker}",
        flush=True,
    )
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required to serve HTTP", file=sys.stderr)
        return 1
    uvicorn.run(create_app(settings=settings), host=args.host, port=args.port)
    return 0
