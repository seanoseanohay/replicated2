import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

QUOTA_THRESHOLD = 0.9  # 90%


def _parse_quantity(value: str) -> float:
    """Parse a Kubernetes resource quantity string to a float."""
    if not value:
        return 0.0
    value = str(value).strip()
    # Handle common suffixes
    multipliers = {
        "Ki": 1024,
        "Mi": 1024 ** 2,
        "Gi": 1024 ** 3,
        "Ti": 1024 ** 4,
        "k": 1000,
        "m": 0.001,
        "M": 1000 ** 2,
        "G": 1000 ** 3,
    }
    for suffix, mult in multipliers.items():
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * mult
            except ValueError:
                return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


class ResourceQuotaRule(BaseRule):
    rule_id = "resource_quota"
    title = "Resource Quota Near Limit"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "ResourceQuota",
            )
        )
        quotas = result.scalars().all()

        for quota in quotas:
            try:
                raw = quota.raw_data or {}
                status = raw.get("status", {}) or {}
                hard = status.get("hard", {}) or {}
                used = status.get("used", {}) or {}

                near_limit_resources = []
                for resource, hard_val in hard.items():
                    used_val = used.get(resource, "0")
                    hard_num = _parse_quantity(str(hard_val))
                    used_num = _parse_quantity(str(used_val))
                    if hard_num > 0 and used_num / hard_num >= QUOTA_THRESHOLD:
                        pct = int(used_num / hard_num * 100)
                        near_limit_resources.append(
                            f"{resource} ({pct}% used: {used_val}/{hard_val})"
                        )

                if near_limit_resources:
                    namespace = quota.namespace or "default"
                    resources_str = ", ".join(near_limit_resources)
                    summary = (
                        f"ResourceQuota {namespace}/{quota.name} is near its limit for: {resources_str}"
                    )
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[quota.id])
                    )
            except Exception:
                continue

        return findings
