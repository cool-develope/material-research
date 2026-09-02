from uuid import uuid4

from material_platform.agent.models import MAX_SELECT_CALLS
from material_platform.agent.service import ResearchAgent
from material_platform.agent.trace import RecordingTracer
from material_platform.domain.citation import Citation
from material_platform.domain.research_material import ContentLocation
from material_platform.index.payload import MATERIAL_UNIT_ID


def _hit(
    path: str, *, lines: tuple[int, int] = (1, 2), snippet: str = "body"
) -> Citation:
    return Citation(
        material_id=uuid4(),
        title="t",
        location=ContentLocation(path=path, line_start=lines[0], line_end=lines[1]),
        citation=f"{path} lines {lines[0]}-{lines[1]}",
        snippet=snippet,
        score=1.0,
    )


def test_first_select_is_raw_query_and_spans_are_traced() -> None:
    tracer = RecordingTracer()
    hit = _hit("src/api.py", snippet="def handle_request")
    queries: list[str] = []

    def select(query: str, *, limit: int = 5, material_type: str | None = None):
        queries.append(query)
        return (hit,)

    agent = ResearchAgent(select, tracer=tracer)
    report = agent.ask("handle_request")
    assert agent.last_select_queries[0] == "handle_request"
    assert queries[0] == "handle_request"
    assert any("src/api.py" in item.citation for item in report.citations)
    names = [span.name for span in tracer.spans]
    assert names[0] == "deep-research"
    for required in (
        "plan",
        "retrieve",
        "extract",
        "cover",
        "findings",
        "write",
        "validate",
    ):
        assert required in names
    retrieve = next(span for span in tracer.spans if span.name == "retrieve")
    assert retrieve.attrs.get("question_id") == "Q0"
    assert retrieve.attrs.get("query") == "handle_request"
    plan = next(span for span in tracer.spans if span.name == "plan")
    output = plan.attrs.get("output")
    assert isinstance(output, dict)
    questions = output.get("questions")
    assert isinstance(questions, list) and questions
    assert questions[0]["id"] == "Q0"
    assert "handle_request" in str(questions[0]["question"])
    assert any(event.name == "select" for event in tracer.events)
    done = next(event for event in tracer.events if event.name == "done")
    assert int(done.attrs["select_calls"]) >= 1


def test_select_budget_never_exceeds_max() -> None:
    calls = {"n": 0}

    def select(query: str, *, limit: int = 5, material_type: str | None = None):
        calls["n"] += 1
        return ()

    class Planner:
        def complete_json(self, prompt: str) -> dict[str, object]:
            return {
                "objective": "research",
                "questions": [
                    {"id": f"Q{index}", "question": f"topic {index} extra"}
                    for index in range(1, 8)
                ],
            }

    tracer = RecordingTracer()
    agent = ResearchAgent(select, tracer=tracer, client=Planner())
    report = agent.ask("root question")
    assert calls["n"] <= MAX_SELECT_CALLS
    assert report.text
    assert "Summary" in report.text


def test_material_point_is_never_a_citation() -> None:
    bad = Citation(
        material_id=uuid4(),
        title="t",
        location=ContentLocation(path=MATERIAL_UNIT_ID),
        citation=MATERIAL_UNIT_ID,
        snippet="summary only",
        score=1.0,
    )
    good = _hit("src/api.py")

    def select(query: str, *, limit: int = 5, material_type: str | None = None):
        return (bad, good)

    report = ResearchAgent(select, tracer=RecordingTracer()).ask("handle_request")
    assert all(MATERIAL_UNIT_ID not in item.citation for item in report.citations)
    assert all(item.location.path != MATERIAL_UNIT_ID for item in report.citations)


