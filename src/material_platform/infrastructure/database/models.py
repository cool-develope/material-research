from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonDoc = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class SourceRow(Base):
    __tablename__ = "sources"

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JsonDoc,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    discovery_runs: Mapped[list[DiscoveryRunRow]] = relationship(
        back_populates="source"
    )


class DiscoveryRunRow(Base):
    __tablename__ = "discovery_runs"

    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sources.source_id"),
        nullable=False,
        index=True,
    )
    discovery_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[SourceRow] = relationship(back_populates="discovery_runs")
    nodes: Mapped[list[DiscoveryNodeRow]] = relationship(back_populates="run")


class DiscoveryNodeRow(Base):
    __tablename__ = "discovery_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discovery_runs.discovery_run_id"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sources.source_id"),
        nullable=False,
    )
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discovery_nodes.node_id"),
        nullable=True,
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    node_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list[dict[str, object]]] = mapped_column(
        JsonDoc,
        nullable=False,
        default=list,
    )
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JsonDoc,
        nullable=False,
        default=dict,
    )

    run: Mapped[DiscoveryRunRow] = relationship(back_populates="nodes")
    source: Mapped[SourceRow] = relationship()
    parent: Mapped[DiscoveryNodeRow | None] = relationship(
        remote_side="DiscoveryNodeRow.node_id",
        foreign_keys="DiscoveryNodeRow.parent_node_id",
    )
    material: Mapped[MaterialRow | None] = relationship(back_populates="node")


class MaterialRow(Base):
    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "root_path",
            "discovery_version",
            name="uq_materials_identity",
        ),
        Index("ix_materials_status", "status"),
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sources.source_id"),
        nullable=False,
    )
    discovery_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discovery_nodes.node_id"),
        nullable=False,
        unique=True,
    )
    discovery_version: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    root_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_root_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    material_type: Mapped[str] = mapped_column(String(32), nullable=False)
    material_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JsonDoc,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source: Mapped[SourceRow] = relationship()
    node: Mapped[DiscoveryNodeRow] = relationship(back_populates="material")
    processing_runs: Mapped[list[ProcessingRunRow]] = relationship(
        back_populates="material"
    )
    classifications: Mapped[list[MaterialClassificationRow]] = relationship(
        back_populates="material"
    )
    artifacts: Mapped[list[MaterialArtifactRow]] = relationship(
        back_populates="material"
    )


class ProcessingRunRow(Base):
    __tablename__ = "processing_runs"

    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("materials.material_id"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dagster_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    material: Mapped[MaterialRow] = relationship(back_populates="processing_runs")


class MaterialClassificationRow(Base):
    __tablename__ = "material_classifications"
    __table_args__ = (
        UniqueConstraint(
            "material_id",
            "classifier",
            "classifier_version",
            name="uq_material_classifications_identity",
        ),
    )

    classification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("materials.material_id"),
        nullable=False,
        index=True,
    )
    classifier: Mapped[str] = mapped_column(String(64), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(64), nullable=False)
    material_type: Mapped[str] = mapped_column(String(32), nullable=False)
    material_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JsonDoc, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    material: Mapped[MaterialRow] = relationship(back_populates="classifications")


class MaterialArtifactRow(Base):
    __tablename__ = "material_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "material_id",
            "artifact_type",
            "processor",
            "processor_version",
            name="uq_material_artifacts_identity",
        ),
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("materials.material_id"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    processor: Mapped[str] = mapped_column(String(64), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    material: Mapped[MaterialRow] = relationship(back_populates="artifacts")


class UserRow(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class SessionRow(Base):
    __tablename__ = "sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ChatThreadRow(Base):
    __tablename__ = "chat_threads"

    thread_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        index=True,
    )
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    messages: Mapped[list[ChatMessageRow]] = relationship(
        back_populates="thread",
        order_by="ChatMessageRow.ordinal",
    )


class ChatMessageRow(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "thread_id",
            "ordinal",
            name="uq_chat_messages_thread_ordinal",
        ),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    thread_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("chat_threads.thread_id"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    thread: Mapped[ChatThreadRow] = relationship(back_populates="messages")
