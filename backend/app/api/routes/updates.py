from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.update import UpdateStatusRead
from app.services.update_service import get_update_status

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/updates", tags=["updates"])


@router.get("/status", response_model=UpdateStatusRead)
async def read_update_status(
    current_user: User = Depends(get_current_user),
) -> UpdateStatusRead:
    """Return whether a newer app release is available from Replicated."""
    status = get_update_status()
    logger.info("update_status_fetched", user=current_user.email if current_user else None)
    return UpdateStatusRead.model_validate(status)
