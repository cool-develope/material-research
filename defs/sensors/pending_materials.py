import dagster as dg

from defs.jobs.process_material import process_material_job
from defs.resources import PlatformResource
from material_platform.application.queue import WorkQueue, pipeline_run_key


@dg.sensor(
    job=process_material_job,
    minimum_interval_seconds=15,
    default_status=dg.DefaultSensorStatus.STOPPED,
)
def pending_materials_sensor(
    context: dg.SensorEvaluationContext,
    platform: PlatformResource,
) -> dg.SensorResult:
    settings = platform.settings()
    with platform.session() as session:
        claimed = WorkQueue(
            session,
            pipeline_version=settings.pipeline_version,
        ).claim_pending(limit=50)

    if not claimed:
        return dg.SensorResult(skip_reason="No pending materials.")

    requests = [
        dg.RunRequest(
            run_key=pipeline_run_key(
                material.material_id,
                settings.pipeline_version,
            ),
            run_config={
                "ops": {
                    "process_material": {
                        "config": {"material_id": str(material.material_id)}
                    }
                }
            },
            tags={
                "material_id": str(material.material_id),
                "source_id": str(material.source_id),
            },
        )
        for material in claimed
    ]
    context.log.info("claimed %s materials", len(requests))
    return dg.SensorResult(run_requests=requests)
