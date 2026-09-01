from __future__ import annotations

import os
import socket
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from defs.jobs.ingest_source import ingest_source_job
from defs.resources import PlatformResource

from tests.unit.discovery.trees import SIMPLE_ZIP, make_mixed_tree, zip_contents

_COMPOSE_PORTS = (5432, 9000, 6333)


def _compose_ready() -> bool:
    for port in _COMPOSE_PORTS:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            sock.close()
        except OSError:
            return False
    return True


pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_COMPOSE") != "1",
    reason="set LIVE_COMPOSE=1 to run against compose postgres/minio/qdrant",
)


def _archive(tmp_path: Path) -> Path:
    if SIMPLE_ZIP.exists():
        return SIMPLE_ZIP
    mixed = make_mixed_tree(tmp_path / "mixed")
    return zip_contents(mixed, tmp_path / "research.zip")


def test_compose_reingest_after_new_resource_does_not_duplicate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _compose_ready():
        pytest.fail("LIVE_COMPOSE=1 but postgres/minio/qdrant are not listening")
    token = uuid4().hex[:10]
    monkeypatch.setenv("QDRANT_COLLECTION", f"gate14{token}")
    monkeypatch.setenv("MINIO_BUCKET", f"gate14{token}")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://material:material@localhost:5432/material",
    )
    command.upgrade(Config("alembic.ini"), "head")
    archive = str(_archive(tmp_path))
    run_config = {"ops": {"ingest_source": {"config": {"path": archive}}}}
    first = ingest_source_job.execute_in_process(
        run_config=run_config,
        resources={
            "platform": PlatformResource(
                data_dir=str(tmp_path / "one"),
                use_sqlite=False,
            )
        },
    )
    second = ingest_source_job.execute_in_process(
        run_config=run_config,
        resources={
            "platform": PlatformResource(
                data_dir=str(tmp_path / "two"),
                use_sqlite=False,
            )
        },
    )
    assert first.success and second.success
    first_ids = first.output_for_node("ingest_source")
    second_ids = second.output_for_node("ingest_source")
    assert len(first_ids) == 3
    assert first_ids == second_ids
