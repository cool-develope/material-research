from __future__ import annotations

from material_platform.agent.models import Finding, ResearchReport
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer, clip
from material_platform.domain.citation import Citation
from material_platform.index.payload import MATERIAL_UNIT_ID


def validate_report(state: AgentState, *, tracer: Tracer) -> AgentState:
    report = state.report
    if report is None:
        return state
    with tracer.span("validate", findings=len(state.findings)):
        by_id = {item.evidence_id: item for item in state.evidence}
        kept_findings: list[Finding] = []
        for finding in state.findings:
            if _finding_ok(finding, by_id):
                kept_findings.append(finding)
        state.findings = kept_findings
        allowed = {
            _key(item.citation)
            for item in state.evidence
            if _unit_ok(item.citation)
        }
        citations = tuple(
            hit for hit in report.citations if _key(hit) in allowed and _unit_ok(hit)
        )
        sections = []
        for section in report.sections:
            keys = tuple(
                key
                for key in section.citation_keys
                if key in by_id and _unit_ok(by_id[key].citation)
            )
            body = section.body
            if not keys and "No evidence" not in body:
                if not any(_unit_ok(hit) for hit in citations):
                    body = "No evidence retrieved."
            sections.append(
                section.model_copy(update={"citation_keys": keys, "body": body})
            )
        text = _rereender(report.objective, sections, report.summary)
        state.report = ResearchReport(
            objective=report.objective,
            sections=tuple(sections),
            summary=report.summary,
            citations=citations,
            text=text,
        )
        tracer.event(
            "validate",
            findings=len(kept_findings),
            citations=len(citations),
        )
        tracer.set_output(
            {
                "findings": len(kept_findings),
                "citations": len(citations),
                "summary": clip(report.summary),
            }
        )
    return state


def _finding_ok(finding: Finding, by_id: dict) -> bool:
    keys = finding.supporting_evidence + finding.contradicting_evidence
    if not keys:
        return False
    return any(
        key in by_id and _unit_ok(by_id[key].citation) for key in keys
    )


def _unit_ok(hit: Citation) -> bool:
    if hit.citation.strip() == MATERIAL_UNIT_ID:
        return False
    if MATERIAL_UNIT_ID in (hit.citation, hit.location.path or ""):
        return False
    loc = hit.location
    if loc.page is not None:
        return True
    if loc.line_start is not None and loc.line_end is not None:
        return True
    return bool(loc.path)


def _key(hit: Citation) -> tuple:
    loc = hit.location
    return (hit.material_id, loc.path, loc.page, loc.line_start, loc.line_end)


def _rereender(objective: str, sections: list, summary: str) -> str:
    parts = [f"# {objective}", ""]
    for section in sections:
        parts.append(f"## {section.question_id} {section.heading}")
        parts.append(section.body)
        parts.append("")
    parts.append("## Summary")
    parts.append(summary)
    return "\n".join(parts).strip() + "\n"
