from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe — always returns 200 if process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Readiness probe — checks DB, Redis, and S3."""
    checks: dict[str, str] = {}
    healthy = True

    # DB check
    try:
        from app.core.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    # Redis check
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings

        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    # S3 check
    try:
        from app.services.storage import storage_service

        storage_service.ensure_bucket_exists()
        checks["storage"] = "ok"
    except Exception as exc:
        checks["storage"] = f"warning: {exc}"

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=http_status,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )
