from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract


class IndexEntry(Contract):
    entry_id: UUID
    material_id: UUID
    unit_id: str
    index_version: str
    title: str
    content: str
    path: str | None = None
    page: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    section: str | None = None
    tokens: str = ""
    embedding: tuple[float, ...] = ()
