from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_tenant_id
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.schemas.dashboard import BundleHealthSummary, DashboardStats, RecurringFinding

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def compute_health_score(findings: list) -> tuple[int, str]:
    """
    Score starts at 100.
    Deduct: critical=-30 each, high=-15 each, medium=-7 each, low=-2 each
    Clamp to 0-100.
    Color: score>=80="green", score>=50="yellow", score>=25="orange", else="red"
    Only count open findings (status != "resolved").
    """
    score = 100
    for f in findings:
        if f.status == "resolved":
            continue
        if f.severity == "critical":
            score -= 30
        elif f.severity == "high":
            score -= 15
        elif f.severity == "medium":
            score -= 7
        elif f.severity == "low":
            score -= 2

    score = max(0, min(100, score))

    if score >= 80:
        color = "green"
    elif score >= 50:
        color = "yellow"
    elif score >= 25:
        color = "orange"
    else:
        color = "red"

    return score, color


@router.get("", response_model=DashboardStats)
async def get_dashboard(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    # Fetch all bundles for tenant
    bundle_result = await db.execute(
        select(Bundle)
        .where(Bundle.tenant_id == tenant_id)
        .order_by(Bundle.created_at.desc())
    )
    bundles = bundle_result.scalars().all()

    total_bundles = len(bundles)
    bundles_ready = sum(1 for b in bundles if b.status == "ready")
    bundles_processing = sum(
        1 for b in bundles if b.status in ("uploaded", "processing")
    )
    bundles_error = sum(1 for b in bundles if b.status == "error")

    # Aggregate findings by severity across all bundles
    agg_by_severity: dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }
    total_open_findings = 0
    most_recent_critical: list[dict] = []
    bundle_summaries: list[BundleHealthSummary] = []

    for bundle in bundles:
        # Fetch all findings for this bundle
        finding_result = await db.execute(
            select(Finding).where(Finding.bundle_id == bundle.id)
        )
        findings = finding_result.scalars().all()

        # Per-bundle severity counts (open only)
        per_sev: dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        open_count = 0
        for f in findings:
            if f.status != "resolved":
                sev = f.severity if f.severity in per_sev else "info"
                per_sev[sev] += 1
                open_count += 1
                agg_by_severity[sev] += 1
                total_open_findings += 1

            # Collect recent critical/high open findings
            if f.severity in ("critical", "high") and f.status != "resolved":
                most_recent_critical.append(
                    {
                        "bundle_id": str(bundle.id),
                        "filename": bundle.original_filename,
                        "finding_title": f.title,
                        "rule_id": f.rule_id,
                        "created_at": f.created_at.isoformat(),
                    }
                )

        health_score, health_color = compute_health_score(findings)

        bundle_summaries.append(
            BundleHealthSummary(
                bundle_id=str(bundle.id),
                filename=bundle.original_filename,
                status=bundle.status,
                uploaded_at=bundle.created_at.isoformat(),
                health_score=health_score,
                health_color=health_color,
                findings_by_severity=per_sev,
                open_findings=open_count,
                total_findings=len(findings),
            )
        )

    # Sort most_recent_critical by created_at descending and take up to 5
    most_recent_critical.sort(key=lambda x: x["created_at"], reverse=True)
    most_recent_critical = most_recent_critical[:5]

    return DashboardStats(
        total_bundles=total_bundles,
        bundles_ready=bundles_ready,
        bundles_processing=bundles_processing,
        bundles_error=bundles_error,
        total_open_findings=total_open_findings,
        findings_by_severity=agg_by_severity,
        most_recent_critical=most_recent_critical,
        bundles=bundle_summaries,
    )


@router.get("/recurring", response_model=list[RecurringFinding])
async def get_recurring_findings(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[RecurringFinding]:
    """Return findings that recur across multiple bundles, ranked by frequency."""
    # Get all bundle IDs for this tenant
    bundle_result = await db.execute(
        select(Bundle.id).where(Bundle.tenant_id == tenant_id)
    )
    bundle_ids = [row[0] for row in bundle_result.all()]

    if not bundle_ids:
        return []

    # Count distinct bundles each rule_id appears in
    rows = await db.execute(
        select(
            Finding.rule_id,
            Finding.title,
            Finding.severity,
            func.count(Finding.bundle_id.distinct()).label("bundle_count"),
            func.count(Finding.id).label("total_occurrences"),
        )
        .where(Finding.bundle_id.in_(bundle_ids))
        .group_by(Finding.rule_id, Finding.title, Finding.severity)
        .having(func.count(Finding.bundle_id.distinct()) > 1)
        .order_by(func.count(Finding.bundle_id.distinct()).desc())
        .limit(10)
    )

    return [
        RecurringFinding(
            rule_id=row.rule_id,
            title=row.title,
            severity=row.severity,
            bundle_count=row.bundle_count,
            total_occurrences=row.total_occurrences,
        )
        for row in rows
    ]
