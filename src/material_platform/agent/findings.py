from __future__ import annotations

from material_platform.agent.models import EvidenceItem, Finding
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer, clip


def build_findings(state: AgentState, *, tracer: Tracer) -> AgentState:
    with tracer.span("findings", evidence=len(state.evidence)):
        findings: list[Finding] = []
        for question in state.plan.questions:
            rows = [item for item in state.evidence if item.question_id == question.id]
            supporting = [
                item for item in rows if item.stance in {"supports", "neutral"}
            ]
            contradicting = [item for item in rows if item.stance == "contradicts"]
            if not rows:
                continue
            claim = _claim(supporting or rows)
            findings.append(
                Finding(
                    finding_id=f"F-{question.id}",
                    question_id=question.id,
                    claim=claim,
                    supporting_evidence=tuple(item.evidence_id for item in supporting),
                    contradicting_evidence=tuple(
                        item.evidence_id for item in contradicting
                    ),
                    confidence=0.5 if contradicting else 0.9,
                )
            )
        state.findings = findings
        tracer.event(
            "findings",
            count=len(findings),
            contradictions=sum(1 for item in findings if item.contradicting_evidence),
        )
        tracer.set_output(
            {
                "count": len(findings),
                "claims": [
                    {"id": item.finding_id, "claim": clip(item.claim)}
                    for item in findings
                ],
            }
        )
    return state


def _claim(rows: list[EvidenceItem]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for item in rows:
        key = _normalize(item.finding)
        if key in seen:
            continue
        seen.add(key)
        loc = item.citation.citation
        parts.append(f"{item.finding} ({loc})")
        if len(parts) >= 4:
            break
    return "; ".join(parts)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
