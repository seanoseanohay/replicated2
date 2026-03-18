import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bundle_id: uuid.UUID
    kind: str
    namespace: str | None
    name: str
    source_path: str
    raw_data: dict
    created_at: datetime


class EvidenceListResponse(BaseModel):
    items: list[EvidenceRead]
    total: int
