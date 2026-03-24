import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_tenant_id, require_manager
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User
from app.schemas.bundle import BundleListResponse, BundleRead
from app.schemas.comparison import ComparisonResult, FindingSummary
from app.services.storage import storage_service
from app.utils.security import sanitize_filename, validate_magic_bytes
from app.workers.tasks import process_bundle, reanalyze_bundle

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


# NOTE: /compare must be defined BEFORE /{bundle_id} so FastAPI doesn't try
# to parse "compare" as a UUID path param.
@router.get("/compare", response_model=ComparisonResult)
async def compare_bundles(
    bundle_a: uuid.UUID = Query(..., description="ID of bundle A"),
    bundle_b: uuid.UUID = Query(..., description="ID of bundle B"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResult:
    # Validate both bundles belong to tenant
    result_a = await db.execute(
        select(Bundle).where(Bundle.id == bundle_a, Bundle.tenant_id == tenant_id)
    )
    b_a = result_a.scalar_one_or_none()
    if b_a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle A not found")

    result_b = await db.execute(
        select(Bundle).where(Bundle.id == bundle_b, Bundle.tenant_id == tenant_id)
    )
    b_b = result_b.scalar_one_or_none()
    if b_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle B not found")

    # Load findings for each bundle
    findings_a_result = await db.execute(
        select(Finding).where(Finding.bundle_id == bundle_a)
    )
    findings_a = findings_a_result.scalars().all()

    findings_b_result = await db.execute(
        select(Finding).where(Finding.bundle_id == bundle_b)
    )
    findings_b = findings_b_result.scalars().all()

    # Index by rule_id (last one wins if duplicates)
    a_by_rule: dict[str, Finding] = {f.rule_id: f for f in findings_a}
    b_by_rule: dict[str, Finding] = {f.rule_id: f for f in findings_b}

    a_rules = set(a_by_rule.keys())
    b_rules = set(b_by_rule.keys())

    new_findings = [
        FindingSummary(
            rule_id=r,
            title=b_by_rule[r].title,
            severity=b_by_rule[r].severity,
            status=b_by_rule[r].status,
        )
        for r in sorted(b_rules - a_rules)
    ]
    resolved_findings = [
        FindingSummary(
            rule_id=r,
            title=a_by_rule[r].title,
            severity=a_by_rule[r].severity,
            status=a_by_rule[r].status,
        )
        for r in sorted(a_rules - b_rules)
    ]
    persisting_findings = [
        FindingSummary(
            rule_id=r,
            title=b_by_rule[r].title,
            severity=b_by_rule[r].severity,
            status=b_by_rule[r].status,
        )
        for r in sorted(a_rules & b_rules)
    ]

    return ComparisonResult(
        bundle_a_id=str(bundle_a),
        bundle_a_filename=b_a.original_filename,
        bundle_b_id=str(bundle_b),
        bundle_b_filename=b_b.original_filename,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        persisting_findings=persisting_findings,
        summary={
            "new": len(new_findings),
            "resolved": len(resolved_findings),
            "persisting": len(persisting_findings),
        },
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


@router.post("/{bundle_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
async def reanalyze_bundle_endpoint(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    if bundle.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bundle is already being processed",
        )

    bundle.status = "processing"
    await db.flush()

    reanalyze_bundle.delay(str(bundle_id))
    logger.info("bundle_reanalysis_queued", bundle_id=str(bundle_id))

    return {"bundle_id": str(bundle_id), "status": "processing"}


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
