from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from material_platform.agent.compact import clip_answer
from material_platform.domain.research import ChatTurn, ResearchReport
from material_platform.infrastructure.database.chat_history import (
    ChatHistoryRepository,
    StoredChatThread,
    StoredChatThreadSummary,
    ThreadAccessError,
)

__all__ = [
    "ChatHistoryService",
    "ThreadAccessError",
]


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
        user_id: UUID | None = None,
    ) -> None:
        self._repo.append_turn(
            thread_id,
            query=query,
            answer=report.text,
            summary=report.summary.strip() or None,
            mode=mode,
            user_id=user_id,
        )

    def get(
        self,
        thread_id: str,
        *,
        user_id: UUID | None = None,
    ) -> StoredChatThread | None:
        return self._repo.get_thread(thread_id, user_id=user_id)

    def list_threads(
        self,
        *,
        user_id: UUID | None = None,
        limit: int = 50,
    ) -> list[StoredChatThreadSummary]:
        return list(self._repo.list_threads(user_id=user_id, limit=limit))

    def compact_turns(
        self,
        thread_id: str,
        *,
        user_id: UUID | None = None,
    ) -> list[ChatTurn]:
        thread = self.get(thread_id, user_id=user_id)
        if thread is None:
            return []
        turns: list[ChatTurn] = []
        pending: str | None = None
        for item in thread.messages:
            if item.role == "user":
                pending = item.content
            elif item.role == "assistant" and pending is not None:
                turns.append(
                    ChatTurn(
                        query=pending,
                        answer=clip_answer(item.summary or item.content),
                    )
                )
                pending = None
        return turns
