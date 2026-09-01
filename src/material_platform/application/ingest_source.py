from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from material_platform.application.content import (
    copy_material_content,
    tree_digest,
    write_discovery_manifest,
)
from material_platform.discovery.archive import ArchiveLimits, SafeZipExpander
from material_platform.discovery.formats import type_from_hint
from material_platform.discovery.inspector import PathInspector
from material_platform.discovery.service import DiscoveryService
from material_platform.discovery.skips import is_skipped_name
from material_platform.domain.discovery import (
    DiscoveryManifest,
    DiscoveryNode,
    DiscoveryRun,
)
from material_platform.domain.enums import (
    DiscoveryRole,
    DiscoveryRunStatus,
    MaterialStatus,
    MaterialType,
    NodeKind,
    SourceStatus,
    SourceType,
)
from material_platform.domain.material import Material
from material_platform.domain.source import Source
from material_platform.infrastructure.database.repositories import (
    DiscoveryNodeRepository,
    DiscoveryRunRepository,
    MaterialRepository,
    SourceRepository,
)
from material_platform.infrastructure.object_store.digest import sha256_stream
from material_platform.infrastructure.object_store.paths import (
    material_content_root,
    raw_original,
)
from material_platform.infrastructure.object_store.protocol import ObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace

_DOCUMENT_SUFFIXES = frozenset(
    {".pdf", ".md", ".txt", ".rst", ".docx", ".doc", ".docm"}
)


