import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_tenant_id, require_manager
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.user import User
from app.schemas.bundle import BundleListResponse, BundleRead
from app.services.storage import storage_service
from app.utils.security import sanitize_filename, validate_magic_bytes
from app.workers.tasks import process_bundle

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["bundles"])

ALLOWED_CONTENT_TYPES = {
    "application/gzip",
    "application/x-gzip",
    "application/x-tar",
    "application/zip",
    "application/octet-stream",
}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BundleRead)
@limiter.limit("10/minute")
async def upload_bundle(
    request: Request,
    file: UploadFile,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BundleRead:
    max_bytes = settings.MAX_BUNDLE_SIZE_MB * 1024 * 1024

    file_bytes = await file.read()

    # Validate magic bytes before size check
    if not validate_magic_bytes(file_bytes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Expected gzip or zip archive.",
        )

    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_BUNDLE_SIZE_MB} MB",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
        )

    try:
        safe_filename = sanitize_filename(file.filename)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    logger.info(
        "bundle_upload_start",
        filename=safe_filename,
        size=len(file_bytes),
        tenant_id=tenant_id,
    )

    try:
        s3_key = storage_service.upload_bundle(file_bytes, safe_filename, tenant_id)
    except Exception as exc:
        logger.error("bundle_upload_s3_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload bundle to storage",
        ) from exc

    bundle = Bundle(
        filename=s3_key.rsplit("/", 1)[-1],
        original_filename=safe_filename,
        size_bytes=len(file_bytes),
        status="uploaded",
        tenant_id=tenant_id,
        s3_key=s3_key,
    )
    db.add(bundle)
    await db.flush()
    await db.refresh(bundle)

    bundle_id = str(bundle.id)
    process_bundle.delay(bundle_id)
    logger.info("bundle_queued", bundle_id=bundle_id)

    return BundleRead.model_validate(bundle)


@router.get("", response_model=BundleListResponse)
async def list_bundles(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
) -> BundleListResponse:
    count_result = await db.execute(
        select(func.count()).select_from(Bundle).where(Bundle.tenant_id == tenant_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Bundle)
        .where(Bundle.tenant_id == tenant_id)
        .order_by(Bundle.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    bundles = result.scalars().all()

    return BundleListResponse(
        items=[BundleRead.model_validate(b) for b in bundles],
        total=total,
    )


@router.get("/{bundle_id}", response_model=BundleRead)
async def get_bundle(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BundleRead:
    result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
    return BundleRead.model_validate(bundle)


@router.delete("/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    _manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    # Delete from S3 (best-effort)
    if bundle.s3_key:
        try:
            storage_service.delete_bundle(bundle.s3_key)
        except Exception as exc:
            logger.warning("s3_delete_failed", s3_key=bundle.s3_key, error=str(exc))

    # Delete from DB (cascades to evidence + findings via DB cascade)
    await db.delete(bundle)
    await db.flush()
