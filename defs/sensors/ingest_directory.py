from __future__ import annotations

import json
import os
from pathlib import Path

import dagster as dg

from defs.ingest_paths import (
    archive_fingerprint,
    ingest_run_key,
    ingest_source_run_config,
    list_source_archives,
)
from defs.jobs.ingest_source import ingest_source_job
from defs.resources import PlatformResource


def watch_directory(platform: PlatformResource) -> Path | None:
    raw = platform.ingest_dir.strip() or os.environ.get("INGEST_DIRECTORY", "").strip()
    if not raw:
        return None
    return Path(raw)


@dg.sensor(
    job=ingest_source_job,
    minimum_interval_seconds=15,
    default_status=dg.DefaultSensorStatus.STOPPED,
)
def ingest_directory_sensor(
    context: dg.SensorEvaluationContext,
    platform: PlatformResource,
) -> dg.SensorResult:
    directory = watch_directory(platform)
    if directory is None:
        return dg.SensorResult(
            skip_reason="No ingest directory. Set ingest_dir or INGEST_DIRECTORY."
        )
    if not directory.is_dir():
        return dg.SensorResult(skip_reason=f"Not a directory: {directory}")

    seen = _load_cursor(context.cursor)
    requests: list[dg.RunRequest] = []
    next_seen: dict[str, str] = {}
    for path in list_source_archives(directory):
        fingerprint = archive_fingerprint(path)
        key = str(path)
        next_seen[key] = fingerprint
        if seen.get(key) == fingerprint:
            continue
        requests.append(
            dg.RunRequest(
                run_key=ingest_run_key(path, fingerprint),
                run_config=ingest_source_run_config(path),
                tags={"ingest_path": str(path), "source_name": path.name},
            )
        )

    cursor = json.dumps(next_seen, sort_keys=True)
    if not requests:
        return dg.SensorResult(skip_reason="No new archives.", cursor=cursor)
    context.log.info("queued %s archive ingest jobs", len(requests))
    return dg.SensorResult(run_requests=requests, cursor=cursor)


def _load_cursor(cursor: str | None) -> dict[str, str]:
    if not cursor:
        return {}
    loaded = json.loads(cursor)
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(value) for key, value in loaded.items()}
