from pathlib import Path

from material_platform.config import Settings
from material_platform.infrastructure.object_store.filesystem import (
    FilesystemObjectStore,
)
from material_platform.infrastructure.object_store.minio import MinioObjectStore
from material_platform.infrastructure.object_store.protocol import ObjectStore


def make_object_store(
    settings: Settings,
    *,
    filesystem_root: Path | None = None,
) -> ObjectStore:
    if filesystem_root is not None:
        return FilesystemObjectStore(filesystem_root)
    return MinioObjectStore(settings)
