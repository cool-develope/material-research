from pathlib import Path

import dagster as dg

from defs.resources import PlatformResource
from material_platform.application.ingest_source import IngestSourceService


class IngestConfig(dg.Config):
    path: str


@dg.op
def ingest_source(
    context: dg.OpExecutionContext,
    config: IngestConfig,
    platform: PlatformResource,
) -> list[str]:
    settings = platform.settings()
    with platform.session() as session:
        service = IngestSourceService.create(
            session,
            platform.store(),
            platform.workspace(),
            discovery_version=settings.discovery_version,
            max_archive_depth=settings.max_archive_depth,
            archive_limits=platform.archive_limits(),
        )
        result = service.ingest(Path(config.path))
    context.log.info("discovered %s materials", len(result.materials))
    return [str(item.material_id) for item in result.materials]


@dg.job
def ingest_source_job() -> None:
    ingest_source()
