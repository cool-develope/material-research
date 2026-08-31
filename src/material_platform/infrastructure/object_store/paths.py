from pathlib import PurePosixPath
from uuid import UUID

from material_platform.infrastructure.object_store.protocol import (
    UnsafeStoragePathError,
)


def safe_object_key(uri: str) -> str:
    if "\x00" in uri:
        raise UnsafeStoragePathError("NUL in object uri")
    relative = PurePosixPath(uri.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or relative.anchor:
        raise UnsafeStoragePathError(f"unsafe object uri: {uri}")
    return relative.as_posix()


def raw_original(source_id: UUID) -> str:
    return f"raw/{source_id}/original"


def discovery_manifest(source_id: UUID, discovery_run_id: UUID) -> str:
    return f"manifests/{source_id}/{discovery_run_id}.json"


def material_content_root(material_id: UUID) -> str:
    return f"materials/{material_id}/content"


def material_content_manifest(material_id: UUID) -> str:
    return f"materials/{material_id}/content-manifest.json"


def material_content(material_id: UUID, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    return f"materials/{material_id}/content/{normalized}"


def material_artifact(
    material_id: UUID,
    artifact_type: str,
    processor_version: str,
) -> str:
    return f"artifacts/{material_id}/{artifact_type}/{processor_version}.json"
