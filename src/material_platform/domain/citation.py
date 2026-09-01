from uuid import UUID

from material_platform.domain.base import Contract
from material_platform.domain.research_material import ContentLocation


class Citation(Contract):
    material_id: UUID
    title: str
    location: ContentLocation
    citation: str
    snippet: str
    score: float
