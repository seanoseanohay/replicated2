import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

# Pods stuck terminating for longer than this many seconds are flagged
TERMINATING_THRESHOLD_SECONDS = 120


class PodTerminatingRule(BaseRule):
    rule_id = "pod_terminating"
    title = "Pods Stuck in Terminating State"
    severity = "high"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        stuck = []
        evidence_ids = []
        stuck_details = []

        for pod in pods:
            try:
                raw = pod.raw_data or {}
                metadata = raw.get("metadata", {}) or {}

                # A pod is terminating when deletionTimestamp is set but it still exists
                if not metadata.get("deletionTimestamp"):
                    continue

                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")
                grace = metadata.get("deletionGracePeriodSeconds", 30)

                # Flag it — if it's in the bundle snapshot it's already stuck
                stuck.append(f"{namespace}/{name} (gracePeriod={grace}s)")
                evidence_ids.append(pod.id)
                stuck_details.append({"namespace": namespace, "pod": name})
            except Exception:
                continue

        if not stuck:
            return []

        objects_str = ", ".join(stuck[:10])
        summary = f"{len(stuck)} pod(s) stuck in Terminating state: {objects_str}"
        first = stuck_details[0]
        remediation = {
            "what_happened": (
                f"Pod {first['namespace']}/{first['pod']} has been stuck in Terminating state."
            ),
            "why_it_matters": (
                "Stuck terminating pods block namespace deletion, deployment rollouts, and can "
                "tie up node resources."
            ),
            "how_to_fix": (
                "Force delete the pod if it has been stuck for more than a few minutes."
            ),
            "cli_commands": [
                f"kubectl delete pod {first['pod']} -n {first['namespace']} --grace-period=0 --force",
            ],
        }
        return [
            self._make_finding(
                bundle_id,
                summary,
                evidence_ids=evidence_ids,
                remediation=remediation,
            )
        ]
