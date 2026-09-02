from uuid import uuid4

import pytest

from material_platform.agent.models import MAX_SELECT_CALLS, ChatTurn
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

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
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

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
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


def test_quick_mode_caps_selects_below_standard() -> None:
    calls = {"n": 0}

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
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

    report = ResearchAgent(
        select, tracer=RecordingTracer(), client=Planner(), mode="quick"
    ).ask("root question")
    assert calls["n"] == 3
    assert calls["n"] < MAX_SELECT_CALLS
    assert report.text


def test_deep_mode_allows_more_selects_than_standard() -> None:
    calls = {"n": 0}

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        calls["n"] += 1
        return ()

    class Planner:
        def complete_json(self, prompt: str) -> dict[str, object]:
            return {
                "objective": "research",
                "questions": [
                    {"id": f"Q{index}", "question": f"topic {index} extra"}
                    for index in range(1, 10)
                ],
            }

    report = ResearchAgent(
        select, tracer=RecordingTracer(), client=Planner(), mode="deep"
    ).ask("root question")
    assert calls["n"] > MAX_SELECT_CALLS
    assert calls["n"] <= 16
    assert report.text


def test_unknown_agent_mode_raises() -> None:
    with pytest.raises(ValueError, match="unknown agent mode"):
        ResearchAgent(lambda *args, **kwargs: (), mode="turbo")


def test_ask_continues_thread() -> None:
    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        return (_hit("src/api.py"),)

    agent = ResearchAgent(select, tracer=RecordingTracer())
    agent.ask("handle_request")
    thread = agent.last_thread_id
    assert thread
    agent.ask("where is it defined", thread_id=thread)
    assert agent.last_state is not None
    assert [turn.query for turn in agent.last_state.conversation] == ["handle_request"]
    agent.ask("what else", thread_id=thread)
    assert agent.last_state is not None
    assert [turn.query for turn in agent.last_state.conversation] == [
        "handle_request",
        "where is it defined",
    ]


def test_ask_without_thread_id_starts_fresh() -> None:
    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        return (_hit("src/api.py"),)

    agent = ResearchAgent(select, tracer=RecordingTracer())
    agent.ask("handle_request")
    agent.ask("where is it defined")
    assert agent.last_state is not None
    assert agent.last_state.conversation == []


def test_planner_sees_compact_request_not_prior_report() -> None:
    marker = "UNIQUE_REPORT_MARKER"
    prompts: list[str] = []

    class Planner:
        def complete_json(self, prompt: str) -> dict[str, object]:
            prompts.append(prompt)
            return {
                "objective": "research",
                "questions": [{"id": "Q1", "question": "details"}],
            }

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        return (_hit("src/api.py", snippet=marker),)

    agent = ResearchAgent(select, tracer=RecordingTracer(), client=Planner())
    agent.ask("handle_request")
    first = len(prompts)
    agent.ask("where is it defined", thread_id=agent.last_thread_id)
    later = prompts[first:]
    plan_prompts = [item for item in later if "Split this research request" in item]
    assert plan_prompts
    assert "handle_request" in plan_prompts[0]
    assert marker not in plan_prompts[0]
    assert "# handle_request" not in plan_prompts[0]


def test_continue_state_compacts_older_turns() -> None:
    from material_platform.agent.compact import RECENT_TURNS
    from material_platform.agent.models import (
        ResearchPlan,
        ResearchQuestion,
        ResearchReport,
        ResearchRequest,
    )
    from material_platform.agent.state import AgentState, continue_state

    previous = AgentState(
        query="latest",
        plan=ResearchPlan(
            objective="latest",
            questions=(ResearchQuestion(id="Q0", question="latest"),),
        ),
        conversation=[ChatTurn(query=f"q{i}", answer=f"a{i}") for i in range(12)],
        request=ResearchRequest(objective="latest"),
        report=ResearchReport(
            objective="latest",
            sections=(),
            summary="summary",
            citations=(),
            text="UNIQUE_REPORT_MARKER full body",
        ),
    )
    nxt = continue_state(previous, "new")
    assert nxt.query == "new"
    assert nxt.evidence == []
    assert nxt.select_calls == 0
    assert len(nxt.conversation) == RECENT_TURNS
    assert nxt.conversation[-1].query == "latest"
    assert nxt.conversation[-1].answer == "summary"
    assert "UNIQUE_REPORT_MARKER" not in nxt.conversation[-1].answer
    assert nxt.summary is not None
    assert "q0" in nxt.summary.text
    assert nxt.request is not None
    assert nxt.request.objective == "new"


