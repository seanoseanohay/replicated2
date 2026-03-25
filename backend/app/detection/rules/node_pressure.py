import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

PRESSURE_CONDITIONS = {"DiskPressure", "MemoryPressure", "PIDPressure"}


class NodePressureRule(BaseRule):
    rule_id = "node_pressure"
    title = "Node Pressure Conditions Detected"
    severity = "medium"

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
                active_pressures = []
                for condition in conditions:
                    ctype = condition.get("type", "")
                    cstatus = condition.get("status", "False")
                    if ctype in PRESSURE_CONDITIONS and cstatus == "True":
                        active_pressures.append(ctype)
                if active_pressures:
                    pressures_str = ", ".join(active_pressures)
                    summary = f"Node {node.name} has active conditions: {pressures_str}"
                    condition_label = active_pressures[0]
                    remediation = {
                        "what_happened": (
                            f"Node {node.name} is reporting {condition_label} pressure. "
                            f"The kubelet is under resource stress."
                        ),
                        "why_it_matters": (
                            "Under pressure conditions the kubelet will evict pods to reclaim "
                            "resources, causing unexpected pod termination."
                        ),
                        "how_to_fix": (
                            "Check which pods are consuming the most resources on this node "
                            "and consider redistributing workloads."
                        ),
                        "cli_commands": [
                            f"kubectl describe node {node.name}",
                            "kubectl top pods --all-namespaces --sort-by=memory | head -20",
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
