from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from uuid import UUID

from material_platform.discovery.skips import is_skipped_name
from material_platform.domain.discovery import DiscoveryManifest
from material_platform.extraction.common import MaterialFile
from material_platform.infrastructure.object_store.digest import sha256_stream
from material_platform.infrastructure.object_store.paths import (
    discovery_manifest,
    material_content,
    material_content_manifest,
)
from material_platform.infrastructure.object_store.protocol import ObjectStore


def list_content_files(root: Path) -> list[tuple[str, Path]]:
    if root.is_file():
        return [(root.name, root)]

    files: list[tuple[str, Path]] = []
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(root)
        if any(is_skipped_name(part) for part in relative.parts):
            continue
        files.append((relative.as_posix(), item))
    return files


def tree_digest(entries: list[tuple[str, str]]) -> str:
    hasher = hashlib.sha256()
    for relative, digest in sorted(entries):
        hasher.update(relative.encode())
        hasher.update(b"\0")
        hasher.update(digest.encode())
        hasher.update(b"\n")
    return hasher.hexdigest()


def copy_material_content(
    store: ObjectStore,
    *,
    material_id: UUID,
    local_path: Path,
) -> str:
    files = list_content_files(local_path)
    recorded: list[tuple[str, str, int]] = []
    for relative, file_path in files:
        with file_path.open("rb") as handle:
            digest, size = sha256_stream(handle)
        with file_path.open("rb") as handle:
            store.put(
                uri=material_content(material_id, relative),
                data=handle,
                size=size,
            )
        recorded.append((relative, digest, size))

    digest = tree_digest([(relative, sha) for relative, sha, _ in recorded])
    payload = json.dumps(
        {
            "digest": digest,
            "files": [
                {"path": relative, "sha256": sha, "size": size}
                for relative, sha, size in recorded
            ],
        }
    ).encode()
    store.put(
        uri=material_content_manifest(material_id),
        data=BytesIO(payload),
        size=len(payload),
        content_type="application/json",
    )
    return digest


def write_discovery_manifest(store: ObjectStore, manifest: DiscoveryManifest) -> str:
    body = manifest.model_dump_json().encode()
    uri = discovery_manifest(manifest.source_id, manifest.discovery_run_id)
    store.put(
        uri=uri,
        data=BytesIO(body),
        size=len(body),
        content_type="application/json",
    )
    return uri


def load_material_files(
    store: ObjectStore,
    material_id: UUID,
    *,
    max_bytes: int | None = None,
) -> tuple[MaterialFile, ...]:
    with store.open(material_content_manifest(material_id)) as handle:
        payload = json.load(handle)
    files = payload.get("files", [])
    if not isinstance(files, list):
        return ()
    loaded: list[MaterialFile] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = str(entry["path"])
        with store.open(material_content(material_id, path)) as handle:
            data = handle.read() if max_bytes is None else handle.read(max_bytes)
        loaded.append(MaterialFile(path=path, data=data))
    return tuple(loaded)
