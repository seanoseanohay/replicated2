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
                    dep_name = deployment.name
                    unavailable = spec_replicas - available_replicas
                    summary = (
                        f"Deployment {namespace}/{dep_name} has "
                        f"{available_replicas}/{spec_replicas} replicas available"
                    )
                    remediation = {
                        "what_happened": (
                            f"Deployment {namespace}/{dep_name} has {unavailable} unavailable "
                            f"replica(s). Desired: {spec_replicas}, Ready: {available_replicas}."
                        ),
                        "why_it_matters": (
                            "Insufficient replicas mean reduced capacity and potential service "
                            "degradation or outage."
                        ),
                        "how_to_fix": (
                            "Check the deployment's pod events and logs to find why replicas "
                            "are not becoming ready."
                        ),
                        "cli_commands": [
                            f"kubectl rollout status deployment/{dep_name} -n {namespace}",
                            f"kubectl describe deployment {dep_name} -n {namespace}",
                            f"kubectl get pods -n {namespace} -l app={dep_name}",
                        ],
                    }
                    findings.append(
                        self._make_finding(
                            bundle_id,
                            summary,
                            evidence_ids=[deployment.id],
                            remediation=remediation,
                        )
                    )
            except Exception:
                continue

        return findings
