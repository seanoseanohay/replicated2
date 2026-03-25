import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class StatefulSetUnavailableRule(BaseRule):
    rule_id = "statefulset_unavailable"
    title = "StatefulSet Not at Desired Capacity"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "StatefulSet",
            )
        )
        statefulsets = result.scalars().all()

        for sts in statefulsets:
            try:
                raw = sts.raw_data or {}
                spec_replicas = raw.get("spec", {}).get("replicas", 1)
                if spec_replicas is None:
                    spec_replicas = 1
                spec_replicas = int(spec_replicas)
                # Skip scaled-to-zero StatefulSets
                if spec_replicas == 0:
                    continue
                ready_replicas = raw.get("status", {}).get("readyReplicas", 0)
                if ready_replicas is None:
                    ready_replicas = 0
                ready_replicas = int(ready_replicas)
                if ready_replicas < spec_replicas:
                    namespace = sts.namespace or "default"
                    sts_name = sts.name
                    unavailable = spec_replicas - ready_replicas
                    summary = (
                        f"StatefulSet {namespace}/{sts_name} has "
                        f"{ready_replicas}/{spec_replicas} replicas ready"
                    )
                    remediation = {
                        "what_happened": (
                            f"StatefulSet {namespace}/{sts_name} has {unavailable} unavailable "
                            f"replica(s). Desired: {spec_replicas}, Ready: {ready_replicas}."
                        ),
                        "why_it_matters": (
                            "Insufficient replicas mean reduced capacity and potential service "
                            "degradation or outage."
                        ),
                        "how_to_fix": (
                            "Check the StatefulSet's pod events and logs to find why replicas "
                            "are not becoming ready."
                        ),
                        "cli_commands": [
                            f"kubectl rollout status statefulset/{sts_name} -n {namespace}",
                            f"kubectl describe statefulset {sts_name} -n {namespace}",
                            f"kubectl get pods -n {namespace} -l app={sts_name}",
                        ],
                    }
                    findings.append(
                        self._make_finding(
                            bundle_id,
                            summary,
                            evidence_ids=[sts.id],
                            remediation=remediation,
                        )
                    )
            except Exception:
                continue

        return findings
