from pathlib import Path

import pytest

from material_platform.config import Settings


def test_settings_defaults_match_local_dev() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("/material")
    assert settings.workspace_root == Path("/tmp/material-platform")
    assert settings.discovery_version == "boundary-v1"
    assert settings.pipeline_version == "process-v1"
    assert settings.max_archive_depth == 5
    assert settings.minio_bucket == "material"
    assert settings.max_extract_bytes == 8 * 1024 * 1024
    assert settings.retry_delay_seconds == 2


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:pass@db:5432/app",
    )
    monkeypatch.setenv("MAX_ARCHIVE_DEPTH", "2")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"
    assert settings.max_archive_depth == 2
