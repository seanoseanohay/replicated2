import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

# Namespaces where missing limits are expected / not worth flagging
IGNORED_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease"}


class MissingResourceLimitsRule(BaseRule):
    rule_id = "missing_resource_limits"
    title = "Containers Missing Resource Limits"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Pod",
            )
        )
        pods = result.scalars().all()

        missing = []
        evidence_ids = []

        for pod in pods:
            try:
                raw = pod.raw_data or {}
                metadata = raw.get("metadata", {}) or {}
                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")

                if namespace in IGNORED_NAMESPACES:
                    continue

                # Skip completed / succeeded pods
                phase = (raw.get("status", {}) or {}).get("phase", "")
                if phase in ("Succeeded", "Failed"):
                    continue

                spec = raw.get("spec", {}) or {}
                containers = spec.get("containers", []) or []

                for container in containers:
                    resources = container.get("resources", {}) or {}
                    limits = resources.get("limits", {}) or {}
                    container_name = container.get("name", "unknown")

                    missing_memory = "memory" not in limits
                    missing_cpu = "cpu" not in limits

                    if missing_memory or missing_cpu:
                        missing_parts = []
                        if missing_memory:
                            missing_parts.append("memory")
                        if missing_cpu:
                            missing_parts.append("cpu")
                        missing.append(
                            f"{namespace}/{name}/{container_name} "
                            f"(missing: {', '.join(missing_parts)})"
                        )
                        evidence_ids.append(pod.id)
                        break  # one finding per pod is enough
            except Exception:
                continue

        if not missing:
            return []

        objects_str = ", ".join(missing[:10])
        extra = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
        summary = (
            f"{len(missing)} container(s) have no resource limits set: "
            f"{objects_str}{extra}. This can lead to node starvation and OOM kills."
        )
        return [
            self._make_finding(
                bundle_id, summary, evidence_ids=list(dict.fromkeys(evidence_ids))
            )
        ]
