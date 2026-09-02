from material_platform.analysis.deterministic import DeterministicAnalyzer
from material_platform.analysis.llm import LlmAnalyzer
from material_platform.analysis.openai_compat import OpenAICompatClient
from material_platform.analysis.profile import MaterialProfile
from material_platform.analysis.protocol import Analyzer, LlmClient
from material_platform.classification.deterministic import ClassificationDecision
from material_platform.config import Settings
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile


class FallbackAnalyzer:
    def __init__(self, primary: Analyzer, fallback: Analyzer) -> None:
        self._primary = primary
        self._fallback = fallback

    def analyze(
        self,
        material: Material,
        decision: ClassificationDecision,
        units: tuple[ContentUnit, ...],
        *,
        files: tuple[MaterialFile, ...] = (),
        profile: MaterialProfile | None = None,
    ) -> MaterialAnalysis:
        try:
            return self._primary.analyze(
                material, decision, units, files=files, profile=profile
            )
        except Exception:
            return self._fallback.analyze(
                material, decision, units, files=files, profile=profile
            )


def make_llm_client(settings: Settings) -> OpenAICompatClient:
    if not settings.llm_base_url:
        raise ValueError("LLM_BASE_URL is required")
    return OpenAICompatClient(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
        timeout=float(settings.llm_timeout_seconds),
    )


def make_analyzer(settings: Settings, *, client: LlmClient | None = None) -> Analyzer:
    fallback = DeterministicAnalyzer(settings)
    kind = settings.analyzer.strip().lower()
    if kind in {"", "deterministic"}:
        return fallback
    if kind != "llm":
        raise ValueError(f"unknown analyzer: {settings.analyzer}")
    if client is None:
        if not settings.llm_base_url:
            raise ValueError("ANALYZER=llm requires LLM_BASE_URL")
        client = make_llm_client(settings)
    return FallbackAnalyzer(LlmAnalyzer(client, settings), fallback)
