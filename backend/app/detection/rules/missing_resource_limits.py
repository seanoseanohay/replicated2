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
        missing_details = []

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

                # Skip crashing pods — missing limits are noise when the pod is already broken
                container_statuses = (raw.get("status", {}) or {}).get("containerStatuses", []) or []
                is_crashing = any(
                    cs.get("state", {}).get("waiting", {}).get("reason") == "CrashLoopBackOff"
                    or cs.get("lastState", {}).get("terminated", {}).get("reason") == "CrashLoopBackOff"
                    or (
                        cs.get("state", {}).get("terminated", {}).get("exitCode") not in (0, None)
                        and (cs.get("restartCount", 0) or 0) >= 1
                    )
                    or (
                        cs.get("lastState", {}).get("terminated", {}).get("exitCode") not in (0, None)
                        and (cs.get("restartCount", 0) or 0) >= 1
                    )
                    for cs in container_statuses
                )
                if is_crashing:
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
                        missing_details.append({
                            "namespace": namespace,
                            "pod": name,
                            "container": container_name,
                        })
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
        first = missing_details[0]
        namespace = first["namespace"]
        # Derive deployment name from pod name
        parts = first["pod"].rsplit("-", 2)
        deployment = parts[0] if len(parts) >= 3 else first["pod"]
        patch_yaml = (
            f"apiVersion: apps/v1\n"
            f"kind: Deployment\n"
            f"metadata:\n"
            f"  name: {deployment}\n"
            f"  namespace: {namespace}\n"
            f"spec:\n"
            f"  template:\n"
            f"    spec:\n"
            f"      containers:\n"
            f"      - name: {first['container']}\n"
            f"        resources:\n"
            f"          requests:\n"
            f"            memory: \"256Mi\"\n"
            f"            cpu: \"100m\"\n"
            f"          limits:\n"
            f"            memory: \"512Mi\"\n"
            f"            cpu: \"500m\"\n"
        )
        remediation = {
            "what_happened": (
                f"{len(missing)} container(s) across {namespace} have no CPU or memory "
                f"resource limits set."
            ),
            "why_it_matters": (
                "Containers without limits can consume unbounded resources, causing node "
                "pressure and OOM kills affecting other workloads."
            ),
            "how_to_fix": (
                "Add resource requests and limits to each container. Start with conservative "
                "values and tune based on observed usage."
            ),
            "patch_yaml": patch_yaml,
            "patch_filename": f"fix-resource-limits-{namespace}.yaml",
            "cli_commands": [
                f"kubectl top pods -n {namespace} --containers",
                (
                    f"kubectl patch deployment {deployment} -n {namespace} "
                    f"--type=merge -p '{{\"spec\":{{\"template\":{{\"spec\":{{\"containers\":"
                    f"[{{\"name\":\"{first['container']}\",\"resources\":{{\"requests\":"
                    f"{{\"memory\":\"256Mi\",\"cpu\":\"100m\"}},\"limits\":"
                    f"{{\"memory\":\"512Mi\",\"cpu\":\"500m\"}}}}}}]}}}}}}}}'"
                ),
            ],
        }
        return [
            self._make_finding(
                bundle_id,
                summary,
                evidence_ids=list(dict.fromkeys(evidence_ids)),
                remediation=remediation,
            )
        ]
