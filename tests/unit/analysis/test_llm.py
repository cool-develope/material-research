import pytest

from material_platform.analysis.factory import make_analyzer
from material_platform.analysis.llm import ANALYZER as LLM_ANALYZER
from material_platform.analysis.openai_compat import (
    OpenAICompatClient,
    _chat_body,
    _parse_json,
)
from material_platform.config import Settings
from tests.unit.helpers.analysis import (
    StubLlm,
    document_decision,
    fake_material,
    page_unit,
)


def test_llm_analyzer_keeps_extracted_title_and_one_summary() -> None:
    unit = page_unit(1, "Introduction to materials")
    unit = unit.model_copy(
        update={"metadata": {**unit.metadata, "title": "Survey of Alloys"}}
    )
    units = (unit, page_unit(2, "Methods section"))
    stub = StubLlm()
    analyzer = make_analyzer(
        Settings(
            _env_file=None, analyzer="llm", llm_base_url="http://example.invalid/v1"
        ),
        client=stub,
    )
    analysis = analyzer.analyze(fake_material(), document_decision(), units)
    assert analysis.analyzer == LLM_ANALYZER
    assert analysis.title == "Survey of Alloys"
    assert analysis.summary == "A survey of alloys for research use."
    assert "alloys" in analysis.topics
    assert analysis.digest_units == 2
    assert analysis.omitted_units == 0
    assert len(units) == 2
    assert stub.prompts and "as a whole" in stub.prompts[0]


def test_llm_failure_falls_back_to_deterministic() -> None:
    units = (page_unit(1, "Introduction to materials"),)
    analyzer = make_analyzer(
        Settings(
            _env_file=None, analyzer="llm", llm_base_url="http://example.invalid/v1"
        ),
        client=StubLlm(error=RuntimeError("down")),
    )
    analysis = analyzer.analyze(fake_material(), document_decision(), units)
    assert analysis.analyzer == "deterministic"
    assert "Introduction to materials" in analysis.summary


def test_llm_without_base_url_raises() -> None:
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        make_analyzer(Settings(_env_file=None, analyzer="llm"))


def test_openai_compat_parses_fenced_json() -> None:
    parsed = _parse_json('```json\n{"summary": "ok"}\n```')
    assert parsed["summary"] == "ok"


def test_openai_compat_joins_v1_chat_completions() -> None:
    client = OpenAICompatClient("http://127.0.0.1:11434/v1/", "ollama", "llama3.1")
    assert client._url == "http://127.0.0.1:11434/v1/chat/completions"


def test_openai_compat_disables_thinking() -> None:
    body = _chat_body("qwen3.5:0.8b", "hello")
    assert body["reasoning_effort"] == "none"
