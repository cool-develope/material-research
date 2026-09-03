from pathlib import Path

import pytest

from material_platform.analysis.factory import make_analyzer
from material_platform.analysis.llm import ANALYZER as LLM_ANALYZER
from material_platform.classification import classify_files
from material_platform.config import Settings
from material_platform.extraction import MaterialFile, extract_units
from material_platform.infrastructure.llm.openai_compat import (
    OpenAICompatClient,
    _chat_body,
    _parse_json,
)
from tests.unit.discovery.artifacts import write_wheel
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
    assert "alloys" in {item.lower() for item in analysis.topics}
    assert analysis.coverage.mode == "direct"
    assert analysis.coverage.analyzed_units == 2
    assert analysis.coverage.total_units == 2
    assert analysis.coverage.ratio == 1.0
    assert len(units) == 2
    assert "materials" in {item.lower() for item in analysis.keywords}
    assert "unicorn" not in {item.lower() for item in analysis.keywords}
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


def test_openai_compat_extracts_json_from_prose() -> None:
    parsed = _parse_json(
        'Sure, here is the plan.\n{"intent": "deepen", "objective": "auth"}\nDone.'
    )
    assert parsed["intent"] == "deepen"
    assert parsed["objective"] == "auth"


def test_openai_compat_joins_v1_chat_completions() -> None:
    client = OpenAICompatClient("http://127.0.0.1:11434/v1/", "ollama", "llama3.1")
    assert client._url == "http://127.0.0.1:11434/v1/chat/completions"


def test_openai_compat_disables_thinking() -> None:
    body = _chat_body("qwen3.5:0.8b", "hello")
    assert body["reasoning_effort"] == "none"
    assert body["response_format"] == {"type": "json_object"}


def test_llm_artifact_prompt_uses_metadata_only(tmp_path: Path) -> None:
    wheel = write_wheel(tmp_path / "requests-2.32.3-py3-none-any.whl")
    files = (MaterialFile(path=wheel.name, data=wheel.read_bytes()),)
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    stub = StubLlm()
    analyzer = make_analyzer(
        Settings(
            _env_file=None, analyzer="llm", llm_base_url="http://example.invalid/v1"
        ),
        client=stub,
    )
    analysis = analyzer.analyze(fake_material(wheel.name), decision, units, files=files)
    assert analysis.coverage.mode == "artifact_metadata"
    assert stub.prompts
    prompt = stub.prompts[0]
    assert "metadata only" in prompt
    assert "x = 1" not in prompt
    assert len(stub.prompts) == 1
