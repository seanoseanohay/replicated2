import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    tenant_id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
