import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bundles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Use generic JSON so the model works with SQLite in tests;
    # the alembic migration explicitly uses JSONB for PostgreSQL.
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_explained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_findings_bundle_id_severity", "bundle_id", "severity"),
        Index("ix_findings_bundle_id_status", "bundle_id", "status"),
    )