def test_report_sections_follow_questions() -> None:
    class Planner:
        def complete_json(self, prompt: str) -> dict[str, object]:
            return {
                "objective": "Auth comparison",
                "questions": [
                    {"id": "Q1", "question": "What methods exist?"},
                    {"id": "Q2", "question": "What is missing here xyzzy?"},
                ],
            }

    api = _hit("src/api.py", snippet="oauth")

    def select(query: str, *, limit: int = 5, material_type: str | None = None):
        if "xyzzy" in query or "missing" in query:
            return ()
        return (api,)

    tracer = RecordingTracer()
    report = ResearchAgent(select, tracer=tracer, client=Planner()).ask(
        "Compare authentication"
    )
    ids = [section.question_id for section in report.sections]
    assert ids[0] == "Q0"
    assert "Q1" in ids
    assert "Q2" in ids
    assert any(event.name == "follow_up" for event in tracer.events) or any(
        span.name == "follow_up" for span in tracer.spans
    )
    assert not any(section.heading.startswith("M") for section in report.sections)
    from material_platform.agent.graph import run_agent

    state = run_agent(
        "Compare authentication",
        select,
        tracer=RecordingTracer(),
        client=Planner(),
    )
    assert state.questions["Q0"].status in {"covered", "researching"}
    assert state.questions["Q2"].status in {"gap", "unresolved", "covered"}
    assert state.questions["Q2"].iterations >= 1


def test_validator_drops_summary_only_finding() -> None:
    from material_platform.agent.findings import build_findings
    from material_platform.agent.models import (
        EvidenceItem,
        ResearchPlan,
        ResearchQuestion,
    )
    from material_platform.agent.state import AgentState
    from material_platform.agent.synthesizer import write_report
    from material_platform.agent.validate import validate_report

    empty = Citation(
        material_id=uuid4(),
        title="t",
        location=ContentLocation(),
        citation="",
        snippet="from the summary",
        score=1.0,
    )
    plan = ResearchPlan(
        objective="q",
        questions=(ResearchQuestion(id="Q0", question="q"),),
    )
    state = AgentState(query="q", plan=plan)
    state.questions = {}
    state.evidence = [
        EvidenceItem(
            evidence_id="E1",
            question_id="Q0",
            material_id=empty.material_id,
            finding="from the summary",
            citation=empty,
        )
    ]
    from material_platform.agent.models import QuestionState

    state.questions = {"Q0": QuestionState(question_id="Q0")}
    tracer = RecordingTracer()
    state = build_findings(state, tracer=tracer)
    state = write_report(state, tracer=tracer)
    state = validate_report(state, tracer=tracer)
    assert state.report is not None
    assert state.report.citations == ()
    assert "No evidence" in state.report.text or not state.findings


def test_contradiction_is_kept_in_report() -> None:
    from material_platform.agent.findings import build_findings
    from material_platform.agent.models import (
        EvidenceItem,
        QuestionState,
        ResearchPlan,
        ResearchQuestion,
    )
    from material_platform.agent.state import AgentState
    from material_platform.agent.synthesizer import write_report

    left = _hit("src/api.py", snippet="oauth")
    right = _hit("src/auth.py", snippet="no oauth")
    plan = ResearchPlan(
        objective="auth",
        questions=(ResearchQuestion(id="Q0", question="auth"),),
    )
    state = AgentState(query="auth", plan=plan)
    state.questions = {"Q0": QuestionState(question_id="Q0")}
    state.evidence = [
        EvidenceItem(
            evidence_id="E1",
            question_id="Q0",
            material_id=left.material_id,
            finding="uses oauth",
            stance="supports",
            citation=left,
        ),
        EvidenceItem(
            evidence_id="E2",
            question_id="Q0",
            material_id=right.material_id,
            finding="no oauth",
            stance="contradicts",
            citation=right,
        ),
    ]
    tracer = RecordingTracer()
    state = build_findings(state, tracer=tracer)
    state = write_report(state, tracer=tracer)
    assert state.findings[0].contradicting_evidence
    assert "Unresolved disagreement" in (state.report.text if state.report else "")
    assert any(event.attrs.get("contradictions") == 1 for event in tracer.events)


def test_graph_is_compiled_langgraph() -> None:
    from material_platform.agent.graph import _compile

    compiled = _compile(
        lambda *args, **kwargs: (), tracer=RecordingTracer(), client=None
    )
    nodes = set(compiled.get_graph().nodes)
    required = (
        "plan",
        "retrieve",
        "extract",
        "cover",
        "follow_up",
        "findings",
        "write",
        "validate",
    )
    for name in required:
        assert name in nodes


