from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import get_logger, setup_logging
from app.middleware.logging import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.services.storage import storage_service

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup_begin")
    try:
        storage_service.ensure_bucket_exists()
    except Exception as exc:
        logger.warning("storage_init_failed", error=str(exc))
    logger.info("startup_complete")
    yield
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

# Routers
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.bundles import router as bundles_router  # noqa: E402
from app.api.routes.evidence import router as evidence_router  # noqa: E402
from app.api.routes.findings import router as findings_router  # noqa: E402
from app.api.routes.reports import router as reports_router  # noqa: E402

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(bundles_router)
app.include_router(evidence_router)
app.include_router(findings_router)
app.include_router(reports_router)
