import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.detection.kots_utils import make_kots_diff
from app.models.evidence import Evidence
from app.models.finding import Finding


class KotsDebugEnabledRule(BaseRule):
    rule_id = "kots_debug_enabled"
    title = "KOTS Config: Debug Mode Enabled in Production"
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
                    if "debug" not in key_lower and "log_level" not in key_lower:
                        continue

                    value = str(entry.get("value", "")).lower()
                    if value not in ("debug", "true"):
                        continue

                    kots_diff = make_kots_diff(
                        configvalues_raw, key, str(entry.get("value", "")), "false"
                    ) if configvalues_raw else ""

                    remediation = {
                        "what_happened": (
                            f"Config key '{key}' has debug mode enabled. Debug logging "
                            "significantly increases log volume, disk usage, and can expose "
                            "sensitive data in logs."
                        ),
                        "why_it_matters": (
                            "Debug mode in production degrades performance, fills disk faster, "
                            "and risks exposing sensitive information in log output."
                        ),
                        "how_to_fix": (
                            "Disable debug mode by setting the key to 'false' or changing "
                            "log_level to 'info'."
                        ),
                        "cli_commands": [
                            f"kubectl kots set config <app-slug> --namespace <namespace> "
                            f"--key {key} --value 'false' --deploy"
                        ],
                        "kots_key": key,
                        "kots_recommended_value": "false",
                        "kots_diff": kots_diff,
                    }

                    summary = (
                        f"Config key '{key}' has debug mode enabled. Debug logging in "
                        "production increases log volume and can expose sensitive data."
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
