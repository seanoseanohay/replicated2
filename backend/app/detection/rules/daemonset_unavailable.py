import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class DaemonSetUnavailableRule(BaseRule):
    rule_id = "daemonset_unavailable"
    title = "DaemonSet Not Fully Scheduled"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "DaemonSet",
            )
        )
        daemonsets = result.scalars().all()

        unavailable = []
        evidence_ids = []
        ds_details = []

        for ds in daemonsets:
            try:
                raw = ds.raw_data or {}
                metadata = raw.get("metadata", {}) or {}
                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")
                status = raw.get("status", {}) or {}

                desired = status.get("desiredNumberScheduled", 0) or 0
                ready = status.get("numberReady", 0) or 0
                unavail = status.get("numberUnavailable", 0) or 0
                misscheduled = status.get("numberMisscheduled", 0) or 0

                if desired == 0:
                    continue

                if ready < desired or unavail > 0 or misscheduled > 0:
                    unavailable.append(
                        f"{namespace}/{name} "
                        f"(desired={desired}, ready={ready}, "
                        f"unavailable={unavail}, misscheduled={misscheduled})"
                    )
                    evidence_ids.append(ds.id)
                    ds_details.append({
                        "name": name,
                        "namespace": namespace,
                        "desired": desired,
                        "ready": ready,
                        "unavailable": unavail,
                    })
            except Exception:
                continue

        if not unavailable:
            return []

        objects_str = ", ".join(unavailable[:10])
        summary = f"{len(unavailable)} DaemonSet(s) not fully scheduled: {objects_str}"
        first = ds_details[0]
        remediation = {
            "what_happened": (
                f"DaemonSet {first['namespace']}/{first['name']} has {first['unavailable']} "
                f"unavailable pod(s). Desired: {first['desired']}, Ready: {first['ready']}."
            ),
            "why_it_matters": (
                "Insufficient replicas mean reduced capacity and potential service "
                "degradation or outage."
            ),
            "how_to_fix": (
                "Check the DaemonSet's pod events and logs to find why pods "
                "are not becoming ready."
            ),
            "cli_commands": [
                f"kubectl rollout status daemonset/{first['name']} -n {first['namespace']}",
                f"kubectl describe daemonset {first['name']} -n {first['namespace']}",
                f"kubectl get pods -n {first['namespace']} -l app={first['name']}",
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
