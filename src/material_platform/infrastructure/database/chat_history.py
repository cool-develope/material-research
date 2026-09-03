from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from material_platform.infrastructure.database.models import (
    ChatMessageRow,
    ChatThreadRow,
)
from material_platform.infrastructure.database.repositories import BaseRepository


@dataclass(frozen=True)
class StoredChatMessage:
    role: str
    content: str
    summary: str | None
    created_at: datetime
    ordinal: int


@dataclass(frozen=True)
class StoredChatThread:
    thread_id: str
    mode: str | None
    messages: tuple[StoredChatMessage, ...]


@dataclass(frozen=True)
class StoredChatThreadSummary:
    thread_id: str
    title: str
    mode: str | None
    updated_at: datetime
    messages: int


class ChatHistoryRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def append_turn(
        self,
        thread_id: str,
        *,
        query: str,
        answer: str,
        summary: str | None,
        mode: str | None,
    ) -> None:
        now = datetime.now(UTC)
        thread = self._session.get(ChatThreadRow, thread_id)
        if thread is None:
            thread = ChatThreadRow(
                thread_id=thread_id,
                mode=mode,
                created_at=now,
                updated_at=now,
            )
            self._session.add(thread)
            next_ordinal = 0
        else:
            thread.updated_at = now
            if mode:
                thread.mode = mode
            current = self._session.scalar(
                select(func.max(ChatMessageRow.ordinal)).where(
                    ChatMessageRow.thread_id == thread_id
                )
            )
            next_ordinal = 0 if current is None else current + 1
        self._session.add(
            ChatMessageRow(
                message_id=uuid4(),
                thread_id=thread_id,
                ordinal=next_ordinal,
                role="user",
                content=query,
                summary=None,
                created_at=now,
            )
        )
        self._session.add(
            ChatMessageRow(
                message_id=uuid4(),
                thread_id=thread_id,
                ordinal=next_ordinal + 1,
                role="assistant",
                content=answer,
                summary=summary,
                created_at=now,
            )
        )

    def get_thread(self, thread_id: str) -> StoredChatThread | None:
        thread = self._session.get(ChatThreadRow, thread_id)
        if thread is None:
            return None
        rows = self._session.scalars(
            select(ChatMessageRow)
            .where(ChatMessageRow.thread_id == thread_id)
            .order_by(ChatMessageRow.ordinal)
        ).all()
        return StoredChatThread(
            thread_id=thread.thread_id,
            mode=thread.mode,
            messages=tuple(
                StoredChatMessage(
                    role=row.role,
                    content=row.content,
                    summary=row.summary,
                    created_at=row.created_at,
                    ordinal=row.ordinal,
                )
                for row in rows
            ),
        )

    def list_threads(self, *, limit: int = 50) -> tuple[StoredChatThreadSummary, ...]:
        threads = self._session.scalars(
            select(ChatThreadRow)
            .order_by(ChatThreadRow.updated_at.desc())
            .limit(limit)
        ).all()
        summaries: list[StoredChatThreadSummary] = []
        for thread in threads:
            first = self._session.scalar(
                select(ChatMessageRow)
                .where(
                    ChatMessageRow.thread_id == thread.thread_id,
                    ChatMessageRow.role == "user",
                )
                .order_by(ChatMessageRow.ordinal)
                .limit(1)
            )
            count = self._session.scalar(
                select(func.count())
                .select_from(ChatMessageRow)
                .where(ChatMessageRow.thread_id == thread.thread_id)
            )
            title = first.content.strip() if first is not None else "New chat"
            summaries.append(
                StoredChatThreadSummary(
                    thread_id=thread.thread_id,
                    title=title,
                    mode=thread.mode,
                    updated_at=thread.updated_at,
                    messages=int(count or 0),
                )
            )
        return tuple(summaries)
