import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.detection.kots_utils import make_kots_diff
from app.models.evidence import Evidence
from app.models.finding import Finding

_DISABLED_VALUES = {"false", "disabled", "0"}


class KotsTlsDisabledRule(BaseRule):
    rule_id = "kots_tls_disabled"
    title = "KOTS Config: TLS/HTTPS Disabled"
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
                    if not any(tok in key_lower for tok in ("tls", "https", "ssl")):
                        continue

                    value = str(entry.get("value", "")).lower()
                    if value not in _DISABLED_VALUES:
                        continue

                    kots_diff = make_kots_diff(
                        configvalues_raw, key, str(entry.get("value", "")), "true"
                    ) if configvalues_raw else ""

                    remediation = {
                        "what_happened": (
                            f"TLS/HTTPS is disabled via KOTS config key '{key}'. Traffic "
                            "between clients and the application is unencrypted."
                        ),
                        "why_it_matters": (
                            "Unencrypted traffic exposes credentials and data to interception. "
                            "Most compliance frameworks require TLS in production."
                        ),
                        "how_to_fix": (
                            "Enable TLS by setting the key to 'true' and ensuring a valid "
                            "certificate is configured."
                        ),
                        "cli_commands": [
                            f"kubectl kots set config <app-slug> --namespace <namespace> "
                            f"--key {key} --value 'true' --deploy"
                        ],
                        "kots_key": key,
                        "kots_recommended_value": "true",
                        "kots_diff": kots_diff,
                    }

                    summary = (
                        f"TLS/HTTPS is disabled via KOTS config key '{key}'. "
                        "Traffic between clients and the application is unencrypted."
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
