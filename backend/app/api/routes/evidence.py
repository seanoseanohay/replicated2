import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_tenant_id
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceListResponse, EvidenceRead

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["evidence"])


@router.get("/{bundle_id}/evidence", response_model=EvidenceListResponse)
async def list_evidence(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    kind: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> EvidenceListResponse:
    # Verify bundle exists and belongs to the tenant
    bundle_result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = bundle_result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found"
        )

    # Build base query
    base_query = select(Evidence).where(Evidence.bundle_id == bundle_id)
    count_query = (
        select(func.count())
        .select_from(Evidence)
        .where(Evidence.bundle_id == bundle_id)
    )

    if kind is not None:
        base_query = base_query.where(Evidence.kind == kind)
        count_query = count_query.where(Evidence.kind == kind)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    evidence_result = await db.execute(
        base_query.order_by(Evidence.created_at.asc()).offset(skip).limit(limit)
    )
    evidence_items = evidence_result.scalars().all()

    logger.info(
        "evidence_listed",
        bundle_id=str(bundle_id),
        tenant_id=tenant_id,
        kind=kind,
        total=total,
        returned=len(evidence_items),
    )

    return EvidenceListResponse(
        items=[EvidenceRead.model_validate(e) for e in evidence_items],
        total=total,
    )


@router.get("/{bundle_id}/evidence/{evidence_id}", response_model=EvidenceRead)
async def get_evidence(
    bundle_id: uuid.UUID,
    evidence_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EvidenceRead:
    # Verify bundle exists and belongs to the tenant
    bundle_result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = bundle_result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found"
        )

    # Fetch the specific evidence record
    evidence_result = await db.execute(
        select(Evidence).where(
            Evidence.id == evidence_id, Evidence.bundle_id == bundle_id
        )
    )
    evidence = evidence_result.scalar_one_or_none()
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found"
        )

    logger.info(
        "evidence_fetched",
        bundle_id=str(bundle_id),
        evidence_id=str(evidence_id),
        tenant_id=tenant_id,
    )

    return EvidenceRead.model_validate(evidence)
