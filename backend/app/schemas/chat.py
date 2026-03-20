import uuid
from datetime import datetime

from pydantic import BaseModel


class ChatMessageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    finding_id: uuid.UUID
    role: str
    content: str
    actor: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
