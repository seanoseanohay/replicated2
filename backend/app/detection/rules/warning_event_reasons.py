import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

DANGEROUS_REASONS = [
    "FailedScheduling",
    "FailedMount",
    "Evicted",
    "BackOff",
    "FailedCreate",
    "FailedAttachVolume",
]
HIGH_SEVERITY_REASONS = {"FailedScheduling", "Evicted"}
REASON_THRESHOLD = 3


class WarningEventReasonsRule(BaseRule):
    rule_id = "warning_event_reasons"
    title = "Repeated Warning Event Reasons"
    severity = "medium"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        findings = []
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Event",
            )
        )
        events = result.scalars().all()

        # reason -> list of (evidence_id, involved_object_name)
        reason_data: dict[str, list] = defaultdict(list)

        for event in events:
            try:
                raw = event.raw_data or {}
                if raw.get("type") != "Warning":
                    continue
                reason = raw.get("reason", "")
                if reason not in DANGEROUS_REASONS:
                    continue
                involved = raw.get("involvedObject", {}) or {}
                obj_kind = involved.get("kind", "object")
                obj_name = involved.get("name", "unknown")
                obj_ref = f"{obj_kind.lower()}/{obj_name}"
                reason_data[reason].append((event.id, obj_ref))
            except Exception:
                continue

        for reason, entries in reason_data.items():
            if len(entries) < REASON_THRESHOLD:
                continue
            count = len(entries)
            unique_objects = list(dict.fromkeys(obj for _, obj in entries))[:5]
            objects_str = ", ".join(unique_objects)
            summary = (
                f"{count} {reason} warning events detected. "
                f"Affected objects: {objects_str}"
            )
            evidence_ids = [eid for eid, _ in entries]
            severity = "high" if reason in HIGH_SEVERITY_REASONS else "medium"
            finding = Finding(
                bundle_id=bundle_id,
                rule_id=self.rule_id,
                title=f"Repeated {reason} Events",
                severity=severity,
                summary=summary,
                evidence_ids=[str(e) for e in evidence_ids],
                status="open",
            )
            findings.append(finding)

        return findings
