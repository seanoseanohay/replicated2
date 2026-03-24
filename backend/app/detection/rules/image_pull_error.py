import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

IMAGE_PULL_REASONS = {"ImagePullBackOff", "ErrImagePull"}


class ImagePullErrorRule(BaseRule):
    rule_id = "image_pull_error"
    title = "Image Pull Error Detected"
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
                error_containers = []
                for cs in container_statuses:
                    waiting_reason = (
                        cs.get("state", {}).get("waiting", {}).get("reason", "")
                    )
                    if waiting_reason in IMAGE_PULL_REASONS:
                        image = cs.get("image", "unknown")
                        error_containers.append(
                            f"{cs.get('name', 'unknown')} (image={image}, reason={waiting_reason})"
                        )

                if error_containers:
                    namespace = pod.namespace or "default"
                    containers_str = ", ".join(error_containers)
                    summary = f"Pod {namespace}/{pod.name} cannot pull container images: {containers_str}"
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[pod.id])
                    )
            except Exception:
                continue

        return findings
