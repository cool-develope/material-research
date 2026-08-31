from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from uuid import UUID

from material_platform.discovery.skips import is_skipped_name
from material_platform.infrastructure.object_store.digest import sha256_stream
from material_platform.infrastructure.object_store.paths import (
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
