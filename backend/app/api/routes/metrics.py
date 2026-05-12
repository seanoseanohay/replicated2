from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.services.metrics_reporter import collect_and_send_metrics_sync

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.post("/report", dependencies=[Depends(require_admin)])
async def trigger_metrics_report(db: AsyncSession = Depends(get_db)) -> dict:
    """Manually trigger custom metrics reporting to the Replicated SDK."""
    result = collect_and_send_metrics_sync()
    if not result.get("sent"):
        detail = result.get("error") or "Failed to send metrics to Replicated SDK"
        raise HTTPException(status_code=503, detail=detail)
    return result
