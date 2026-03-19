import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FindingEventRead(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    actor: str
    event_type: str
    old_value: str | None
    new_value: str | None
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
