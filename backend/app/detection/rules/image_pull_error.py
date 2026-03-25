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
                            {
                                "name": cs.get("name", "unknown"),
                                "image": image,
                                "reason": waiting_reason,
                                "message": cs.get("state", {}).get("waiting", {}).get("message", waiting_reason),
                            }
                        )

                if error_containers:
                    namespace = pod.namespace or "default"
                    containers_str = ", ".join(
                        f"{c['name']} (image={c['image']}, reason={c['reason']})"
                        for c in error_containers
                    )
                    summary = f"Pod {namespace}/{pod.name} cannot pull container images: {containers_str}"
                    first = error_containers[0]
                    remediation = {
                        "what_happened": (
                            f"Pod {namespace}/{pod.name} cannot pull image {first['image']}. "
                            f"The error is: {first['reason']}."
                        ),
                        "why_it_matters": (
                            "The pod cannot start until the image is accessible. "
                            "All replicas using this image are affected."
                        ),
                        "how_to_fix": (
                            "Verify the image name and tag are correct, that the registry is "
                            "reachable from the cluster, and that an imagePullSecret is configured "
                            "if the registry requires authentication."
                        ),
                        "cli_commands": [
                            f"kubectl describe pod {pod.name} -n {namespace}",
                            f"kubectl get secrets -n {namespace} | grep docker",
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
