import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class PodPendingRule(BaseRule):
    rule_id = "pod_pending"
    title = "Pods Stuck in Pending State"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        pending_pods = []
        pending_ids = []
        namespaces = []
        for pod in pods:
            try:
                raw = pod.raw_data or {}
                phase = raw.get("status", {}).get("phase", "")
                if phase == "Pending":
                    namespace = pod.namespace or "default"
                    pending_pods.append(f"{namespace}/{pod.name}")
                    pending_ids.append(pod.id)
                    namespaces.append(namespace)
            except Exception:
                continue

        if not pending_pods:
            return []

        pods_str = ", ".join(pending_pods)
        summary = f"{len(pending_pods)} pod(s) stuck in Pending state: {pods_str}"
        namespace = namespaces[0] if namespaces else "default"
        first_pod_parts = pending_pods[0].split("/", 1)
        first_pod = first_pod_parts[1] if len(first_pod_parts) > 1 else pending_pods[0]
        remediation = {
            "what_happened": (
                f"{len(pending_pods)} pod(s) are stuck in Pending state: {pods_str}. "
                f"The Kubernetes scheduler cannot place them on a node."
            ),
            "why_it_matters": (
                "Pending pods are not serving traffic. Common causes are insufficient "
                "CPU/memory on all nodes, missing node selectors, or taints with no tolerations."
            ),
            "how_to_fix": (
                "Describe each pod to see the scheduler's reason. "
                "Check node capacity with kubectl top nodes."
            ),
            "cli_commands": [
                f"kubectl describe pod {first_pod} -n {namespace}",
                "kubectl top nodes",
                "kubectl get nodes -o wide",
            ],
        }
        return [
            self._make_finding(
                bundle_id,
                summary,
                evidence_ids=pending_ids,
                remediation=remediation,
            )
        ]
