"""Chat transcript tables for FastAPI history. Not agent LLM context.

Revision ID: 0005_chat_history
Revises: 0004_drop_index_entries
Create Date: 2026-09-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_chat_history"
down_revision: str | None = "0004_drop_index_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("thread_id"),
    )
    op.create_table(
        "chat_messages",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.thread_id"]),
        sa.PrimaryKeyConstraint("message_id"),
        sa.UniqueConstraint(
            "thread_id",
            "ordinal",
            name="uq_chat_messages_thread_ordinal",
        ),
    )
    op.create_index(
        "ix_chat_messages_thread_id",
        "chat_messages",
        ["thread_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
