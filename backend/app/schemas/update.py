from pydantic import BaseModel


class UpdateStatusRead(BaseModel):
    available: bool
    version: str | None
    notes: str | None
    license_valid: bool | None
    current_version: str | None
