import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class OOMKilledRule(BaseRule):
    rule_id = "oom_killed"
    title = "Pod OOMKilled Detected"
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
                oom_containers = []
                for cs in container_statuses:
                    last_reason = (
                        cs.get("lastState", {}).get("terminated", {}).get("reason", "")
                    )
                    if last_reason == "OOMKilled":
                        oom_containers.append(cs.get("name", "unknown"))

                if oom_containers:
                    namespace = pod.namespace or "default"
                    pod_name = pod.name
                    containers_str = ", ".join(oom_containers)
                    summary = f"Pod {namespace}/{pod_name} has OOMKilled containers: {containers_str}"
                    container = oom_containers[0]
                    # Derive deployment name from pod name (strip last two suffix segments)
                    parts = pod_name.rsplit("-", 2)
                    deployment = parts[0] if len(parts) >= 3 else pod_name
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
                        f"      - name: {container}\n"
                        f"        resources:\n"
                        f"          limits:\n"
                        f"            memory: \"512Mi\"\n"
                    )
                    remediation = {
                        "what_happened": (
                            f"Container {container} in pod {namespace}/{pod_name} was killed by "
                            f"the Linux OOM killer because it exceeded its memory limit."
                        ),
                        "why_it_matters": (
                            "OOM kills cause abrupt process termination which can corrupt "
                            "in-flight writes and drop active connections."
                        ),
                        "how_to_fix": (
                            "Increase the memory limit for this container. Monitor actual usage "
                            "with kubectl top to set an appropriate value."
                        ),
                        "patch_yaml": patch_yaml,
                        "patch_filename": f"fix-oom-{pod_name}-memory.yaml",
                        "cli_commands": [
                            f"kubectl top pod {pod_name} -n {namespace}",
                            (
                                f"kubectl patch deployment {deployment} -n {namespace} "
                                f"--type=merge -p '{{\"spec\":{{\"template\":{{\"spec\":"
                                f"{{\"containers\":[{{\"name\":\"{container}\","
                                f"\"resources\":{{\"limits\":{{\"memory\":\"512Mi\"}}}}}}]}}}}}}}}'"
                            ),
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
