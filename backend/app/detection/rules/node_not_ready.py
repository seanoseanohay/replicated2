import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class NodeNotReadyRule(BaseRule):
    rule_id = "node_not_ready"
    title = "Node Not Ready"
    severity = "critical"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Node",
            )
        )
        nodes = result.scalars().all()

        for node in nodes:
            try:
                raw = node.raw_data or {}
                conditions = raw.get("status", {}).get("conditions", []) or []
                is_not_ready = False
                not_ready_time = "unknown"
                for condition in conditions:
                    if (
                        condition.get("type") == "Ready"
                        and condition.get("status") != "True"
                    ):
                        is_not_ready = True
                        not_ready_time = condition.get("lastTransitionTime", "unknown")
                        break
                if is_not_ready:
                    summary = (
                        f"Node {node.name} is not in Ready state. "
                        "This may indicate a hardware, network, or kubelet issue."
                    )
                    remediation = {
                        "what_happened": (
                            f"Node {node.name} has been in NotReady state since {not_ready_time}. "
                            f"Workloads on this node are at risk."
                        ),
                        "why_it_matters": (
                            "Pods on a NotReady node will be evicted after the pod eviction timeout "
                            "(default 5 minutes), causing disruption to any workloads running there."
                        ),
                        "how_to_fix": (
                            "SSH to the node and check kubelet status. If the node is unrecoverable, "
                            "cordon and drain it to safely migrate workloads."
                        ),
                        "cli_commands": [
                            f"kubectl describe node {node.name}",
                            f"kubectl cordon {node.name}",
                            f"kubectl drain {node.name} --ignore-daemonsets --delete-emptydir-data",
                        ],
                    }
                    findings.append(
                        self._make_finding(
                            bundle_id,
                            summary,
                            evidence_ids=[node.id],
                            remediation=remediation,
                        )
                    )
            except Exception:
                continue

        return findings
