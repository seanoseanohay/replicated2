import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_tenant_id, require_manager
from app.core.logging import get_logger
from app.models.notification_config import NotificationConfig
from app.models.user import User
from app.schemas.notification import NotificationConfigRead, NotificationConfigUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/config", response_model=NotificationConfigRead)
async def get_notification_config(
    tenant_id: str = Depends(get_tenant_id),
    _manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> NotificationConfigRead:
    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        # Return a default (unsaved) config
        config = NotificationConfig(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email_enabled=False,
            slack_enabled=False,
            notify_on_severities="critical,high",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(config)
        await db.flush()
        await db.refresh(config)
    return NotificationConfigRead.model_validate(config)


@router.post("/config", response_model=NotificationConfigRead)
async def update_notification_config(
    update: NotificationConfigUpdate,
    tenant_id: str = Depends(get_tenant_id),
    _manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> NotificationConfigRead:
    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = NotificationConfig(tenant_id=tenant_id)
        db.add(config)

    if update.email_enabled is not None:
        config.email_enabled = update.email_enabled
    if update.email_recipients is not None:
        config.email_recipients = update.email_recipients
    if update.slack_enabled is not None:
        config.slack_enabled = update.slack_enabled
    if update.slack_webhook_url is not None:
        config.slack_webhook_url = update.slack_webhook_url
    if update.notify_on_severities is not None:
        config.notify_on_severities = update.notify_on_severities

    config.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(config)

    logger.info("notification_config_updated", tenant_id=tenant_id)
    return NotificationConfigRead.model_validate(config)
