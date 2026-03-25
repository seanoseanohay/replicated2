import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class HPAMaxedRule(BaseRule):
    rule_id = "hpa_maxed"
    title = "HorizontalPodAutoscaler at Maximum Replicas"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "HorizontalPodAutoscaler",
            )
        )
        hpas = result.scalars().all()

        for hpa in hpas:
            try:
                raw = hpa.raw_data or {}
                max_replicas = raw.get("spec", {}).get("maxReplicas", 0)
                if max_replicas is None:
                    max_replicas = 0
                max_replicas = int(max_replicas)
                current_replicas = raw.get("status", {}).get("currentReplicas", 0)
                if current_replicas is None:
                    current_replicas = 0
                current_replicas = int(current_replicas)
                if current_replicas > 0 and current_replicas >= max_replicas:
                    namespace = hpa.namespace or "default"
                    hpa_name = hpa.name
                    summary = (
                        f"HPA {namespace}/{hpa_name} is at max replicas "
                        f"({current_replicas}/{max_replicas}) and cannot scale further"
                    )
                    remediation = {
                        "what_happened": (
                            f"HorizontalPodAutoscaler {namespace}/{hpa_name} is at its maximum "
                            f"replica count ({max_replicas}). It cannot scale further."
                        ),
                        "why_it_matters": (
                            "The application is under load it cannot handle. If demand continues "
                            "to grow, response times will degrade."
                        ),
                        "how_to_fix": (
                            "Either increase the HPA maxReplicas limit or investigate why the "
                            "application needs so many replicas (memory leak, CPU inefficiency, "
                            "traffic spike)."
                        ),
                        "cli_commands": [
                            f"kubectl describe hpa {hpa_name} -n {namespace}",
                            f"kubectl top pods -n {namespace}",
                        ],
                    }
                    findings.append(
                        self._make_finding(
                            bundle_id,
                            summary,
                            evidence_ids=[hpa.id],
                            remediation=remediation,
                        )
                    )
            except Exception:
                continue

        return findings
