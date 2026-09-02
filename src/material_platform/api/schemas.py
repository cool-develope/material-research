from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from material_platform.agent.budgets import AgentMode
from material_platform.agent.models import ReportSection
from material_platform.domain.citation import Citation
from material_platform.domain.enums import MaterialType
from material_platform.index.service import SEARCH_PAGE_DEFAULT, SEARCH_PAGE_MAX

_MATERIAL_TYPES = {item.value for item in MaterialType}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=SEARCH_PAGE_DEFAULT, ge=1, le=SEARCH_PAGE_MAX)
    material_type: str | None = None

    @field_validator("query")
    @classmethod
    def _query(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("query is required")
        return text

    @field_validator("material_type")
    @classmethod
    def _material_type(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        kind = value.strip().lower()
        if kind not in _MATERIAL_TYPES:
            raise ValueError(f"unknown material_type: {value}")
        return kind


class SearchHit(BaseModel):
    material_id: UUID
    title: str
    material_type: str
    root_path: str
    score: float
    siblings: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    has_more: bool
    results: list[SearchHit]
    trace_url: str | None = None


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: AgentMode | None = None

    @field_validator("query")
    @classmethod
    def _query(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("query is required")
        return text


class ChatResponse(BaseModel):
    objective: str
    summary: str
    text: str
    sections: list[ReportSection]
    citations: list[Citation]
    mode: str
    trace_url: str | None = None


class HealthResponse(BaseModel):
    ok: Literal[True]
