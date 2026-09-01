from pathlib import Path

from material_platform.config import Settings
from material_platform.infrastructure.qdrant.client import (
    close_path_clients,
    make_qdrant_client,
)


def test_path_client_is_cached_and_closes(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        qdrant_url=None,
        qdrant_path=tmp_path / "qdrant",
    )
    first = make_qdrant_client(settings)
    second = make_qdrant_client(settings)
    assert first is second
    close_path_clients()
    third = make_qdrant_client(settings)
    assert third is not first
    close_path_clients()
