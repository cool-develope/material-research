from __future__ import annotations

from material_platform.analysis.deterministic import analyze_units
from material_platform.analysis.digest import build_digest
from material_platform.analysis.protocol import LlmClient
from material_platform.classification.deterministic import ClassificationDecision
from material_platform.config import Settings
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit

ANALYZER = "llm"
ANALYZER_VERSION = "v1"


class LlmAnalyzer:
    def __init__(self, client: LlmClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def analyze(
        self,
        material: Material,
        decision: ClassificationDecision,
        units: tuple[ContentUnit, ...],
    ) -> MaterialAnalysis:
        base = analyze_units(material, decision, units)
        digest = build_digest(
            decision,
            units,
            digest_tokens=self._settings.analysis_digest_tokens,
            snippet_tokens=self._settings.analysis_snippet_tokens,
        )
        payload = self._client.complete_json(_prompt(material, decision, digest.text))
        summary = _string(payload.get("summary")) or base.summary
        purpose = _string(payload.get("purpose")) or base.purpose
        topics = _strings(payload.get("topics")) or base.topics
        technologies = _strings(payload.get("technologies")) or base.technologies
        return base.model_copy(
            update={
                "title": base.title or _string(payload.get("title")) or "",
                "summary": summary,
                "purpose": purpose,
                "topics": topics,
                "technologies": technologies,
                "research_relevance": _relevance(
                    payload.get("research_relevance"), base.research_relevance
                ),
                "analyzer": ANALYZER,
                "analyzer_version": ANALYZER_VERSION,
                "digest_units": digest.unit_count,
                "digest_tokens": digest.token_count,
                "omitted_units": digest.omitted_units,
            }
        )


def _prompt(material: Material, decision: ClassificationDecision, digest: str) -> str:
    kind = decision.material_type.value
    subtype = decision.subtype or "-"
    return (
        "Analyze this research material as a whole. "
        "Do not summarize a single page or file. "
        "Do not invent paths or page numbers.\n"
        "Return JSON with keys: title, summary, purpose, topics, "
        "technologies, research_relevance.\n"
        "summary: 2-4 sentences. topics: 5-12 keywords. "
        "research_relevance: number between 0 and 1.\n"
        f"name: {material.name}\n"
        f"type: {kind}/{subtype}\n\n"
        f"{digest}"
    )


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        key = item.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if len(out) >= 12:
            break
    return tuple(out)


def _relevance(value: object, fallback: float | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return fallback
    number = float(value)
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number
