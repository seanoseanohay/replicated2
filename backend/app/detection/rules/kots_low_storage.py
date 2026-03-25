import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.detection.kots_utils import make_kots_diff
from app.models.evidence import Evidence
from app.models.finding import Finding

_STORAGE_KEYS = ("storage", "disk", "volume_size", "pvc_size")
_UNIT_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:Gi|Mi|GB|MB|G|M)?\s*$", re.IGNORECASE)


def _parse_numeric(value: str) -> float | None:
    """Extract numeric portion from a storage value string."""
    m = _UNIT_PATTERN.match(str(value))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


class KotsLowStorageRule(BaseRule):
    rule_id = "kots_low_storage"
    title = "KOTS Config: Storage Size Below Recommended Minimum"
    severity = "medium"

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
                    if not any(tok in key_lower for tok in _STORAGE_KEYS):
                        continue

                    value = str(entry.get("value", ""))
                    numeric = _parse_numeric(value)
                    if numeric is None or numeric >= 10:
                        continue

                    kots_diff = make_kots_diff(
                        configvalues_raw, key, value, "10Gi"
                    ) if configvalues_raw else ""

                    remediation = {
                        "what_happened": (
                            f"Config key '{key}' sets storage to '{value}', which is below "
                            "the recommended minimum of 10Gi. Low storage can cause data loss "
                            "if the volume fills up."
                        ),
                        "why_it_matters": (
                            "When storage fills up, databases crash, logs stop writing, and "
                            "the application becomes unavailable."
                        ),
                        "how_to_fix": (
                            "Increase storage to at least 10Gi. Note: PVC resizing requires "
                            "the StorageClass to support volume expansion."
                        ),
                        "cli_commands": [
                            f"kubectl kots set config <app-slug> --namespace <namespace> "
                            f"--key {key} --value '10Gi' --deploy",
                            "kubectl get pvc --all-namespaces",
                        ],
                        "kots_key": key,
                        "kots_recommended_value": "10Gi",
                        "kots_diff": kots_diff,
                    }

                    summary = (
                        f"Config key '{key}' sets storage to '{value}', which is below "
                        "the recommended minimum of 10Gi."
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
