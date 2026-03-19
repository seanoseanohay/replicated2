import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationConfigRead(BaseModel):
    id: uuid.UUID
    tenant_id: str
    email_enabled: bool
    email_recipients: str | None
    slack_enabled: bool
    slack_webhook_url: str | None
    notify_on_severities: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationConfigUpdate(BaseModel):
    email_enabled: bool | None = None
    email_recipients: str | None = None
    slack_enabled: bool | None = None
    slack_webhook_url: str | None = None
    notify_on_severities: str | None = None
