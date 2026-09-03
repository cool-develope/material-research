from __future__ import annotations

from sqlalchemy.orm import Session

from material_platform.agent.compact import clip_answer
from material_platform.agent.models import ChatTurn, ResearchReport
from material_platform.infrastructure.database.chat_history import (
    ChatHistoryRepository,
    StoredChatThread,
    StoredChatThreadSummary,
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

    def list_threads(self, *, limit: int = 50) -> list[StoredChatThreadSummary]:
        return list(self._repo.list_threads(limit=limit))

    def compact_turns(self, thread_id: str) -> list[ChatTurn]:
        thread = self.get(thread_id)
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
