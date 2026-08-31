from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from material_platform.domain.discovery import BoundaryEvidence


class BoundaryDecision(StrEnum):
    MATERIAL = "material"
    CONTAINER = "container"
    IGNORE = "ignore"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BoundaryResult:
    decision: BoundaryDecision
    confidence: float
    material_hint: str | None = None
    evidence: tuple[BoundaryEvidence, ...] = ()


class BoundaryDetector(Protocol):
    def detect(self, path: Path) -> BoundaryResult | None: ...


class CompositeBoundaryDetector:
    def __init__(self, detectors: Sequence[BoundaryDetector]) -> None:
        self._detectors = tuple(detectors)

    def detect(self, path: Path) -> BoundaryResult:
        for detector in self._detectors:
            result = detector.detect(path)
            if result is not None:
                return result
        return BoundaryResult(decision=BoundaryDecision.UNKNOWN, confidence=0.0)
