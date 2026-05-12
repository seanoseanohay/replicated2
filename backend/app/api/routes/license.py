from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.license import LicenseStatusRead
from app.services.license_service import get_license_status

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/license", tags=["license"])


@router.get("/status", response_model=LicenseStatusRead)
async def read_license_status(
    current_user: User = Depends(get_current_user),
) -> LicenseStatusRead:
    """Return current Replicated license status and entitlements."""
    status = get_license_status()
    logger.info("license_status_fetched", user=current_user.email if current_user else None)
    return LicenseStatusRead.model_validate(status)
