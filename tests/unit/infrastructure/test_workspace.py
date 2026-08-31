from pathlib import Path
from uuid import uuid4

import pytest

from material_platform.infrastructure.object_store import UnsafeStoragePathError
from material_platform.infrastructure.workspace import TemporaryWorkspace


def test_scratch_session_deletes_on_exit(tmp_path: Path) -> None:
    workspace = TemporaryWorkspace(tmp_path)
    source_id = uuid4()
    node_id = uuid4()

    with workspace.scratch(source_id, node_id) as path:
        (path / "paper.pdf").write_bytes(b"%PDF")
        assert path.is_dir()
        assert (path / "paper.pdf").is_file()

    assert not path.exists()


def test_remove_refuses_paths_outside_scratch(tmp_path: Path) -> None:
    workspace = TemporaryWorkspace(tmp_path)
    outside = tmp_path / "not-scratch"
    outside.mkdir()

    with pytest.raises(UnsafeStoragePathError):
        workspace.remove(outside)
