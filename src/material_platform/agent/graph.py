from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from material_platform.agent.coverage import cover_state, follow_up_state, has_work
from material_platform.agent.extract import extract_pending
from material_platform.agent.findings import build_findings
from material_platform.agent.langfuse_trace import langfuse_handler
from material_platform.agent.models import MAX_SELECT_CALLS, ResearchReport
from material_platform.agent.planner import plan_state
from material_platform.agent.retrieve import SelectFn, retrieve_one
from material_platform.agent.state import AgentState, bootstrap
from material_platform.agent.synthesizer import write_report
from material_platform.agent.trace import Tracer, clip
from material_platform.agent.validate import validate_report
from material_platform.analysis.protocol import LlmClient
from material_platform.domain.citation import Citation


class GraphState(TypedDict):
    state: AgentState


def run_agent(
    query: str,
    select: SelectFn,
    *,
    tracer: Tracer,
    client: LlmClient | None = None,
) -> AgentState:
    compiled = _compile(select, tracer=tracer, client=client)
    with tracer.span("deep-research", query=query, runtime="langgraph"):
        result = compiled.invoke(
            {"state": bootstrap(query)},
            config=_config(query, tracer),
        )
        state = result["state"]
        tracer.event(
            "done",
            select_calls=state.select_calls,
            evidence=len(state.evidence),
            findings=len(state.findings),
            citations=len(state.report.citations) if state.report else 0,
        )
        tracer.set_output(
            {
                "text": clip(state.report.text) if state.report else "",
                "citations": (
                    len(state.report.citations) if state.report else 0
                ),
                "findings": len(state.findings),
                "select_calls": state.select_calls,
            }
        )
    tracer.flush()
    return state


def report_of(state: AgentState) -> ResearchReport:
    if state.report is None:
        raise RuntimeError("agent produced no report")
    return state.report


def citations_of(state: AgentState) -> tuple[Citation, ...]:
    return report_of(state).citations


def _compile(
    select: SelectFn, *, tracer: Tracer, client: LlmClient | None
) -> Any:
    def _plan(g: GraphState) -> GraphState:
        return {"state": plan_state(g["state"], tracer=tracer, client=client)}

    def _retrieve(g: GraphState) -> GraphState:
        return {"state": retrieve_one(g["state"], select, tracer=tracer)}

    def _extract(g: GraphState) -> GraphState:
        return {
            "state": extract_pending(g["state"], tracer=tracer, client=client)
        }

    def _cover(g: GraphState) -> GraphState:
        return {"state": cover_state(g["state"], tracer=tracer)}

    def _follow(g: GraphState) -> GraphState:
        return {
            "state": follow_up_state(g["state"], tracer=tracer, client=client)
        }

    def _route(g: GraphState) -> str:
        return "retrieve" if has_work(g["state"]) else "findings"

    def _findings(g: GraphState) -> GraphState:
        return {"state": build_findings(g["state"], tracer=tracer)}

    def _write(g: GraphState) -> GraphState:
        return {
            "state": write_report(g["state"], tracer=tracer, client=client)
        }

    def _validate(g: GraphState) -> GraphState:
        return {"state": validate_report(g["state"], tracer=tracer)}

    graph = StateGraph(GraphState)
    graph.add_node("plan", _plan)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("extract", _extract)
    graph.add_node("cover", _cover)
    graph.add_node("follow_up", _follow)
    graph.add_node("findings", _findings)
    graph.add_node("write", _write)
    graph.add_node("validate", _validate)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "extract")
    graph.add_edge("extract", "cover")
    graph.add_edge("cover", "follow_up")
    graph.add_conditional_edges(
        "follow_up", _route, {"retrieve": "retrieve", "findings": "findings"}
    )
    graph.add_edge("findings", "write")
    graph.add_edge("write", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def _config(query: str, tracer: Tracer) -> dict[str, object]:
    callbacks: list[object] = []
    if _has_langfuse(tracer):
        handler = langfuse_handler(
            session_id=getattr(tracer, "_session_id", None)
        )
        if handler is not None:
            callbacks.append(handler)
    session = getattr(tracer, "_session_id", None)
    return {
        "run_name": "deep-research",
        "recursion_limit": MAX_SELECT_CALLS * 5 + 16,
        "callbacks": callbacks,
        "metadata": {
            "query": clip(query),
            "langfuse_session_id": session or "",
            "langfuse_tags": ["deep-research"],
        },
    }


def _has_langfuse(tracer: Tracer) -> bool:
    from material_platform.agent.langfuse_trace import LangfuseTracer
    from material_platform.agent.trace import TeeTracer

    if isinstance(tracer, LangfuseTracer):
        return True
    if isinstance(tracer, TeeTracer):
        return any(isinstance(inner, LangfuseTracer) for inner in tracer.inners)
    return False