def _material_name(root_path: str, node: DiscoveryNode) -> str:
    title = node.metadata.get("artifact_title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return Path(root_path.rstrip("/")).name or root_path


def _material_type(node: DiscoveryNode) -> tuple[MaterialType, str | None]:
    hint = node.metadata.get("material_hint")
    if isinstance(hint, str):
        mapped = type_from_hint(hint)
        if mapped is not None:
            return mapped
    suffix = Path(node.path).suffix.lower()
    if suffix in _DOCUMENT_SUFFIXES:
        return MaterialType.DOCUMENT, suffix.lstrip(".")
    return MaterialType.UNKNOWN, None


@dataclass(frozen=True)
class IngestResult:
    source: Source
    run: DiscoveryRun
    manifest: DiscoveryManifest
    materials: tuple[Material, ...]


class IngestSourceService:
    def __init__(
        self,
        session: Session,
        store: ObjectStore,
        discovery: DiscoveryService,
        *,
        discovery_version: str,
    ) -> None:
        self._session = session
        self._store = store
        self._discovery = discovery
        self._discovery_version = discovery_version
        self._sources = SourceRepository(session)
        self._runs = DiscoveryRunRepository(session)
        self._nodes = DiscoveryNodeRepository(session)
        self._materials = MaterialRepository(session)

    @classmethod
    def create(
        cls,
        session: Session,
        store: ObjectStore,
        workspace: TemporaryWorkspace,
        *,
        discovery_version: str,
        max_archive_depth: int,
        archive_limits: ArchiveLimits,
    ) -> IngestSourceService:
        discovery = DiscoveryService.default(
            expander=SafeZipExpander(archive_limits),
            workspace=workspace,
            max_archive_depth=max_archive_depth,
            discovery_version=discovery_version,
        )
        return cls(
            session,
            store,
            discovery,
            discovery_version=discovery_version,
        )

    def ingest(self, path: Path) -> IngestResult:
        path = path.resolve()
        source = self._register_source(path)
        run = DiscoveryRun(
            discovery_run_id=uuid4(),
            source_id=source.source_id,
            discovery_version=self._discovery_version,
            status=DiscoveryRunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self._runs.add(run)
        self._session.flush()

        try:
            manifest = self._discovery.discover(
                path,
                source_id=source.source_id,
                discovery_run_id=run.discovery_run_id,
            )
            self._nodes.add_all(list(manifest.nodes))
            self._session.flush()
            materials = self._upsert_materials(manifest)
            write_discovery_manifest(self._store, manifest)
            source = source.model_copy(update={"status": SourceStatus.COMPLETED})
            run = run.model_copy(
                update={
                    "status": DiscoveryRunStatus.SUCCEEDED,
                    "finished_at": datetime.now(UTC),
                }
            )
        except Exception as exc:
            source = source.model_copy(update={"status": SourceStatus.FAILED})
            run = run.model_copy(
                update={
                    "status": DiscoveryRunStatus.FAILED,
                    "finished_at": datetime.now(UTC),
                    "error": str(exc),
                }
            )
            self._sources.save(source)
            self._runs.save(run)
            raise
        finally:
            self._discovery.cleanup()

        self._sources.save(source)
        self._runs.save(run)
        self._session.flush()
        return IngestResult(
            source=source,
            run=run,
            manifest=manifest,
            materials=tuple(materials),
        )

    def _register_source(self, path: Path) -> Source:
        inspector = PathInspector()
        inspected = inspector.inspect(path)
        source_type = _source_type(inspected.node_kind)
        digest, size = _source_digest(path)
        existing = self._sources.get_by_sha256(digest)
        if existing is not None:
            return existing.model_copy(update={"status": SourceStatus.DISCOVERING})

        source_id = uuid4()
        raw_uri = raw_original(source_id)
        if path.is_file():
            with path.open("rb") as handle:
                self._store.put(uri=raw_uri, data=handle, size=size)
        source = Source(
            source_id=source_id,
            source_type=source_type,
            original_name=path.name,
            raw_uri=raw_uri if path.is_file() else f"file://{path}",
            sha256=digest,
            size_bytes=size,
            created_at=datetime.now(UTC),
            status=SourceStatus.DISCOVERING,
        )
        self._sources.add(source)
        self._session.flush()
        return source

    def _upsert_materials(self, manifest: DiscoveryManifest) -> list[Material]:
        created: list[Material] = []
        for node in manifest.nodes:
            if node.role is not DiscoveryRole.MATERIAL:
                continue
            created.append(self._upsert_material(node))
        return created

    def _upsert_material(self, node: DiscoveryNode) -> Material:
        existing = self._materials.get_by_identity(
            node.source_id,
            node.path,
            self._discovery_version,
        )
        material_id = existing.material_id if existing is not None else uuid4()
        local = node.metadata.get("local_path")
        if not isinstance(local, str):
            raise FileNotFoundError(f"missing local path for {node.path}")
        local_path = Path(local)
        digest = copy_material_content(
            self._store,
            material_id=material_id,
            local_path=local_path,
        )
        material_type, subtype = _material_type(node)
        origin = node.metadata.get("origin_chain", [])
        material = Material(
            material_id=material_id,
            source_id=node.source_id,
            discovery_node_id=node.node_id,
            discovery_version=self._discovery_version,
            name=_material_name(node.path, node),
            root_path=node.path,
            content_root_uri=material_content_root(material_id),
            content_digest=digest,
            status=MaterialStatus.DISCOVERED,
            created_at=(
                existing.created_at if existing is not None else datetime.now(UTC)
            ),
            material_type=material_type,
            material_subtype=subtype,
            metadata=_material_metadata(node, origin),
        )
        return self._materials.upsert(material)


def _material_metadata(
    node: DiscoveryNode, origin: object
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "origin_chain": origin,
        "material_hint": node.metadata.get("material_hint"),
    }
    for key in ("format", "package", "version", "artifact_title"):
        value = node.metadata.get(key)
        if value:
            metadata[key] = value
    return metadata


def _source_type(kind: NodeKind) -> SourceType:
    if kind is NodeKind.ARCHIVE:
        return SourceType.ARCHIVE
    if kind is NodeKind.DIRECTORY:
        return SourceType.DIRECTORY
    return SourceType.FILE


def _source_digest(path: Path) -> tuple[str, int]:
    if path.is_file():
        with path.open("rb") as handle:
            return sha256_stream(handle)
    entries: list[tuple[str, str]] = []
    total = 0
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path)
        if any(is_skipped_name(part) for part in relative.parts):
            continue
        with item.open("rb") as handle:
            digest, size = sha256_stream(handle)
        total += size
        entries.append((relative.as_posix(), digest))
    return tree_digest(entries), total
