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
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[node.id])
                    )
            except Exception:
                continue

        return findings
