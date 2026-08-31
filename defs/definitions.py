from __future__ import annotations

import dagster as dg

from defs.jobs.ingest_source import ingest_source_job
from defs.jobs.process_material import process_material_job
from defs.resources import PlatformResource
from defs.sensors.pending_materials import pending_materials_sensor

defs = dg.Definitions(
    jobs=[ingest_source_job, process_material_job],
    sensors=[pending_materials_sensor],
    resources={"platform": PlatformResource()},
)
