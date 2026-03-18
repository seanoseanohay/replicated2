import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class PVCPendingRule(BaseRule):
    rule_id = "pvc_pending"
    title = "PersistentVolumeClaims Stuck in Pending State"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "PersistentVolumeClaim",
            )
        )
        pvcs = result.scalars().all()

        pending_pvcs = []
        pending_ids = []
        for pvc in pvcs:
            try:
                raw = pvc.raw_data or {}
                phase = raw.get("status", {}).get("phase", "")
                if phase == "Pending":
                    namespace = pvc.namespace or "default"
                    pending_pvcs.append(f"{namespace}/{pvc.name}")
                    pending_ids.append(pvc.id)
            except Exception:
                continue

        if not pending_pvcs:
            return []

        pvcs_str = ", ".join(pending_pvcs)
        summary = (
            f"{len(pending_pvcs)} PersistentVolumeClaim(s) stuck in Pending state: {pvcs_str}. "
            "Check that a StorageClass is available and has sufficient capacity."
        )
        return [self._make_finding(bundle_id, summary, evidence_ids=pending_ids)]
