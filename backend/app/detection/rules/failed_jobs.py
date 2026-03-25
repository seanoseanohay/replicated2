import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class FailedJobsRule(BaseRule):
    rule_id = "failed_jobs"
    title = "Failed Kubernetes Jobs Detected"
    severity = "high"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Job",
            )
        )
        jobs = result.scalars().all()

        failed = []
        evidence_ids = []
        failed_details = []

        for job in jobs:
            try:
                raw = job.raw_data or {}
                metadata = raw.get("metadata", {}) or {}
                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")
                status = raw.get("status", {}) or {}

                failed_count = status.get("failed", 0) or 0
                conditions = status.get("conditions", []) or []

                # A job is "failed" if it has a Failed condition or non-zero failed pods
                is_failed = failed_count > 0 or any(
                    c.get("type") == "Failed" and c.get("status") == "True"
                    for c in conditions
                )

                # Also flag jobs with no active/succeeded pods (stuck / never ran)
                active = status.get("active", 0) or 0
                succeeded = status.get("succeeded", 0) or 0
                spec = raw.get("spec", {}) or {}
                completions = spec.get("completions", 1) or 1
                is_stuck = active == 0 and succeeded < completions and not is_failed

                if is_failed:
                    failed.append(f"{namespace}/{name} (failed={failed_count})")
                    evidence_ids.append(job.id)
                    failed_details.append({"namespace": namespace, "name": name})
                elif is_stuck:
                    failed.append(
                        f"{namespace}/{name} (stuck: 0 active, {succeeded}/{completions} succeeded)"
                    )
                    evidence_ids.append(job.id)
                    failed_details.append({"namespace": namespace, "name": name})
            except Exception:
                continue

        if not failed:
            return []

        objects_str = ", ".join(failed[:10])
        summary = f"{len(failed)} job(s) failed or are stuck: {objects_str}"
        first = failed_details[0] if failed_details else {"namespace": "default", "name": "unknown"}
        remediation = {
            "what_happened": (
                f"Job {first['namespace']}/{first['name']} has failed or is stuck. "
                f"{len(failed)} job(s) total are affected."
            ),
            "why_it_matters": (
                "Failed jobs may indicate data processing errors, migration failures, or "
                "other batch workload issues that require manual intervention."
            ),
            "how_to_fix": (
                "Check the job logs to understand the failure reason. "
                "You may need to delete and recreate the job after fixing the underlying issue."
            ),
            "cli_commands": [
                f"kubectl describe job {first['name']} -n {first['namespace']}",
                f"kubectl logs -l job-name={first['name']} -n {first['namespace']}",
                f"kubectl get pods -n {first['namespace']} --selector=job-name={first['name']}",
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
