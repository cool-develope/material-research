from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from material_platform.infrastructure.object_store.paths import safe_object_key
from material_platform.infrastructure.object_store.protocol import (
    UnsafeStoragePathError,
)

_CHUNK = 1024 * 1024


class FilesystemObjectStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        uri: str,
        data: BinaryIO,
        size: int,
        content_type: str | None = None,
    ) -> None:
        _ = content_type
        target = self._resolve(uri)
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with target.open("wb") as dst:
                while chunk := data.read(_CHUNK):
                    written += len(chunk)
                    if written > size:
                        raise ValueError(
                            f"size mismatch for {uri}: declared {size}, wrote {written}"
                        )
                    dst.write(chunk)
            if written != size:
                raise ValueError(
                    f"size mismatch for {uri}: declared {size}, wrote {written}"
                )
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def open(self, uri: str) -> BinaryIO:
        return self._resolve(uri).open("rb")

    def exists(self, uri: str) -> bool:
        return self._resolve(uri).is_file()

    def _resolve(self, uri: str) -> Path:
        key = safe_object_key(uri)
        target = (self._root / key).resolve()
        if not target.is_relative_to(self._root):
            raise UnsafeStoragePathError(f"path escaped object store: {uri}")
        return target
