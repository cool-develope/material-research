from __future__ import annotations

from typing import Literal
from uuid import UUID

from material_platform.agent.budgets import STANDARD
from material_platform.domain.base import Contract
from material_platform.domain.citation import Citation

MAX_PLAN_QUESTIONS = STANDARD.plan_questions
MAX_SELECT_CALLS = STANDARD.select_calls
MAX_UNITS_PER_MATERIAL = STANDARD.units_per_material
MAX_EVIDENCE_PER_QUESTION = STANDARD.evidence_per_question
MAX_TOTAL_EVIDENCE = STANDARD.evidence_total
RAW_QUESTION_ID = "Q0"

QuestionStatus = Literal["pending", "researching", "covered", "gap", "unresolved"]
Priority = Literal["required", "optional"]
Stance = Literal["supports", "contradicts", "neutral"]


class ResearchQuestion(Contract):
    id: str
    question: str
    priority: Priority = "required"
    comparative: bool = False


class ResearchPlan(Contract):
    objective: str
    questions: tuple[ResearchQuestion, ...]


class EvidenceItem(Contract):
    evidence_id: str
    question_id: str
    material_id: UUID
    finding: str
    stance: Stance = "supports"
    citation: Citation


class Finding(Contract):
    finding_id: str
    question_id: str
    claim: str
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...] = ()
    confidence: float = 1.0


class QuestionState(Contract):
    question_id: str
    status: QuestionStatus = "pending"
    evidence_ids: tuple[str, ...] = ()
    material_ids: tuple[UUID, ...] = ()
    iterations: int = 0
    last_query: str = ""


class SearchAttempt(Contract):
    query: str
    question_id: str
    hits: int
    follow_up: bool = False


class ReportSection(Contract):
    question_id: str
    heading: str
    body: str
    citation_keys: tuple[str, ...] = ()


class ResearchReport(Contract):
    objective: str
    sections: tuple[ReportSection, ...]
    summary: str
    citations: tuple[Citation, ...]
    text: str
