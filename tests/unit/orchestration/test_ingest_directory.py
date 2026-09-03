from pathlib import Path

import dagster as dg
from defs.ingest_paths import list_source_archives
from defs.resources import PlatformResource
from defs.sensors.ingest_directory import ingest_directory_sensor

from tests.unit.discovery.trees import make_mixed_tree, zip_contents


def _folder_with_zips(tmp_path: Path) -> Path:
    folder = tmp_path / "inbox"
    folder.mkdir()
    first = make_mixed_tree(tmp_path / "one")
    second = make_mixed_tree(tmp_path / "two")
    zip_contents(first, folder / "a.zip")
    zip_contents(second, folder / "b.zip")
    (folder / "notes.pdf").write_bytes(b"%PDF-1.4")
    (folder / ".hidden.zip").write_bytes(b"nope")
    nested = folder / "nested"
    nested.mkdir()
    zip_contents(first, nested / "ignored.zip")
    return folder


def test_list_source_archives_is_top_level_expand_only(tmp_path: Path) -> None:
    folder = _folder_with_zips(tmp_path)
    names = [path.name for path in list_source_archives(folder)]
    assert names == ["a.zip", "b.zip"]


def test_directory_sensor_launches_one_job_per_new_zip(tmp_path: Path) -> None:
    folder = _folder_with_zips(tmp_path)
    platform = PlatformResource(
        data_dir=str(tmp_path / "data"),
        ingest_dir=str(folder),
        use_sqlite=True,
    )
    context = dg.build_sensor_context(resources={"platform": platform})
    tick = ingest_directory_sensor.evaluate_tick(context)
    requests = list(tick.run_requests or [])
    assert len(requests) == 2
    names = sorted(req.tags["source_name"] for req in requests)
    assert names == ["a.zip", "b.zip"]
    paths = {
        req.run_config["ops"]["ingest_source"]["config"]["path"] for req in requests
    }
    assert paths == {
        str((folder / "a.zip").resolve()),
        str((folder / "b.zip").resolve()),
    }
    assert all(req.run_key and req.run_key.startswith("ingest:") for req in requests)


def test_directory_sensor_skips_seen_archives(tmp_path: Path) -> None:
    folder = _folder_with_zips(tmp_path)
    platform = PlatformResource(
        data_dir=str(tmp_path / "data"),
        ingest_dir=str(folder),
        use_sqlite=True,
    )
    first = ingest_directory_sensor.evaluate_tick(
        dg.build_sensor_context(resources={"platform": platform})
    )
    second = ingest_directory_sensor.evaluate_tick(
        dg.build_sensor_context(
            resources={"platform": platform},
            cursor=first.cursor,
        )
    )
    assert list(second.run_requests or []) == []
    assert second.skip_message == "No new archives."


def test_directory_sensor_relaunches_when_zip_changes(tmp_path: Path) -> None:
    folder = _folder_with_zips(tmp_path)
    platform = PlatformResource(
        data_dir=str(tmp_path / "data"),
        ingest_dir=str(folder),
        use_sqlite=True,
    )
    first = ingest_directory_sensor.evaluate_tick(
        dg.build_sensor_context(resources={"platform": platform})
    )
    changed = folder / "a.zip"
    changed.write_bytes(changed.read_bytes() + b"\x00")
    second = ingest_directory_sensor.evaluate_tick(
        dg.build_sensor_context(
            resources={"platform": platform},
            cursor=first.cursor,
        )
    )
    requests = list(second.run_requests or [])
    assert len(requests) == 1
    assert requests[0].tags["source_name"] == "a.zip"


def test_directory_sensor_skips_without_path(tmp_path: Path) -> None:
    platform = PlatformResource(data_dir=str(tmp_path / "data"), use_sqlite=True)
    tick = ingest_directory_sensor.evaluate_tick(
        dg.build_sensor_context(resources={"platform": platform})
    )
    assert list(tick.run_requests or []) == []
    assert tick.skip_message is not None
    assert "No ingest directory" in tick.skip_message
