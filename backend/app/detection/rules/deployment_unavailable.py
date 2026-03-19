import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class DeploymentUnavailableRule(BaseRule):
    rule_id = "deployment_unavailable"
    title = "Deployment Not at Desired Capacity"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Deployment",
            )
        )
        deployments = result.scalars().all()

        for deployment in deployments:
            try:
                raw = deployment.raw_data or {}
                spec_replicas = raw.get("spec", {}).get("replicas", 1)
                if spec_replicas is None:
                    spec_replicas = 1
                spec_replicas = int(spec_replicas)
                # Skip scaled-to-zero deployments
                if spec_replicas == 0:
                    continue
                available_replicas = raw.get("status", {}).get("availableReplicas", 0)
                if available_replicas is None:
                    available_replicas = 0
                available_replicas = int(available_replicas)
                if available_replicas < spec_replicas:
                    namespace = deployment.namespace or "default"
                    summary = (
                        f"Deployment {namespace}/{deployment.name} has "
                        f"{available_replicas}/{spec_replicas} replicas available"
                    )
                    findings.append(
                        self._make_finding(bundle_id, summary, evidence_ids=[deployment.id])
                    )
            except Exception:
                continue

        return findings
