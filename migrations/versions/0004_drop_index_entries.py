"""Drop live PostgreSQL retrieval rows. Search lives in Qdrant.

Revision ID: 0004_drop_index_entries
Revises: 0003_index_entries
Create Date: 2026-09-01

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_drop_index_entries"
down_revision: str | None = "0003_index_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_index_entries_material_id", table_name="index_entries")
    op.drop_table("index_entries")


def downgrade() -> None:
    raise NotImplementedError("restore index_entries from 0003 if needed")
