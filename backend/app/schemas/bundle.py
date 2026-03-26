import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BundleCreate(BaseModel):
    filename: str
    original_filename: str
    size_bytes: int
    tenant_id: str = "default"
    s3_key: str | None = None


class BundleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    original_filename: str
    size_bytes: int
    status: str
    tenant_id: str
    s3_key: str | None
    error_message: str | None
    progress_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BundleListResponse(BaseModel):
    items: list[BundleRead]
    total: int
