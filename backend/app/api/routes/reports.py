import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_tenant_id
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.reporting.report import build_markdown_report, build_report

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["reports"])


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


async def _get_findings_and_counts(bundle_id: uuid.UUID, db: AsyncSession):
    findings_result = await db.execute(
        select(Finding).where(Finding.bundle_id == bundle_id)
    )
    findings = list(findings_result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(Evidence).where(Evidence.bundle_id == bundle_id)
    )
    evidence_count = count_result.scalar_one()
    return findings, {"total": evidence_count}


@router.get("/{bundle_id}/report")
async def get_report_json(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bundle = await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    findings, evidence_counts = await _get_findings_and_counts(bundle_id, db)
    report = build_report(bundle, findings, evidence_counts)
    logger.info("report_generated", bundle_id=str(bundle_id), tenant_id=tenant_id)
    return report


@router.get("/{bundle_id}/report.md", response_class=PlainTextResponse)
async def get_report_markdown(
    bundle_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    bundle = await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    findings, evidence_counts = await _get_findings_and_counts(bundle_id, db)
    md = build_markdown_report(bundle, findings, evidence_counts)
    logger.info("report_markdown_generated", bundle_id=str(bundle_id), tenant_id=tenant_id)
    return PlainTextResponse(
        content=md,
        headers={
            "Content-Disposition": f'attachment; filename="report-{bundle_id}.md"'
        },
    )
