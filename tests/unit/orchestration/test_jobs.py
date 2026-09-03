from pathlib import Path
from uuid import UUID

import dagster as dg
from defs.jobs.ingest_source import ingest_source_job
from defs.jobs.process_material import process_material, process_material_job
from defs.resources import PlatformResource
from defs.sensors.pending_materials import pending_materials_sensor

from material_platform.domain.enums import MaterialStatus
from material_platform.infrastructure.database.repositories import MaterialRepository
from tests.unit.discovery.trees import make_mixed_tree, zip_contents


def _platform(tmp_path: Path) -> PlatformResource:
    return PlatformResource(data_dir=str(tmp_path / "data"), use_sqlite=True)


def _materials(platform: PlatformResource) -> list:
    loaded = []
    with platform.session() as session:
        for status in MaterialStatus:
            loaded.extend(MaterialRepository(session).list_by_status(status))
    return loaded


def test_ingest_and_process_jobs_mark_materials_ready(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    platform = _platform(tmp_path)

    ingested = ingest_source_job.execute_in_process(
        run_config={
            "ops": {"ingest_source": {"config": {"path": str(archive)}}}
        },
        resources={"platform": platform},
    )
    assert ingested.success
    material_ids = ingested.output_for_node("ingest_source")
    assert len(material_ids) == 3

    for material_id in material_ids:
        processed = process_material_job.execute_in_process(
            run_config={
                "ops": {
                    "process_material": {"config": {"material_id": material_id}}
                }
            },
            resources={"platform": platform},
        )
        assert processed.success

    loaded = _materials(platform)
    assert {item.status for item in loaded} == {MaterialStatus.READY}


def test_pending_sensor_claims_discovered_materials(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    platform = _platform(tmp_path)
    ingest_source_job.execute_in_process(
        run_config={
            "ops": {"ingest_source": {"config": {"path": str(archive)}}}
        },
        resources={"platform": platform},
    )

    context = dg.build_sensor_context(resources={"platform": platform})
    tick = pending_materials_sensor.evaluate_tick(context)
    requests = list(tick.run_requests or [])
    assert len(requests) == 3
    assert all(req.run_key and req.run_key.endswith(":process-v1") for req in requests)
    assert all(UUID(req.tags["material_id"]) for req in requests)

    loaded = _materials(platform)
    assert {item.status for item in loaded} == {MaterialStatus.PROCESSING}


def test_process_retry_delay_is_seconds() -> None:
    policy = process_material.retry_policy
    assert policy is not None
    assert policy.delay == 2
    assert policy.max_retries == 2


def test_reingest_job_after_restart_does_not_duplicate(tmp_path: Path) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    data_dir = str(tmp_path / "data")
    run_config = {
        "ops": {"ingest_source": {"config": {"path": str(archive)}}}
    }
    first = ingest_source_job.execute_in_process(
        run_config=run_config,
        resources={
            "platform": PlatformResource(data_dir=data_dir, use_sqlite=True)
        },
    )
    second = ingest_source_job.execute_in_process(
        run_config=run_config,
        resources={
            "platform": PlatformResource(data_dir=data_dir, use_sqlite=True)
        },
    )
    assert first.success and second.success
    assert first.output_for_node("ingest_source") == second.output_for_node(
        "ingest_source"
    )
