import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class PodCrashLoopRule(BaseRule):
    rule_id = "pod_crashloop"
    title = "Pod CrashLoopBackOff Detected"
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
                affected_containers = []
                for cs in container_statuses:
                    restart_count = cs.get("restartCount", 0) or 0
                    last_reason = (
                        cs.get("lastState", {}).get("terminated", {}).get("reason", "")
                    )
                    if restart_count > 5 or last_reason == "CrashLoopBackOff":
                        affected_containers.append(
                            {
                                "name": cs.get("name", "unknown"),
                                "restartCount": restart_count,
                                "reason": last_reason,
                            }
                        )
                if affected_containers:
                    namespace = pod.namespace or "default"
                    pod_name = pod.name
                    details = ", ".join(
                        f"{c['name']} (restarts={c['restartCount']}, reason={c['reason']})"
                        for c in affected_containers
                    )
                    summary = f"Pod {namespace}/{pod_name} has containers in crash loop: {details}"
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[pod.id])
                    )
            except Exception:
                continue

        return findings
