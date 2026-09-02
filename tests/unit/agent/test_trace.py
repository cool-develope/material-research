from material_platform.agent.llm import TracedLlmClient
from material_platform.agent.trace import NoOpTracer, RecordingTracer, make_tracer


def test_make_tracer_without_keys_is_noop() -> None:
    tracer = make_tracer()
    assert isinstance(tracer, NoOpTracer)


def test_traced_llm_records_generation() -> None:
    tracer = RecordingTracer()

    class Inner:
        def complete_json(self, prompt: str) -> dict[str, object]:
            return {"ok": True, "echo": prompt}

    client = TracedLlmClient(Inner(), tracer, name="plan")
    payload = client.complete_json("hello world")
    assert payload["ok"] is True
    assert tracer.generations
    assert tracer.generations[0].name == "plan"
    assert "hello" in str(tracer.generations[0].attrs["prompt"])
    assert "llm" in [span.name for span in tracer.spans]
    llm = next(span for span in tracer.spans if span.name == "llm")
    assert llm.attrs.get("output") == {"ok": True, "echo": "hello world"}


def test_named_generations_match_graph_nodes() -> None:
    from uuid import uuid4

    from material_platform.agent.service import ResearchAgent
    from material_platform.domain.citation import Citation
    from material_platform.domain.research_material import ContentLocation

    class Script:
        def complete_json(self, prompt: str) -> dict[str, object]:
            if "Split this" in prompt:
                return {
                    "objective": "Auth",
                    "questions": [{"id": "Q1", "question": "What methods exist?"}],
                }
            if "Extract evidence" in prompt:
                return {
                    "items": [{"index": 1, "finding": "oauth", "stance": "supports"}]
                }
            if "Rewrite this section" in prompt:
                return {"body": "oauth (src/api.py lines 1-2)"}
            if "executive summary" in prompt:
                return {"summary": "oauth is used."}
            return {}

    hit = Citation(
        material_id=uuid4(),
        title="t",
        location=ContentLocation(path="src/api.py", line_start=1, line_end=2),
        citation="src/api.py lines 1-2",
        snippet="oauth",
        score=1.0,
    )
    tracer = RecordingTracer()
    ResearchAgent(
        lambda *args, **kwargs: (hit,),
        tracer=tracer,
        client=Script(),
    ).ask("Compare authentication")
    names = [item.name for item in tracer.generations]
    for required in ("plan", "extract", "write", "summary"):
        assert required in names
