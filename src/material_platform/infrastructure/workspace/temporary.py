from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from shutil import rmtree
from uuid import UUID

from material_platform.infrastructure.object_store.protocol import (
    UnsafeStoragePathError,
)


class TemporaryWorkspace:
    def __init__(self, root: Path) -> None:
        self._root = (root / "scratch").resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def scratch_dir(self, source_id: UUID, node_id: UUID) -> Path:
        path = self._root / str(source_id) / str(node_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def remove(self, path: Path) -> None:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._root):
            raise UnsafeStoragePathError(f"refusing to delete outside scratch: {path}")
        rmtree(resolved)

    @contextmanager
    def scratch(self, source_id: UUID, node_id: UUID) -> Iterator[Path]:
        path = self.scratch_dir(source_id, node_id)
        try:
            yield path
        finally:
            if path.exists():
                rmtree(path, ignore_errors=True)
