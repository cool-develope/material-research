from __future__ import annotations

from pathlib import Path
from uuid import UUID

from material_platform.discovery.archive import SafeZipExpander, UnsafeArchiveError
from material_platform.discovery.archive_router import ArchiveRouter
from material_platform.discovery.boundary import (
    BoundaryDecision,
    BoundaryDetector,
    BoundaryResult,
)
from material_platform.discovery.context import DiscoveryContext
from material_platform.discovery.detectors import default_boundary_detector
from material_platform.discovery.inspector import PathInspection, PathInspector
from material_platform.discovery.skips import is_skipped_name
from material_platform.domain.discovery import DiscoveryManifest
from material_platform.domain.enums import DiscoveryRole, NodeKind
from material_platform.infrastructure.workspace import TemporaryWorkspace


class DiscoveryService:
    def __init__(
        self,
        *,
        inspector: PathInspector,
        router: ArchiveRouter,
        workspace: TemporaryWorkspace,
        boundary_detector: BoundaryDetector,
        max_archive_depth: int = 5,
        discovery_version: str = "boundary-v1",
    ) -> None:
        self._inspector = inspector
        self._router = router
        self._workspace = workspace
        self._boundary_detector = boundary_detector
        self._max_archive_depth = max_archive_depth
        self._discovery_version = discovery_version
        self._scratch_dirs: list[Path] = []

    @classmethod
    def default(
        cls,
        *,
        expander: SafeZipExpander,
        workspace: TemporaryWorkspace,
        max_archive_depth: int = 5,
        discovery_version: str = "boundary-v1",
    ) -> DiscoveryService:
        return cls(
            inspector=PathInspector(),
            router=ArchiveRouter(expander.limits, zip_expander=expander),
            workspace=workspace,
            boundary_detector=default_boundary_detector(),
            max_archive_depth=max_archive_depth,
            discovery_version=discovery_version,
        )

    def cleanup(self) -> None:
        for destination in self._scratch_dirs:
            if destination.exists():
                self._workspace.remove(destination)
        self._scratch_dirs.clear()

    def discover(
        self,
        path: Path,
        *,
        source_id: UUID,
        discovery_run_id: UUID,
    ) -> DiscoveryManifest:
        self.cleanup()
        context = DiscoveryContext(
            source_id=source_id,
            discovery_run_id=discovery_run_id,
        )
        self._discover_path(path, context, is_source_root=True)
        return DiscoveryManifest(
            source_id=source_id,
            discovery_run_id=discovery_run_id,
            discovery_version=self._discovery_version,
            nodes=tuple(context.nodes),
        )

    def _discover_path(
        self,
        path: Path,
        context: DiscoveryContext,
        *,
        is_source_root: bool,
    ) -> None:
        if not is_source_root and (is_skipped_name(path.name) or path.is_symlink()):
            return
        inspected = self._inspector.inspect(path)
        if inspected.is_archive:
            self._discover_archive(path, context, inspected)
            return
        if inspected.is_file:
            extra = dict(inspected.peek)
            extra["format"] = inspected.format
            context.record(
                path=context.logical_path(path.name, is_directory=False),
                node_kind=NodeKind.FILE,
                role=DiscoveryRole.MATERIAL,
                material_hint=inspected.material_hint,
                local_path=path,
                extra=extra,
            )
            return
        self._discover_directory(path, context, is_source_root=is_source_root)

    def _discover_archive(
        self,
        path: Path,
        context: DiscoveryContext,
        inspected: PathInspection,
    ) -> None:
        next_archive_depth = context.archive_depth + 1
        if next_archive_depth > self._max_archive_depth:
            raise UnsafeArchiveError("archive nesting exceeds limit")
        logical = context.logical_path(path.name, is_directory=False)
        container = context.record(
            path=logical,
            node_kind=NodeKind.ARCHIVE,
            role=DiscoveryRole.CONTAINER,
            include_path_in_origin=False,
            local_path=path,
            extra={"format": inspected.format},
        )
        destination = self._workspace.scratch_dir(
            context.source_id, container.node_id
        )
        expanded = self._router.expand(path, destination, inspected.format)
        self._scratch_dirs.append(destination)
        child = context.child(
            container,
            logical_prefix="",
            origin_chain=context.origin_chain + (path.name,),
            archive_depth=next_archive_depth,
        )
        for entry in _sorted_entries(expanded):
            self._discover_path(entry, child, is_source_root=False)

    def _discover_directory(
        self,
        path: Path,
        context: DiscoveryContext,
        *,
        is_source_root: bool,
    ) -> None:
        boundary = self._boundary_detector.detect(path)
        if boundary is None:
            boundary = BoundaryResult(BoundaryDecision.UNKNOWN, 0.0)
        logical = context.logical_path(path.name, is_directory=True)
        if boundary.decision is BoundaryDecision.IGNORE:
            return
        if boundary.decision is BoundaryDecision.MATERIAL:
            context.record(
                path=logical,
                node_kind=NodeKind.DIRECTORY,
                role=DiscoveryRole.MATERIAL,
                confidence=boundary.confidence,
                evidence=boundary.evidence,
                material_hint=boundary.material_hint,
                local_path=path,
            )
            return
        container = context.record(
            path=logical,
            node_kind=NodeKind.DIRECTORY,
            role=DiscoveryRole.CONTAINER,
            confidence=boundary.confidence,
            evidence=boundary.evidence,
            include_path_in_origin=False,
            local_path=path,
        )
        child_prefix = logical if not is_source_root else ""
        child = context.child(container, logical_prefix=child_prefix)
        for entry in _sorted_entries(path):
            self._discover_path(entry, child, is_source_root=False)


def _sorted_entries(path: Path) -> list[Path]:
    return sorted(path.iterdir(), key=lambda entry: entry.name.lower())
