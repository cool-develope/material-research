"""Index entries for lexical and hashed-vector retrieval.

Revision ID: 0003_index_entries
Revises: 0002_classifications
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_index_entries"
down_revision: str | None = "0002_classifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "index_entries",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", sa.String(length=1024), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=1024), nullable=True),
        sa.Column("tokens", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.material_id"]),
        sa.PrimaryKeyConstraint("entry_id"),
        sa.UniqueConstraint(
            "material_id",
            "unit_id",
            "index_version",
            name="uq_index_entries_identity",
        ),
    )
    op.create_index(
        "ix_index_entries_material_id",
        "index_entries",
        ["material_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_index_entries_material_id", table_name="index_entries")
    op.drop_table("index_entries")
