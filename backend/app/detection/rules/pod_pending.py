import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class PodPendingRule(BaseRule):
    rule_id = "pod_pending"
    title = "Pods Stuck in Pending State"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        pending_pods = []
        pending_ids = []
        for pod in pods:
            try:
                raw = pod.raw_data or {}
                phase = raw.get("status", {}).get("phase", "")
                if phase == "Pending":
                    namespace = pod.namespace or "default"
                    pending_pods.append(f"{namespace}/{pod.name}")
                    pending_ids.append(pod.id)
            except Exception:
                continue

        if not pending_pods:
            return []

        pods_str = ", ".join(pending_pods)
        summary = f"{len(pending_pods)} pod(s) stuck in Pending state: {pods_str}"
        return [self._make_finding(bundle_id, summary, evidence_ids=pending_ids)]
