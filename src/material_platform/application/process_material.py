from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from material_platform.analysis import ANALYZER, ANALYZER_VERSION, analyze_units
from material_platform.application.content import load_material_files
from material_platform.application.queue import WorkQueue
from material_platform.classification import (
    CLASSIFIER,
    CLASSIFIER_VERSION,
    classify_files,
)
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.artifact import MaterialArtifact
from material_platform.domain.classification import MaterialClassification
from material_platform.domain.enums import MaterialStatus, ProcessingRunStatus
from material_platform.domain.material import Material
from material_platform.domain.research_material import ResearchMaterial
from material_platform.extraction import EXTRACTOR, EXTRACTOR_VERSION, extract_units
from material_platform.index import IndexService
from material_platform.infrastructure.database.repositories import (
    ArtifactRepository,
    ClassificationRepository,
    MaterialRepository,
    ProcessingRunRepository,
    SourceRepository,
)
from material_platform.infrastructure.object_store.digest import sha256_stream
from material_platform.infrastructure.object_store.paths import material_artifact
from material_platform.infrastructure.object_store.protocol import ObjectStore
from material_platform.research import (
    RESEARCH_PROCESSOR,
    RESEARCH_VERSION,
    build_research_material,
)


@dataclass(frozen=True)
class ProcessResult:
    material: Material
    classification: MaterialClassification
    research: ResearchMaterial
    analysis: MaterialAnalysis


class ProcessMaterialService:
    def __init__(
        self,
        session: Session,
        store: ObjectStore,
        *,
        pipeline_version: str = "process-v1",
        dagster_run_id: str | None = None,
        max_extract_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._session = session
        self._store = store
        self._dagster_run_id = dagster_run_id
        self._max_extract_bytes = max_extract_bytes
        self._sources = SourceRepository(session)
        self._materials = MaterialRepository(session)
        self._classifications = ClassificationRepository(session)
        self._artifacts = ArtifactRepository(session)
        self._runs = ProcessingRunRepository(session)
        self._index = IndexService(session)
        self._queue = WorkQueue(session, pipeline_version=pipeline_version)

    def process(self, material: Material) -> ProcessResult:
        claimed = self._queue.claim(material.material_id)
        if claimed is None:
            raise RuntimeError(f"could not claim material {material.material_id}")
        run = self._runs.get_latest(claimed.material_id)
        if run is not None:
            run = run.model_copy(
                update={
                    "status": ProcessingRunStatus.RUNNING,
                    "started_at": datetime.now(UTC),
                    "dagster_run_id": self._dagster_run_id or run.dagster_run_id,
                }
            )
            self._runs.save(run)
            self._session.flush()
        try:
            result = self._process(claimed)
            if run is not None:
                self._runs.save(
                    run.model_copy(
                        update={
                            "status": ProcessingRunStatus.SUCCEEDED,
                            "finished_at": datetime.now(UTC),
                        }
                    )
                )
            self._session.flush()
            return result
        except Exception as exc:
            failed = claimed.model_copy(update={"status": MaterialStatus.FAILED})
            self._materials.save(failed)
            if run is not None:
                self._runs.save(
                    run.model_copy(
                        update={
                            "status": ProcessingRunStatus.FAILED,
                            "finished_at": datetime.now(UTC),
                            "error": str(exc),
                        }
                    )
                )
            self._session.flush()
            raise

    def _process(self, material: Material) -> ProcessResult:
        files = load_material_files(
            self._store,
            material.material_id,
            max_bytes=self._max_extract_bytes,
        )
        decision = classify_files(tuple(item.path for item in files))
        classification = self._classifications.upsert(
            MaterialClassification(
                classification_id=uuid4(),
                material_id=material.material_id,
                material_type=decision.material_type,
                subtype=decision.subtype,
                confidence=decision.confidence,
                classifier=CLASSIFIER,
                classifier_version=CLASSIFIER_VERSION,
                evidence=decision.evidence,
                created_at=datetime.now(UTC),
            )
        )

        material = material.model_copy(
            update={
                "status": MaterialStatus.CLASSIFIED,
                "material_type": classification.material_type,
                "material_subtype": classification.subtype,
            }
        )
        self._materials.save(material)
        self._session.flush()

        units = extract_units(decision, files)
        self._store_json(
            material.material_id,
            artifact_type="extraction",
            processor=EXTRACTOR,
            processor_version=EXTRACTOR_VERSION,
            payload={"units": [unit.model_dump(mode="json") for unit in units]},
        )
        material = self._set_status(material, MaterialStatus.EXTRACTED)

        analysis = analyze_units(material, decision, units)
        self._store_json(
            material.material_id,
            artifact_type="analysis",
            processor=ANALYZER,
            processor_version=ANALYZER_VERSION,
            payload=analysis.model_dump(mode="json"),
        )
        material = self._set_status(material, MaterialStatus.ANALYZED)

        source = self._sources.get(material.source_id)
        if source is None:
            raise LookupError(f"missing source {material.source_id}")
        research = build_research_material(
            material, source, decision, units, analysis
        )
        self._store_json(
            material.material_id,
            artifact_type="research",
            processor=RESEARCH_PROCESSOR,
            processor_version=RESEARCH_VERSION,
            payload=research.model_dump(mode="json"),
        )

        self._index.replace(research)
        material = self._set_status(material, MaterialStatus.INDEXED)
        material = self._set_status(material, MaterialStatus.READY)
        return ProcessResult(
            material=material,
            classification=classification,
            research=research,
            analysis=analysis,
        )

    def _set_status(self, material: Material, status: MaterialStatus) -> Material:
        material = material.model_copy(update={"status": status})
        self._materials.save(material)
        self._session.flush()
        return material

    def _store_json(
        self,
        material_id: UUID,
        *,
        artifact_type: str,
        processor: str,
        processor_version: str,
        payload: dict[str, object],
    ) -> MaterialArtifact:
        body = json.dumps(payload, sort_keys=True).encode()
        uri = material_artifact(material_id, artifact_type, processor_version)
        digest, size = sha256_stream(BytesIO(body))
        self._store.put(
            uri=uri,
            data=BytesIO(body),
            size=size,
            content_type="application/json",
        )
        return self._artifacts.upsert(
            MaterialArtifact(
                artifact_id=uuid4(),
                material_id=material_id,
                artifact_type=artifact_type,
                processor=processor,
                processor_version=processor_version,
                storage_uri=uri,
                sha256=digest,
                created_at=datetime.now(UTC),
            )
        )
