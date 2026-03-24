import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_recipients: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    slack_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notify_on_severities: Mapped[str] = mapped_column(
        String(128), nullable=False, default="critical,high"
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
