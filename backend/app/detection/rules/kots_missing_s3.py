import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.detection.kots_utils import make_kots_diff
from app.models.evidence import Evidence
from app.models.finding import Finding

_S3_KEYS = ("s3_bucket", "object_storage_bucket", "backup_bucket")


class KotsMissingS3Rule(BaseRule):
    rule_id = "kots_missing_s3"
    title = "KOTS Config: S3/Object Storage Not Configured"
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
                    if not any(tok in key_lower for tok in _S3_KEYS):
                        continue

                    value = entry.get("value")
                    if value not in (None, "", "null"):
                        continue

                    kots_diff = make_kots_diff(
                        configvalues_raw, key, str(value or ""), "my-bucket-name"
                    ) if configvalues_raw else ""

                    remediation = {
                        "what_happened": (
                            f"Config key '{key}' for S3/object storage is not configured. "
                            "Features that depend on object storage (backups, file uploads, "
                            "artifacts) will fail."
                        ),
                        "why_it_matters": (
                            "Missing object storage configuration typically causes silent "
                            "failures — uploads appear to succeed but data is lost."
                        ),
                        "how_to_fix": (
                            "Configure an S3-compatible bucket and set the bucket name, "
                            "endpoint, access key, and secret key in the KOTS admin console."
                        ),
                        "cli_commands": [
                            f"kubectl kots set config <app-slug> --namespace <namespace> "
                            f"--key {key} --value 'my-bucket-name' --deploy"
                        ],
                        "kots_key": key,
                        "kots_diff": kots_diff,
                    }

                    summary = (
                        f"Config key '{key}' for S3/object storage is not configured. "
                        "Object-storage-dependent features will fail."
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
