from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import get_logger, setup_logging
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.bundles import router as bundles_router  # noqa: E402
from app.api.routes.evidence import router as evidence_router  # noqa: E402
from app.api.routes.findings import router as findings_router  # noqa: E402
from app.api.routes.reports import router as reports_router  # noqa: E402

app.include_router(health_router)
app.include_router(bundles_router)
app.include_router(evidence_router)
app.include_router(findings_router)
app.include_router(reports_router)
