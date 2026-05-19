from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import get_logger, setup_logging
from app.middleware.logging import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.services.license_service import is_license_valid
from app.services.storage import storage_service

setup_logging()
logger = get_logger(__name__)


async def _bootstrap_admin() -> None:
    """Create an admin account from env vars if it doesn't already exist."""
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return
    import uuid as _uuid
    from sqlalchemy import select as _select
    from app.core.database import AsyncSessionLocal
    from app.core.auth import hash_password
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            _select(User).where(
                User.email == settings.BOOTSTRAP_ADMIN_EMAIL,
                User.tenant_id == "default",
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.role = "admin"
            existing.hashed_password = hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD)
            existing.is_active = True
            await db.flush()
            await db.commit()
            logger.info("bootstrap_admin_updated", email=settings.BOOTSTRAP_ADMIN_EMAIL)
            return
        user = User(
            id=_uuid.uuid4(),
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            full_name="Admin",
            role="admin",
            tenant_id="default",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.commit()
        logger.info("bootstrap_admin_created", email=settings.BOOTSTRAP_ADMIN_EMAIL)


async def _bootstrap_notification_defaults() -> None:
    """Seed the default tenant's notification settings once from install defaults."""
    from sqlalchemy import select as _select
    from app.core.database import AsyncSessionLocal
    from app.models.notification_config import NotificationConfig

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            _select(NotificationConfig).where(NotificationConfig.tenant_id == "default")
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return
        config = NotificationConfig(
            tenant_id="default",
            email_enabled=settings.DEFAULT_EMAIL_NOTIFICATIONS_ENABLED,
            email_recipients=settings.DEFAULT_EMAIL_RECIPIENTS or None,
            slack_enabled=settings.DEFAULT_SLACK_NOTIFICATIONS_ENABLED,
            slack_webhook_url=settings.DEFAULT_SLACK_WEBHOOK_URL or None,
            notify_on_severities=settings.DEFAULT_NOTIFY_ON_SEVERITIES,
        )
        db.add(config)
        await db.flush()
        await db.commit()
        logger.info("bootstrap_notification_defaults_created", tenant_id="default")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup_begin")
    try:
        storage_service.ensure_bucket_exists()
    except Exception as exc:
        logger.warning("storage_init_failed", error=str(exc))
    try:
        await _bootstrap_admin()
    except Exception as exc:
        logger.warning("bootstrap_admin_failed", error=str(exc))
    try:
        await _bootstrap_notification_defaults()
    except Exception as exc:
        logger.warning("bootstrap_notification_defaults_failed", error=str(exc))

    # Start APScheduler for periodic metrics reporting (backend pod only)
    scheduler: BackgroundScheduler | None = None
    if settings.METRICS_ENABLED:
        from app.services.metrics_reporter import collect_and_send_metrics_sync

        scheduler = BackgroundScheduler()

        def _report_metrics() -> None:
            try:
                collect_and_send_metrics_sync()
            except Exception as exc:
                logger.warning("scheduled_metrics_report_failed", error=str(exc))

        scheduler.add_job(
            _report_metrics,
            "interval",
            hours=1,
            id="report-custom-metrics",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("metrics_scheduler_started", interval_hours=1)
    else:
        logger.info("metrics_scheduler_disabled")

    logger.info("startup_complete")
    yield
    if scheduler is not None and scheduler.running:
        scheduler.shutdown()
        logger.info("metrics_scheduler_shutdown")
    logger.info("shutdown")


app = FastAPI(
    title="Bundle Analyzer",
    version="0.1.0",
    description="Kubernetes support bundle analyzer",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware — order matters: request_id first (outermost), then access log
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# License enforcement middleware — blocks protected routes when license expired/invalid
_LICENSE_ALLOWLIST = {
    "/health",
    "/api/v1/auth",
    "/api/v1/config",
    "/api/v1/license",
    "/api/v1/updates",
}


@app.middleware("http")
async def license_check_middleware(request, call_next):
    path = request.url.path
    # Skip allowlisted paths and docs/redoc/openapi
    if any(path.startswith(prefix) for prefix in _LICENSE_ALLOWLIST):
        return await call_next(request)
    if path in ("/docs", "/redoc", "/openapi.json"):
        return await call_next(request)
    if not is_license_valid():
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={
                "detail": "License expired or invalid. Please contact support to renew.",
                "code": "LICENSE_INVALID",
            },
        )
    return await call_next(request)

# Routers
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.bundles import router as bundles_router  # noqa: E402
from app.api.routes.comments import router as comments_router  # noqa: E402
from app.api.routes.dashboard import router as dashboard_router  # noqa: E402
from app.api.routes.evidence import router as evidence_router  # noqa: E402
from app.api.routes.findings import router as findings_router  # noqa: E402
from app.api.routes.notifications import router as notifications_router  # noqa: E402
from app.api.routes.reports import router as reports_router  # noqa: E402
from app.api.routes.chat import router as chat_router  # noqa: E402
from app.api.routes.admin import router as admin_router  # noqa: E402
from app.api.routes.metrics import router as metrics_router  # noqa: E402
from app.api.routes.license import router as license_router  # noqa: E402
from app.api.routes.updates import router as updates_router  # noqa: E402
from app.api.routes.support_bundles import router as support_bundles_router  # noqa: E402
from app.api.routes.public_config import router as public_config_router  # noqa: E402

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(bundles_router)
app.include_router(chat_router)
app.include_router(metrics_router)
app.include_router(license_router)
app.include_router(updates_router)
app.include_router(comments_router)
app.include_router(dashboard_router)
app.include_router(evidence_router)
app.include_router(findings_router)
app.include_router(notifications_router)
app.include_router(reports_router)
app.include_router(support_bundles_router)
app.include_router(public_config_router)
