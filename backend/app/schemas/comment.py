import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class CommentRead(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    actor: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment body must not be empty")
        if len(v) > 4096:
            raise ValueError("Comment body must be at most 4096 characters")
        return v
