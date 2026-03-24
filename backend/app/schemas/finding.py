import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bundle_id: uuid.UUID
    rule_id: str
    title: str
    severity: str
    summary: str
    evidence_ids: list[uuid.UUID]
    status: str
    reviewer_notes: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    ai_explanation: str | None
    ai_remediation: str | None
    ai_explained_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FindingListResponse(BaseModel):
    items: list[FindingRead]
    total: int


class FindingUpdate(BaseModel):
    status: str | None = None  # open | acknowledged | resolved
    reviewer_notes: str | None = None
    reviewed_by: str | None = None
