from __future__ import annotations

from material_platform.agent.context import chat_context, for_summary, for_write_section
from material_platform.agent.state import AgentState
from material_platform.domain.citation import Citation
from material_platform.domain.protocols import LlmClient
from material_platform.domain.research import ReportSection, ResearchReport
from material_platform.infrastructure.tracing.llm import named_llm
from material_platform.infrastructure.tracing.trace import Tracer, clip


def write_report(
    state: AgentState,
    *,
    tracer: Tracer,
    client: LlmClient | None = None,
) -> AgentState:
    with tracer.span("write", findings=len(state.findings)):
        by_id = {item.evidence_id: item for item in state.evidence}
        objective = state.plan.objective
        context = chat_context(state)
        sections: list[ReportSection] = []
        citations: list[Citation] = []
        for question in state.plan.questions:
            finding = next(
                (item for item in state.findings if item.question_id == question.id),
                None,
            )
            body = _section_body(finding, by_id)
            drafted = _llm_section(
                objective,
                question.question,
                body,
                named_llm(client, tracer, "write"),
                context=context,
            )
            if drafted:
                body = drafted
            keys = ()
            if finding is not None:
                keys = finding.supporting_evidence + finding.contradicting_evidence
                for key in keys:
                    item = by_id.get(key)
                    if item is not None:
                        citations.append(item.citation)
            sections.append(
                ReportSection(
                    question_id=question.id,
                    heading=question.question,
                    body=body,
                    citation_keys=keys,
                )
            )
        summary = _summary(
            objective,
            sections,
            named_llm(client, tracer, "summary"),
            context=context,
        )
        text = _render(objective, sections, summary)
        state.report = ResearchReport(
            objective=objective,
            sections=tuple(sections),
            summary=summary,
            citations=tuple(_dedupe(citations)),
            text=text,
        )
        tracer.event("write", sections=len(sections), citations=len(citations))
        tracer.set_output(
            {
                "summary": clip(summary),
                "sections": [
                    {
                        "id": item.question_id,
                        "heading": clip(item.heading),
                        "body": clip(item.body),
                    }
                    for item in sections
                ],
            }
        )
    return state


def _section_body(finding, by_id: dict) -> str:
    if finding is None:
        return "No evidence retrieved."
    lines = [finding.claim]
    if finding.contradicting_evidence:
        lines.append("Unresolved disagreement:")
        for key in finding.contradicting_evidence:
            item = by_id.get(key)
            if item is not None:
                lines.append(f"- {item.finding} ({item.citation.citation})")
    return "\n".join(lines)


def _summary(
    objective: str,
    sections: list[ReportSection],
    client: LlmClient | None,
    *,
    context: str = "",
) -> str:
    covered = [item.heading for item in sections if "No evidence" not in item.body]
    fallback = (
        f"{objective}. Covered: {'; '.join(covered)}."
        if covered
        else f"{objective}. Insufficient evidence."
    )
    if client is None:
        return fallback
    try:
        payload = client.complete_json(
            for_summary(objective, sections, context=context)
        )
    except Exception:
        return fallback
    text = payload.get("summary")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return fallback


def _llm_section(
    objective: str,
    heading: str,
    body: str,
    client: LlmClient | None,
    *,
    context: str = "",
) -> str | None:
    if client is None:
        return None
    try:
        payload = client.complete_json(
            for_write_section(objective, heading, body, context=context)
        )
    except Exception:
        return None
    text = payload.get("body")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _render(objective: str, sections: list[ReportSection], summary: str) -> str:
    parts = [f"# {objective}", ""]
    for section in sections:
        parts.append(f"## {section.question_id} {section.heading}")
        parts.append(section.body)
        parts.append("")
    parts.append("## Summary")
    parts.append(summary)
    return "\n".join(parts).strip() + "\n"


def _dedupe(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple] = set()
    out: list[Citation] = []
    for hit in citations:
        loc = hit.location
        key = (hit.material_id, loc.path, loc.page, loc.line_start, loc.line_end)
        if key in seen:
            continue
        seen.add(key)
        out.append(hit)
    return out
