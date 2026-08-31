from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from material_platform.infrastructure.object_store import (
    FilesystemObjectStore,
    UnsafeStoragePathError,
    material_content,
    raw_original,
    sha256_stream,
)


def test_put_open_round_trip(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    uri = raw_original(uuid4())
    payload = b"research zip bytes"

    store.put(uri=uri, data=BytesIO(payload), size=len(payload))

    assert store.exists(uri)
    with store.open(uri) as handle:
        assert handle.read() == payload


def test_rejects_path_traversal(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)

    with pytest.raises(UnsafeStoragePathError):
        store.put(uri="../secret", data=BytesIO(b"x"), size=1)

    with pytest.raises(UnsafeStoragePathError):
        store.exists("/etc/passwd")


def test_size_mismatch_does_not_keep_file(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    uri = material_content(uuid4(), "README.md")

    with pytest.raises(ValueError, match="size mismatch"):
        store.put(uri=uri, data=BytesIO(b"hello"), size=1)

    assert not store.exists(uri)


def test_sha256_stream_matches_known_digest() -> None:
    digest, size = sha256_stream(BytesIO(b"abc"))
    assert size == 3
    assert digest == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
