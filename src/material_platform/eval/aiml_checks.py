from __future__ import annotations

from collections.abc import Iterable

from material_platform.application.local import LocalIngest
from material_platform.application.process_material import ProcessResult
from material_platform.domain.material import Material
from material_platform.eval.aiml_corpus import (
    PACKAGES_ROOT,
    PEFT_ROOT,
    QLORA_PDF,
    SLP3_PDF,
    TRANSFORMERS_JS_ROOT,
    TRANSFORMERS_ROOT,
    expected_roots,
    expected_type,
)
from material_platform.index.payload import MATERIAL_UNIT_ID

_SKIPPED_MATERIAL_PARTS = ("node_modules", ".venv", "venv")
SLP3_MIN_PAGES = 400


def discovery_errors(materials: Iterable[Material]) -> tuple[str, ...]:
    items = tuple(materials)
    paths = [item.root_path for item in items]
    errors: list[str] = []
    for expected in expected_roots():
        if expected.endswith(".whl"):
            continue
        if not any(_path_matches(path, expected) for path in paths):
            errors.append(f"missing material {expected}")
    wheels = [
        path
        for path in paths
        if path.startswith(PACKAGES_ROOT) and path.endswith(".whl")
    ]
    if not wheels:
        errors.append("missing python wheel under packages/")
    for item in items:
        wanted = expected_type(item.root_path)
        if wanted is not None and item.material_type is not wanted:
            errors.append(
                f"{item.root_path} type {item.material_type} expected {wanted}"
            )
        if any(part in _SKIPPED_MATERIAL_PARTS for part in item.root_path.split("/")):
            errors.append(f"skipped tree became a material: {item.root_path}")
        if item.root_path.rstrip("/").endswith("/tests") or item.root_path == "tests/":
            errors.append(f"tests/ became a material: {item.root_path}")
    return tuple(errors)


def process_errors(results: Iterable[ProcessResult]) -> tuple[str, ...]:
    errors: list[str] = []
    by_path = {item.material.root_path: item for item in results}
    transformers = _find(by_path, TRANSFORMERS_ROOT)
    if transformers is not None:
        coverage = transformers.analysis.coverage
        deep = coverage.deeply_analyzed_files
        scanned = coverage.structurally_scanned_files
        if deep is not None and deep > 20:
            errors.append(f"transformers deep-read {deep} files, cap is 20")
        if scanned is None or scanned <= 20:
            errors.append(
                f"transformers structurally_scanned_files={scanned}, expected >> 20"
            )
        indexed = {
            unit.location.path
            for unit in transformers.research.content_units
            if unit.location.path
        }
        if len(indexed) > 20:
            errors.append(f"transformers indexed {len(indexed)} files, cap is 20")
        if any(
            path is not None and ("/tests/" in f"/{path}" or path.startswith("tests/"))
            for path in indexed
        ):
            errors.append("transformers indexed a tests/ file")
    slp3 = _find(by_path, SLP3_PDF)
    if slp3 is not None:
        pages = {
            unit.location.page
            for unit in slp3.research.content_units
            if unit.location.page is not None
        }
        if len(pages) < SLP3_MIN_PAGES:
            errors.append(f"slp3 has {len(pages)} pages, expected >= {SLP3_MIN_PAGES}")
        if slp3.analysis.coverage.mode != "hierarchical":
            errors.append(
                f"slp3 coverage {slp3.analysis.coverage.mode}, expected hierarchical"
            )
        title_page = next(
            (unit for unit in slp3.research.content_units if unit.location.page == 1),
            None,
        )
        if title_page is None or "Speech and Language Processing" not in (
            title_page.content or ""
        ):
            errors.append("slp3 page 1 missing title phrase")
    qlora = _find(by_path, QLORA_PDF)
    if qlora is not None and not any(
        "NormalFloat" in (unit.content or "") for unit in qlora.research.content_units
    ):
        errors.append("qlora units missing NormalFloat")
    for item in results:
        path = item.material.root_path
        if path.endswith(".whl") or path.endswith(".jar"):
            if item.analysis.coverage.mode != "artifact_metadata":
                errors.append(f"{path} coverage {item.analysis.coverage.mode}")
            if len(item.research.content_units) != 1:
                errors.append(f"{path} should be one artifact unit")
    peft = _find(by_path, PEFT_ROOT)
    if peft is not None and peft.analysis.coverage.mode != "structural_sample":
        errors.append(f"peft coverage {peft.analysis.coverage.mode}")
    js = _find(by_path, TRANSFORMERS_JS_ROOT)
    if js is not None and js.analysis.coverage.mode != "structural_sample":
        errors.append(f"transformers.js coverage {js.analysis.coverage.mode}")
    return tuple(errors)


def citation_errors(citations: Iterable[object]) -> tuple[str, ...]:
    errors: list[str] = []
    for hit in citations:
        text = str(getattr(hit, "citation", ""))
        path = getattr(getattr(hit, "location", None), "path", None)
        if MATERIAL_UNIT_ID in (text, path or ""):
            errors.append("cited __material__")
    return tuple(errors)


def ingest_errors(run: LocalIngest) -> tuple[str, ...]:
    return discovery_errors(run.ingest.materials) + process_errors(run.processed)


def format_errors(errors: tuple[str, ...], *, heading: str) -> str:
    if not errors:
        return f"{heading}: ok\n"
    lines = [f"{heading}: {len(errors)} issue(s)"]
    lines.extend(f"  - {item}" for item in errors)
    return "\n".join(lines) + "\n"


def _find(by_path: dict[str, ProcessResult], expected: str) -> ProcessResult | None:
    for path, item in by_path.items():
        if _path_matches(path, expected):
            return item
    return None


def _path_matches(path: str, expected: str) -> bool:
    if path == expected:
        return True
    if expected.endswith("/") and (path == expected or path.startswith(expected)):
        return True
    return expected.rstrip("/") in path.split("/") or path.endswith(expected)
