from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/v1/config", tags=["config"])


class PublicConfigRead(BaseModel):
    allow_registration: bool


@router.get("", response_model=PublicConfigRead)
async def read_public_config() -> PublicConfigRead:
    return PublicConfigRead(allow_registration=settings.ALLOW_REGISTRATION)
