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
                for condition in conditions:
                    if condition.get("type") == "Ready" and condition.get("status") != "True":
                        is_not_ready = True
                        break
                if is_not_ready:
                    summary = (
                        f"Node {node.name} is not in Ready state. "
                        "This may indicate a hardware, network, or kubelet issue."
                    )
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[node.id])
                    )
            except Exception:
                continue

        return findings
