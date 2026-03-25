import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

FAILED_REASONS = {"Error", "OOMKilled", "CrashLoopBackOff", "RunContainerError"}


class InitContainerFailedRule(BaseRule):
    rule_id = "init_container_failed"
    title = "Init Container Failures Detected"
    severity = "high"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        failed = []
        evidence_ids = []
        failed_details = []

        for pod in pods:
            try:
                raw = pod.raw_data or {}
                metadata = raw.get("metadata", {}) or {}
                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")

                init_statuses = (raw.get("status", {}) or {}).get(
                    "initContainerStatuses", []
                ) or []

                for cs in init_statuses:
                    waiting_reason = (
                        cs.get("state", {}).get("waiting", {}).get("reason", "") or ""
                    )
                    terminated_reason = (
                        cs.get("lastState", {}).get("terminated", {}).get("reason", "")
                        or cs.get("state", {}).get("terminated", {}).get("reason", "")
                        or ""
                    )
                    restart_count = cs.get("restartCount", 0) or 0
                    container_name = cs.get("name", "unknown")

                    is_failed = (
                        waiting_reason in FAILED_REASONS
                        or terminated_reason in FAILED_REASONS
                        or (restart_count > 0 and not cs.get("ready", False))
                    )

                    if is_failed:
                        reason = waiting_reason or terminated_reason or "unknown"
                        failed.append(
                            f"{namespace}/{name} init:{container_name} "
                            f"(reason={reason}, restarts={restart_count})"
                        )
                        evidence_ids.append(pod.id)
                        failed_details.append({
                            "namespace": namespace,
                            "pod": name,
                            "init_container": container_name,
                        })
                        break  # one finding per pod
            except Exception:
                continue

        if not failed:
            return []

        objects_str = ", ".join(failed[:10])
        summary = f"{len(failed)} pod(s) have failing init containers: {objects_str}"
        first = failed_details[0]
        remediation = {
            "what_happened": (
                f"Init container {first['init_container']} in pod "
                f"{first['namespace']}/{first['pod']} has failed. The main containers will not "
                f"start until all init containers succeed."
            ),
            "why_it_matters": (
                "The entire pod is blocked. No application containers are running."
            ),
            "how_to_fix": (
                "Check the init container logs to find the failure reason."
            ),
            "cli_commands": [
                f"kubectl logs {first['pod']} -n {first['namespace']} -c {first['init_container']}",
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