def test_sqlite_checkpointer_continues_thread(tmp_path) -> None:
    from material_platform.config import Settings
    from material_platform.infrastructure.langgraph_backends import make_checkpointer

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'material.db'}",
        workspace_root=tmp_path,
    )
    saver, _ref = make_checkpointer(settings)

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        return (_hit("src/api.py"),)

    agent = ResearchAgent(select, tracer=RecordingTracer(), checkpointer=saver)
    agent.ask("handle_request")
    agent.ask("where is it defined", thread_id=agent.last_thread_id)
    assert agent.last_state is not None
    assert [turn.query for turn in agent.last_state.conversation] == ["handle_request"]


def test_extract_strips_snippets_from_persisted_evidence() -> None:
    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        return (_hit("src/api.py", snippet="secret body text"),)

    agent = ResearchAgent(select, tracer=RecordingTracer())
    agent.ask("handle_request")
    assert agent.last_state is not None
    assert agent.last_state.evidence
    assert all(item.citation.snippet == "" for item in agent.last_state.evidence)


def test_extract_maps_pending_in_token_batches() -> None:
    from material_platform.agent.extract import extract_pending
    from material_platform.agent.models import ResearchPlan, ResearchQuestion
    from material_platform.agent.state import AgentState

    calls = {"n": 0}

    class Mapper:
        def complete_json(self, prompt: str) -> dict[str, object]:
            calls["n"] += 1
            return {"items": [{"index": 1, "finding": "claim", "stance": "supports"}]}

    long = "x" * 5000
    plan = ResearchPlan(
        objective="q",
        questions=(ResearchQuestion(id="Q0", question="q"),),
    )
    state = AgentState(query="q", plan=plan)
    state.pending_question = "Q0"
    state.pending = [
        _hit("a.py", snippet=long),
        _hit("b.py", snippet=long),
    ]
    state = extract_pending(state, tracer=RecordingTracer(), client=Mapper())
    assert calls["n"] == 2
    assert len(state.evidence) == 2
    assert all(item.citation.snippet == "" for item in state.evidence)


def test_store_recalls_compact_memories_on_reference() -> None:
    from langgraph.store.memory import InMemoryStore

    prompts: list[str] = []

    class Planner:
        def complete_json(self, prompt: str) -> dict[str, object]:
            prompts.append(prompt)
            return {
                "objective": "research",
                "questions": [{"id": "Q1", "question": "details"}],
            }

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
        return (_hit("src/api.py"),)

    store = InMemoryStore()
    agent = ResearchAgent(
        select, tracer=RecordingTracer(), client=Planner(), store=store
    )
    agent.ask("handle_request")
    thread = agent.last_thread_id
    saved = store.search((thread,), limit=10)
    assert any(item.key == "request" for item in saved)
    first = len(prompts)
    agent.ask("as we said, where is auth", thread_id=thread)
    plan_prompts = [
        item for item in prompts[first:] if "Split this research request" in item
    ]
    assert plan_prompts
    assert "Recalled memories:" in plan_prompts[0]


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

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
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

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        **_: object,
    ):
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

    state, _thread = run_agent(
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


def test_findings_dedup_equivalent_claims() -> None:
    from material_platform.agent.findings import build_findings
    from material_platform.agent.models import (
        EvidenceItem,
        QuestionState,
        ResearchPlan,
        ResearchQuestion,
    )
    from material_platform.agent.state import AgentState

    first = _hit("src/api.py", snippet="oauth")
    second = _hit("src/auth.py", snippet="oauth")
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
            material_id=first.material_id,
            finding="Access tokens expire after 15 minutes",
            citation=first,
        ),
        EvidenceItem(
            evidence_id="E2",
            question_id="Q0",
            material_id=second.material_id,
            finding="access tokens expire after 15 minutes",
            citation=second,
        ),
    ]
    state = build_findings(state, tracer=RecordingTracer())
    assert len(state.findings) == 1
    assert state.findings[0].claim.count("15 minutes") == 1
    assert state.findings[0].supporting_evidence == ("E1", "E2")


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
