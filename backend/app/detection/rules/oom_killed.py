import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class OOMKilledRule(BaseRule):
    rule_id = "oom_killed"
    title = "Pod OOMKilled Detected"
    severity = "high"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        for pod in pods:
            try:
                raw = pod.raw_data or {}
                container_statuses = (
                    raw.get("status", {}).get("containerStatuses", []) or []
                )
                oom_containers = []
                for cs in container_statuses:
                    last_reason = (
                        cs.get("lastState", {})
                        .get("terminated", {})
                        .get("reason", "")
                    )
                    if last_reason == "OOMKilled":
                        oom_containers.append(cs.get("name", "unknown"))

                if oom_containers:
                    namespace = pod.namespace or "default"
                    pod_name = pod.name
                    containers_str = ", ".join(oom_containers)
                    summary = (
                        f"Pod {namespace}/{pod_name} has OOMKilled containers: {containers_str}"
                    )
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[pod.id])
                    )
            except Exception:
                continue

        return findings
