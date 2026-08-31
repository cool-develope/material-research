"""Classification and artifact tables.

Revision ID: 0002_classifications
Revises: 0001_initial
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_classifications"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_classifications",
        sa.Column(
            "classification_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classifier", sa.String(length=64), nullable=False),
        sa.Column("classifier_version", sa.String(length=64), nullable=False),
        sa.Column("material_type", sa.String(length=32), nullable=False),
        sa.Column("material_subtype", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.material_id"]),
        sa.PrimaryKeyConstraint("classification_id"),
        sa.UniqueConstraint(
            "material_id",
            "classifier",
            "classifier_version",
            name="uq_material_classifications_identity",
        ),
    )
    op.create_index(
        "ix_material_classifications_material_id",
        "material_classifications",
        ["material_id"],
    )

    op.create_table(
        "material_artifacts",
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("processor", sa.String(length=64), nullable=False),
        sa.Column("processor_version", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.String(length=2048), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.material_id"]),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.UniqueConstraint(
            "material_id",
            "artifact_type",
            "processor",
            "processor_version",
            name="uq_material_artifacts_identity",
        ),
    )
    op.create_index(
        "ix_material_artifacts_material_id",
        "material_artifacts",
        ["material_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_material_artifacts_material_id",
        table_name="material_artifacts",
    )
    op.drop_table("material_artifacts")
    op.drop_index(
        "ix_material_classifications_material_id",
        table_name="material_classifications",
    )
    op.drop_table("material_classifications")
