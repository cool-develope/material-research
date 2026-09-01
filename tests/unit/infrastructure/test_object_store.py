from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from defs.resources import PlatformResource

from material_platform.config import Settings
from material_platform.infrastructure.object_store import (
    FilesystemObjectStore,
    MinioObjectStore,
    UnsafeStoragePathError,
    make_object_store,
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


def test_make_object_store_uses_filesystem_when_root_given(tmp_path: Path) -> None:
    store = make_object_store(
        Settings(_env_file=None),
        filesystem_root=tmp_path / "store",
    )
    assert isinstance(store, FilesystemObjectStore)


def test_make_object_store_uses_minio_without_filesystem_root() -> None:
    store = make_object_store(Settings(_env_file=None))
    assert isinstance(store, MinioObjectStore)


def test_platform_resource_uses_filesystem_for_sqlite(tmp_path: Path) -> None:
    platform = PlatformResource(data_dir=str(tmp_path / "data"), use_sqlite=True)
    assert isinstance(platform.store(), FilesystemObjectStore)


def test_platform_resource_uses_minio_for_postgres(tmp_path: Path) -> None:
    platform = PlatformResource(data_dir=str(tmp_path / "data"), use_sqlite=False)
    assert isinstance(platform.store(), MinioObjectStore)


def test_platform_resource_reuses_engine(tmp_path: Path) -> None:
    platform = PlatformResource(data_dir=str(tmp_path / "data"), use_sqlite=True)
    assert platform.engine() is platform.engine()
    assert platform.session_factory() is platform.session_factory()


def test_minio_rejects_path_traversal_before_network() -> None:
    store = MinioObjectStore(Settings(_env_file=None))
    with pytest.raises(UnsafeStoragePathError):
        store.put(uri="../secret", data=BytesIO(b"x"), size=1)
    with pytest.raises(UnsafeStoragePathError):
        store.exists("/etc/passwd")


def _live_minio() -> MinioObjectStore | None:
    store = MinioObjectStore(Settings(_env_file=None))
    try:
        store.ensure_bucket()
    except Exception:
        return None
    return store


def test_minio_put_open_round_trip_when_server_running() -> None:
    store = _live_minio()
    if store is None:
        pytest.skip("MinIO is not running on localhost:9000")
    uri = raw_original(uuid4())
    payload = b"minio round trip"
    store.put(uri=uri, data=BytesIO(payload), size=len(payload))
    assert store.exists(uri)
    with store.open(uri) as handle:
        assert handle.read() == payload
    assert not store.exists(raw_original(uuid4()))
