from __future__ import annotations

from sqlalchemy.orm import Session

from material_platform.agent.models import ResearchReport
from material_platform.infrastructure.database.chat_history import (
    ChatHistoryRepository,
    StoredChatThread,
)


class ChatHistoryService:
    def __init__(self, session: Session) -> None:
        self._repo = ChatHistoryRepository(session)

    def record_turn(
        self,
        thread_id: str,
        *,
        query: str,
        report: ResearchReport,
        mode: str,
    ) -> None:
        self._repo.append_turn(
            thread_id,
            query=query,
            answer=report.text,
            summary=report.summary.strip() or None,
            mode=mode,
        )

    def get(self, thread_id: str) -> StoredChatThread | None:
        return self._repo.get_thread(thread_id)
