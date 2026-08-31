"""Initial sources, discovery, materials, and processing runs.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("original_name", sa.String(length=1024), nullable=False),
        sa.Column("raw_uri", sa.String(length=2048), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_sources_sha256", "sources", ["sha256"])

    op.create_table(
        "discovery_runs",
        sa.Column("discovery_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discovery_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["sources.source_id"]),
        sa.PrimaryKeyConstraint("discovery_run_id"),
    )
    op.create_index(
        "ix_discovery_runs_source_id",
        "discovery_runs",
        ["source_id"],
    )

    op.create_table(
        "discovery_nodes",
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discovery_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("node_kind", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["discovery_run_id"],
            ["discovery_runs.discovery_run_id"],
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.source_id"]),
        sa.ForeignKeyConstraint(["parent_node_id"], ["discovery_nodes.node_id"]),
        sa.PrimaryKeyConstraint("node_id"),
    )
    op.create_index(
        "ix_discovery_nodes_discovery_run_id",
        "discovery_nodes",
        ["discovery_run_id"],
    )

    op.create_table(
        "materials",
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discovery_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discovery_version", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=1024), nullable=False),
        sa.Column("root_path", sa.String(length=2048), nullable=False),
        sa.Column("content_root_uri", sa.String(length=2048), nullable=False),
        sa.Column("content_digest", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("material_type", sa.String(length=32), nullable=False),
        sa.Column("material_subtype", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.source_id"]),
        sa.ForeignKeyConstraint(["discovery_node_id"], ["discovery_nodes.node_id"]),
        sa.PrimaryKeyConstraint("material_id"),
        sa.UniqueConstraint("discovery_node_id"),
        sa.UniqueConstraint(
            "source_id",
            "root_path",
            "discovery_version",
            name="uq_materials_identity",
        ),
    )
    op.create_index("ix_materials_status", "materials", ["status"])

    op.create_table(
        "processing_runs",
        sa.Column("processing_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("processor_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dagster_run_id", sa.String(length=128), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["material_id"], ["materials.material_id"]),
        sa.PrimaryKeyConstraint("processing_run_id"),
    )
    op.create_index(
        "ix_processing_runs_material_id",
        "processing_runs",
        ["material_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_runs_material_id", table_name="processing_runs")
    op.drop_table("processing_runs")
    op.drop_index("ix_materials_status", table_name="materials")
    op.drop_table("materials")
    op.drop_index("ix_discovery_nodes_discovery_run_id", table_name="discovery_nodes")
    op.drop_table("discovery_nodes")
    op.drop_index("ix_discovery_runs_source_id", table_name="discovery_runs")
    op.drop_table("discovery_runs")
    op.drop_index("ix_sources_sha256", table_name="sources")
    op.drop_table("sources")
