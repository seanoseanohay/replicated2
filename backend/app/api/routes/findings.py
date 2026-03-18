import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.schemas.finding import FindingListResponse, FindingRead, FindingUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["findings"])


def get_tenant_id(x_tenant_id: str = Header(default="default")) -> str:
    return x_tenant_id


async def _get_bundle_for_tenant(
    bundle_id: uuid.UUID, tenant_id: str, db: AsyncSession
) -> Bundle:
    result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
    return bundle


@router.get("/{bundle_id}/findings", response_model=FindingListResponse)
async def list_findings(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    severity: str | None = None,
    finding_status: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> FindingListResponse:
    await _get_bundle_for_tenant(bundle_id, tenant_id, db)

    base_query = select(Finding).where(Finding.bundle_id == bundle_id)
    count_query = select(func.count()).select_from(Finding).where(
        Finding.bundle_id == bundle_id
    )

    if severity is not None:
        base_query = base_query.where(Finding.severity == severity)
        count_query = count_query.where(Finding.severity == severity)
    if finding_status is not None:
        base_query = base_query.where(Finding.status == finding_status)
        count_query = count_query.where(Finding.status == finding_status)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    findings_result = await db.execute(
        base_query.order_by(Finding.created_at.asc()).offset(skip).limit(limit)
    )
    findings = findings_result.scalars().all()

    logger.info(
        "findings_listed",
        bundle_id=str(bundle_id),
        tenant_id=tenant_id,
        total=total,
        returned=len(findings),
    )

    return FindingListResponse(
        items=[FindingRead.model_validate(f) for f in findings],
        total=total,
    )


@router.patch("/{bundle_id}/findings/{finding_id}", response_model=FindingRead)
async def update_finding(
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    update: FindingUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> FindingRead:
    await _get_bundle_for_tenant(bundle_id, tenant_id, db)

    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id, Finding.bundle_id == bundle_id
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    if update.status is not None:
        finding.status = update.status
        finding.reviewed_at = datetime.now(timezone.utc)
    if update.reviewer_notes is not None:
        finding.reviewer_notes = update.reviewer_notes
    if update.reviewed_by is not None:
        finding.reviewed_by = update.reviewed_by

    finding.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(finding)

    logger.info(
        "finding_updated",
        finding_id=str(finding_id),
        bundle_id=str(bundle_id),
        tenant_id=tenant_id,
    )

    return FindingRead.model_validate(finding)


@router.post(
    "/{bundle_id}/findings/{finding_id}/explain",
    response_model=FindingRead,
)
async def explain_finding(
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> FindingRead:
    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are not enabled",
        )

    await _get_bundle_for_tenant(bundle_id, tenant_id, db)

    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id, Finding.bundle_id == bundle_id
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    # Fetch up to 5 evidence items by evidence_ids
    evidence_list = []
    if finding.evidence_ids:
        evidence_uuids = [uuid.UUID(str(eid)) for eid in finding.evidence_ids[:5]]
        ev_result = await db.execute(
            select(Evidence).where(Evidence.id.in_(evidence_uuids))
        )
        evidence_list = list(ev_result.scalars().all())

    from app.ai.explainer import explain_finding as _explain
    try:
        explanation, remediation = _explain(finding, evidence_list, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("ai_explain_error", finding_id=str(finding_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI explanation failed",
        ) from exc

    finding.ai_explanation = explanation
    finding.ai_remediation = remediation
    finding.ai_explained_at = datetime.now(timezone.utc)
    finding.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(finding)

    logger.info(
        "finding_explained",
        finding_id=str(finding_id),
        bundle_id=str(bundle_id),
    )

    return FindingRead.model_validate(finding)
