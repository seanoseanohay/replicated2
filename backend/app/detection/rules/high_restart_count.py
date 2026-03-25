import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

# Flag containers that have restarted this many times even if not in CrashLoopBackOff
HIGH_RESTART_THRESHOLD = 3


class HighRestartCountRule(BaseRule):
    rule_id = "high_restart_count"
    title = "Containers with High Restart Count"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        flagged = []
        evidence_ids = []
        flagged_details = []

        for pod in pods:
            try:
                raw = pod.raw_data or {}
                metadata = raw.get("metadata", {}) or {}
                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")

                container_statuses = (raw.get("status", {}) or {}).get(
                    "containerStatuses", []
                ) or []

                for cs in container_statuses:
                    restart_count = cs.get("restartCount", 0) or 0
                    container_name = cs.get("name", "unknown")

                    # Skip if already in CrashLoopBackOff (caught by pod_crashloop rule)
                    waiting_reason = (
                        cs.get("state", {}).get("waiting", {}).get("reason", "") or ""
                    )
                    if waiting_reason == "CrashLoopBackOff":
                        continue

                    is_not_ready = not cs.get("ready", True)
                    if restart_count >= HIGH_RESTART_THRESHOLD or (
                        restart_count > 0 and is_not_ready
                    ):
                        flagged.append(
                            f"{namespace}/{name}/{container_name} "
                            f"(restarts={restart_count}, ready={cs.get('ready', False)})"
                        )
                        evidence_ids.append(pod.id)
                        flagged_details.append({
                            "namespace": namespace,
                            "pod": name,
                            "container": container_name,
                            "count": restart_count,
                        })
                        break  # one finding per pod
            except Exception:
                continue

        if not flagged:
            return []

        objects_str = ", ".join(flagged[:10])
        summary = (
            f"{len(flagged)} container(s) have restarted {HIGH_RESTART_THRESHOLD}+ "
            f"times without entering CrashLoopBackOff: {objects_str}"
        )
        first = flagged_details[0]
        remediation = {
            "what_happened": (
                f"Container {first['container']} in pod {first['namespace']}/{first['pod']} "
                f"has restarted {first['count']} times."
            ),
            "why_it_matters": (
                "Frequent restarts indicate an unstable application that may be losing state "
                "and dropping connections on each restart."
            ),
            "how_to_fix": (
                "Review the container logs to identify the crash cause. Check liveness probe "
                "configuration — overly aggressive probes can cause unnecessary restarts."
            ),
            "cli_commands": [
                f"kubectl logs {first['pod']} -n {first['namespace']} -c {first['container']} --previous",
                f"kubectl describe pod {first['pod']} -n {first['namespace']}",
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
