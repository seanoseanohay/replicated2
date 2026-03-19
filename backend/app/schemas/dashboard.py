from pydantic import BaseModel


class BundleHealthSummary(BaseModel):
    bundle_id: str
    filename: str
    status: str
    uploaded_at: str
    health_score: int           # 0-100
    health_color: str           # "green" | "yellow" | "orange" | "red"
    findings_by_severity: dict  # {"critical": 0, "high": 2, "medium": 3, "low": 1, "info": 0}
    open_findings: int
    total_findings: int


class DashboardStats(BaseModel):
    total_bundles: int
    bundles_ready: int
    bundles_processing: int
    bundles_error: int
    total_open_findings: int
    findings_by_severity: dict  # aggregate across all bundles
    most_recent_critical: list[dict]  # up to 5: {bundle_id, filename, finding_title, rule_id, created_at}
    bundles: list[BundleHealthSummary]  # all bundles with health scores
