import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.detection.kots_utils import make_kots_diff
from app.models.evidence import Evidence
from app.models.finding import Finding


class KotsLowReplicasRule(BaseRule):
    rule_id = "kots_low_replicas"
    title = "KOTS Config: Replica Count Set to 1 (No High Availability)"
    severity = "high"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "KotsConfigValues",
            )
        )
        evidence_list = result.scalars().all()

        for ev in evidence_list:
            try:
                raw = ev.raw_data or {}
                values = raw.get("values") or {}
                configvalues_raw = raw.get("_configvalues_raw") or {}

                for key, entry in values.items():
                    if not isinstance(entry, dict):
                        continue
                    key_lower = key.lower()
                    if "replicas" not in key_lower and "replica_count" not in key_lower:
                        continue

                    value = entry.get("value", "")
                    if str(value) not in ("1", 1):
                        continue

                    kots_diff = make_kots_diff(
                        configvalues_raw, key, str(value), "2"
                    ) if configvalues_raw else ""

                    remediation = {
                        "what_happened": (
                            f"The KOTS configuration key '{key}' is set to 1 replica. "
                            "With a single replica, any pod failure, node drain, or rolling "
                            "update causes a brief outage."
                        ),
                        "why_it_matters": (
                            "Production workloads should run at least 2 replicas for high "
                            "availability. A single replica means zero redundancy."
                        ),
                        "how_to_fix": (
                            "Increase the replica count to at least 2 in the KOTS admin "
                            "console or via the CLI."
                        ),
                        "cli_commands": [
                            f"kubectl kots set config <app-slug> -n <namespace> "
                            f"--config-file fix-kots-{key}.yaml --merge --deploy"
                        ],
                        "kots_key": key,
                        "kots_recommended_value": "2",
                        "kots_diff": kots_diff,
                    }

                    summary = (
                        f"Config key '{key}' is set to 1, which means no redundancy. "
                        "A single pod failure will cause downtime."
                    )
                    findings.append(
                        self._make_finding(
                            bundle_id,
                            summary,
                            evidence_ids=[ev.id],
                            remediation=remediation,
                        )
                    )
            except Exception:
                continue

        return findings
