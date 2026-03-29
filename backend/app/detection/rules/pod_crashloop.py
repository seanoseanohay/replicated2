import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class PodCrashLoopRule(BaseRule):
    rule_id = "pod_crashloop"
    title = "Pod Crash Detected"
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
                    waiting_reason = (
                        cs.get("state", {}).get("waiting", {}).get("reason", "")
                    )
                    last_exit_code = (
                        cs.get("lastState", {}).get("terminated", {}).get("exitCode")
                    )
                    current_exit_code = (
                        cs.get("state", {}).get("terminated", {}).get("exitCode")
                    )
                    last_reason = (
                        cs.get("lastState", {}).get("terminated", {}).get("reason", "")
                    )
                    is_crashing = (
                        waiting_reason == "CrashLoopBackOff"
                        or restart_count > 5
                        or (restart_count >= 2 and last_exit_code not in (0, None))
                        or (current_exit_code not in (0, None) and restart_count >= 1)
                    )
                    if is_crashing:
                        reason = waiting_reason or last_reason or "Error"
                        affected_containers.append(
                            {
                                "name": cs.get("name", "unknown"),
                                "restartCount": restart_count,
                                "reason": reason,
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
                    # Use first affected container for remediation
                    container = affected_containers[0]["name"]
                    count = affected_containers[0]["restartCount"]
                    remediation = {
                        "what_happened": (
                            f"Container {container} in pod {namespace}/{pod_name} has restarted "
                            f"{count} times and is in CrashLoopBackOff. Kubernetes keeps restarting "
                            f"it but it keeps failing."
                        ),
                        "why_it_matters": (
                            "The pod is unavailable and consuming cluster resources during its "
                            "restart backoff window."
                        ),
                        "how_to_fix": (
                            "Check the container logs from the previous (crashed) instance to find "
                            "the root cause, then fix the underlying application error."
                        ),
                        "cli_commands": [
                            f"kubectl logs {pod_name} -n {namespace} --previous -c {container}",
                            f"kubectl describe pod {pod_name} -n {namespace}",
                        ],
                    }
                    findings.append(
                        self._make_finding(
                            bundle_id,
                            summary,
                            evidence_ids=[pod.id],
                            remediation=remediation,
                        )
                    )
            except Exception:
                continue

        return findings
