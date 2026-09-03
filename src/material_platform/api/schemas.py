from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from material_platform.application.index import SEARCH_PAGE_DEFAULT, SEARCH_PAGE_MAX
from material_platform.domain.budgets import AgentMode
from material_platform.domain.citation import Citation
from material_platform.domain.enums import MaterialType
from material_platform.domain.research import ReportSection

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
    snippet: str = ""
    keywords: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    has_more: bool
    page_count: int = 0
    total: int = 0
    results: list[SearchHit]
    trace_url: str | None = None


class MaterialUnitHit(BaseModel):
    unit_type: str
    citation: str


class MaterialDetailResponse(BaseModel):
    material_id: UUID
    title: str
    material_type: str
    material_subtype: str | None = None
    root_path: str
    status: str
    summary: str
    purpose: str | None = None
    keywords: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    research_relevance: float | None = None
    units: list[MaterialUnitHit] = Field(default_factory=list)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: AgentMode | None = None
    thread_id: str | None = None

    @field_validator("query")
    @classmethod
    def _query(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("query is required")
        return text

    @field_validator("thread_id")
    @classmethod
    def _thread_id(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class ChatResponse(BaseModel):
    objective: str
    summary: str
    text: str
    sections: list[ReportSection]
    citations: list[Citation]
    mode: str
    thread_id: str
    trace_url: str | None = None


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    summary: str | None = None
    created_at: str
    ordinal: int


class ChatHistoryResponse(BaseModel):
    thread_id: str
    mode: str | None = None
    messages: list[ChatHistoryMessage]


class ChatThreadSummary(BaseModel):
    thread_id: str
    title: str
    mode: str | None = None
    updated_at: str
    messages: int


class ChatThreadListResponse(BaseModel):
    threads: list[ChatThreadSummary]


class HealthResponse(BaseModel):
    ok: Literal[True]


class SignUpRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("name is required")
        return text

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _email(value)

    @model_validator(mode="after")
    def _passwords(self) -> SignUpRequest:
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self


class SignInRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _email(value)


class UserResponse(BaseModel):
    user_id: UUID
    name: str
    email: str


def _email(value: str) -> str:
    text = value.strip().lower()
    local, _, domain = text.partition("@")
    if not local or "." not in domain:
        raise ValueError("valid email required")
    return text
