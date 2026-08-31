from uuid import UUID

import dagster as dg

from defs.resources import PlatformResource
from material_platform.application.process_material import ProcessMaterialService
from material_platform.infrastructure.database.repositories import MaterialRepository


class ProcessConfig(dg.Config):
    material_id: str


@dg.op(
    pool="document_extraction",
    retry_policy=dg.RetryPolicy(max_retries=2, delay=0.1),
)
def process_material(
    context: dg.OpExecutionContext,
    config: ProcessConfig,
    platform: PlatformResource,
) -> str:
    material_id = UUID(config.material_id)
    with platform.session() as session:
        material = MaterialRepository(session).get(material_id)
        if material is None:
            raise dg.Failure(f"unknown material {material_id}")
        result = ProcessMaterialService(
            session,
            platform.store(),
            pipeline_version=platform.settings().pipeline_version,
            dagster_run_id=context.run_id,
        ).process(material)
    context.log.info("material %s is %s", material_id, result.material.status.value)
    return str(result.material.material_id)


@dg.job
def process_material_job() -> None:
    process_material()
