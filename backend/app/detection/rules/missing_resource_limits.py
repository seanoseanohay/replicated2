import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

# Kubernetes core namespaces — skip entirely, not customer workloads
_KUBE_CORE_RE = re.compile(r"^kube-")

# Infrastructure addon namespaces — flag at info, not medium
# Matches namespace names containing common addon/infrastructure keywords
_INFRA_NS_RE = re.compile(
    r"storage|operator|controller|manager|monitoring|logging|"
    r"cert-|ingress|istio|linkerd|calico|flannel|weave|cilium|"
    r"metallb|external-dns|velero|vault|consul|traefik|-system$",
    re.IGNORECASE,
)


def _is_kube_core(ns: str) -> bool:
    return bool(_KUBE_CORE_RE.match(ns))


def _is_infra(ns: str) -> bool:
    return bool(_INFRA_NS_RE.search(ns))


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

        # user-space pods missing limits (medium severity)
        missing: list[str] = []
        evidence_ids: list = []
        missing_details: list[dict] = []

        # infrastructure addon pods missing limits (info severity)
        infra_missing: list[str] = []
        infra_evidence_ids: list = []
        infra_missing_details: list[dict] = []

        for pod in pods:
            try:
                raw = pod.raw_data or {}
                metadata = raw.get("metadata", {}) or {}
                name = metadata.get("name", "unknown")
                namespace = metadata.get("namespace", "default")

                if _is_kube_core(namespace):
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
                        entry = (
                            f"{namespace}/{name}/{container_name} "
                            f"(missing: {', '.join(missing_parts)})"
                        )
                        detail = {
                            "namespace": namespace,
                            "pod": name,
                            "container": container_name,
                        }
                        if _is_infra(namespace):
                            infra_missing.append(entry)
                            infra_evidence_ids.append(pod.id)
                            infra_missing_details.append(detail)
                        else:
                            missing.append(entry)
                            evidence_ids.append(pod.id)
                            missing_details.append(detail)
                        break  # one entry per pod is enough
            except Exception:
                continue

        findings = []

        def _build_finding(details, eids, entries, severity_override=None):
            if not details:
                return None
            first = details[0]
            namespace = first["namespace"]
            parts = first["pod"].rsplit("-", 2)
            deployment = parts[0] if len(parts) >= 3 else first["pod"]
            objects_str = ", ".join(entries[:10])
            extra = f" (+{len(entries) - 10} more)" if len(entries) > 10 else ""
            summary = (
                f"{len(entries)} container(s) have no resource limits set: "
                f"{objects_str}{extra}. This can lead to node starvation and OOM kills."
            )
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
                    f"{len(entries)} container(s) across {namespace} have no CPU or memory "
                    f"resource limits set."
                    + (" (Infrastructure namespace — lower priority.)" if severity_override == "info" else "")
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
            f = self._make_finding(
                bundle_id,
                summary,
                evidence_ids=list(dict.fromkeys(eids)),
                remediation=remediation,
            )
            if severity_override:
                f.severity = severity_override
            return f

        user_finding = _build_finding(missing_details, evidence_ids, missing)
        if user_finding:
            findings.append(user_finding)

        infra_finding = _build_finding(
            infra_missing_details, infra_evidence_ids, infra_missing,
            severity_override="info",
        )
        if infra_finding:
            findings.append(infra_finding)

        return findings
