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
                elif is_stuck:
                    failed.append(f"{namespace}/{name} (stuck: 0 active, {succeeded}/{completions} succeeded)")
                    evidence_ids.append(job.id)
            except Exception:
                continue

        if not failed:
            return []

        objects_str = ", ".join(failed[:10])
        summary = f"{len(failed)} job(s) failed or are stuck: {objects_str}"
        return [self._make_finding(bundle_id, summary, evidence_ids=evidence_ids)]
