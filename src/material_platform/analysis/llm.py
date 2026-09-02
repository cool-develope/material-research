from __future__ import annotations

from material_platform.analysis.deterministic import DeterministicAnalyzer
from material_platform.analysis.document import extractive_leaf, merge_leaves
from material_platform.analysis.group import group_units
from material_platform.analysis.keywords import grounded, unique
from material_platform.analysis.profile import MaterialProfile, budgets_of
from material_platform.analysis.profiler import build_profile
from material_platform.analysis.protocol import LlmClient
from material_platform.classification.deterministic import ClassificationDecision
from material_platform.config import Settings
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile

ANALYZER = "llm"
ANALYZER_VERSION = "v2"


class LlmAnalyzer:
    def __init__(self, client: LlmClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def analyze(
        self,
        material: Material,
        decision: ClassificationDecision,
        units: tuple[ContentUnit, ...],
        *,
        files: tuple[MaterialFile, ...] = (),
        profile: MaterialProfile | None = None,
    ) -> MaterialAnalysis:
        built = profile or build_profile(
            material,
            decision,
            units,
            files=files,
            settings=self._settings,
        )
        base = DeterministicAnalyzer(self._settings).analyze(
            material, decision, units, files=files, profile=built
        )
        payload = _synthesize(
            self._client, material, decision, units, built, self._settings
        )
        pool = built.candidate_keywords
        summary = _string(payload.get("summary")) or base.summary
        purpose = _string(payload.get("purpose")) or base.purpose
        keywords = grounded(
            payload.get("keywords") or payload.get("topics"), pool, limit=25
        ) or base.keywords
        topics = grounded(payload.get("topics"), pool, limit=12) or base.topics
        technologies = (
            unique(_strings(payload.get("technologies")), limit=8)
            or base.technologies
        )
        return base.model_copy(
            update={
                "title": base.title or _string(payload.get("title")) or "",
                "summary": summary,
                "purpose": purpose,
                "topics": topics,
                "keywords": keywords,
                "technologies": technologies,
                "research_relevance": _relevance(
                    payload.get("research_relevance"), base.research_relevance
                ),
                "analyzer": ANALYZER,
                "analyzer_version": ANALYZER_VERSION,
                "coverage": built.coverage,
            }
        )


def _synthesize(
    client: LlmClient,
    material: Material,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    profile: MaterialProfile,
    settings: Settings,
) -> dict[str, object]:
    budgets = budgets_of(settings)
    if profile.mode == "hierarchical":
        leaf = _hierarchy(
            client, units, profile, budgets.leaf_tokens, budgets.reduce_fanin
        )
        prompt = _final_prompt(material, decision, profile, leaf)
    else:
        prompt = _direct_prompt(material, decision, profile)
    return client.complete_json(prompt)


def _hierarchy(
    client: LlmClient,
    units: tuple[ContentUnit, ...],
    profile: MaterialProfile,
    leaf_tokens: int,
    fan_in: int,
) -> dict[str, object]:
    groups = group_units(units, target_tokens=leaf_tokens)
    leaves: list[dict[str, object]] = []
    pool = profile.candidate_keywords
    for group in groups:
        fallback = extractive_leaf(group)
        try:
            payload = client.complete_json(_leaf_prompt(group, pool))
            leaves.append(_merge_payload(fallback, payload, pool))
        except Exception:
            leaves.append(fallback)
    packed: tuple[dict[str, object], ...] = tuple(leaves)
    while len(packed) > 1:
        nxt: list[dict[str, object]] = []
        for start in range(0, len(packed), fan_in):
            batch = packed[start : start + fan_in]
            merged = merge_leaves(batch)
            try:
                payload = client.complete_json(_reduce_prompt(batch, pool))
                nxt.append(_merge_payload(merged, payload, pool))
            except Exception:
                nxt.append(merged)
        packed = tuple(nxt)
    return packed[0] if packed else {}


def _direct_prompt(
    material: Material, decision: ClassificationDecision, profile: MaterialProfile
) -> str:
    leaf = profile.section_digests[0] if profile.section_digests else {}
    kind = decision.material_type.value
    if profile.mode == "artifact_metadata":
        return (
            "Rewrite this packaged artifact profile from metadata only. "
            "Do not invent files, APIs, or runtime behavior. "
            "Do not assume the package was executed.\n"
            "Return JSON with keys: title, summary, purpose, topics, keywords, "
            "technologies, research_relevance.\n"
            "keywords: exact terms selected from candidates.\n"
            f"name: {material.name}\n"
            f"type: {kind}/{decision.subtype or '-'}\n"
            f"mode: {profile.mode}\n"
            f"candidates: {', '.join(profile.candidate_keywords[:40])}\n"
            f"identity: {profile.identity}\n"
            f"structure: {profile.structure}\n"
        )
    return (
        "Analyze this research material as a whole. "
        "Do not summarize a single page or file. "
        "Do not invent paths or page numbers.\n"
        "Return JSON with keys: title, summary, purpose, topics, keywords, "
        "technologies, research_relevance.\n"
        "summary: 2-4 sentences. topics: 5-12 semantic concepts. "
        "keywords: 10-25 exact terms selected from candidates. "
        "research_relevance: number between 0 and 1.\n"
        f"name: {material.name}\n"
        f"type: {kind}/{decision.subtype or '-'}\n"
        f"mode: {profile.mode}\n"
        f"candidates: {', '.join(profile.candidate_keywords[:40])}\n"
        f"digest: {leaf.get('summary') or ''}\n"
        f"identity: {profile.identity}\n"
        f"structure: {profile.structure}\n"
    )


def _final_prompt(
    material: Material,
    decision: ClassificationDecision,
    profile: MaterialProfile,
    leaf: dict[str, object],
) -> str:
    return _direct_prompt(material, decision, profile) + (
        f"reduced_summary: {leaf.get('summary') or ''}\n"
        f"reduced_topics: {leaf.get('topics') or []}\n"
    )


def _leaf_prompt(group: tuple[ContentUnit, ...], pool: tuple[str, ...]) -> str:
    body = "\n\n".join(
        f"[{unit.location.path or unit.unit_id}]\n{unit.content}" for unit in group
    )
    return (
        "Extract structured facts from this document slice. "
        "JSON keys: summary, main_points, topics, candidate_keywords, "
        "section_titles. Use only terms from candidates when listing keywords.\n"
        f"candidates: {', '.join(pool[:40])}\n\n{body[:12000]}"
    )


def _reduce_prompt(
    batch: tuple[dict[str, object], ...], pool: tuple[str, ...]
) -> str:
    return (
        "Merge these structured slice analyses. JSON keys: summary, "
        "main_points, topics, candidate_keywords. "
        "Keywords must be selected from candidates.\n"
        f"candidates: {', '.join(pool[:40])}\n"
        f"slices: {list(batch)[:8]}"
    )


def _merge_payload(
    fallback: dict[str, object], payload: dict[str, object], pool: tuple[str, ...]
) -> dict[str, object]:
    merged = dict(fallback)
    summary = _string(payload.get("summary"))
    if summary:
        merged["summary"] = summary
    topics = grounded(payload.get("topics"), pool, limit=12)
    if topics:
        merged["topics"] = list(topics)
    keywords = grounded(
        payload.get("candidate_keywords") or payload.get("keywords"),
        pool,
        limit=20,
    )
    if keywords:
        merged["candidate_keywords"] = list(keywords)
    return merged


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _relevance(value: object, fallback: float | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return fallback
    number = float(value)
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number
