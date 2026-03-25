import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding


class PVCPendingRule(BaseRule):
    rule_id = "pvc_pending"
    title = "PersistentVolumeClaims Stuck in Pending State"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "PersistentVolumeClaim",
            )
        )
        pvcs = result.scalars().all()

        pending_pvcs = []
        pending_ids = []
        pvc_details = []
        for pvc in pvcs:
            try:
                raw = pvc.raw_data or {}
                phase = raw.get("status", {}).get("phase", "")
                if phase == "Pending":
                    namespace = pvc.namespace or "default"
                    pending_pvcs.append(f"{namespace}/{pvc.name}")
                    pending_ids.append(pvc.id)
                    pvc_details.append({"namespace": namespace, "name": pvc.name})
            except Exception:
                continue

        if not pending_pvcs:
            return []

        pvcs_str = ", ".join(pending_pvcs)
        summary = (
            f"{len(pending_pvcs)} PersistentVolumeClaim(s) stuck in Pending state: {pvcs_str}. "
            "Check that a StorageClass is available and has sufficient capacity."
        )
        first = pvc_details[0]
        remediation = {
            "what_happened": (
                f"PersistentVolumeClaim {first['namespace']}/{first['name']} has been in "
                f"Pending state. No PersistentVolume has been bound to it."
            ),
            "why_it_matters": (
                "Any pod that mounts this PVC will also be stuck in Pending, "
                "blocking application startup."
            ),
            "how_to_fix": (
                "Check whether a StorageClass is defined and has a provisioner that can satisfy "
                "the claim. Verify the requested storage size is available."
            ),
            "cli_commands": [
                f"kubectl describe pvc {first['name']} -n {first['namespace']}",
                "kubectl get storageclass",
                "kubectl get pv",
            ],
        }
        return [
            self._make_finding(
                bundle_id,
                summary,
                evidence_ids=pending_ids,
                remediation=remediation,
            )
        ]
