import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import BaseRule
from app.models.evidence import Evidence
from app.models.finding import Finding

WARNING_THRESHOLD = 10


class WarningEventsRule(BaseRule):
    rule_id = "warning_events"
    title = "Excessive Kubernetes Warning Events"
    severity = "low"

    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        result = session.execute(
            select(Evidence).where(
                Evidence.bundle_id == bundle_id,
                Evidence.kind == "Event",
            )
        )
        events = result.scalars().all()

        warning_events = []
        warning_ids = []
        reason_counter: Counter = Counter()
        namespaces: list[str] = []

        for event in events:
            try:
                raw = event.raw_data or {}
                if raw.get("type") == "Warning":
                    warning_events.append(event)
                    warning_ids.append(event.id)
                    reason = raw.get("reason", "Unknown")
                    reason_counter[reason] += 1
                    ns = event.namespace or raw.get("metadata", {}).get("namespace", "default")
                    namespaces.append(ns)
            except Exception:
                continue

        if len(warning_events) <= WARNING_THRESHOLD:
            return []

        top_reasons = reason_counter.most_common(5)
        reasons_str = ", ".join(f"{r} ({c})" for r, c in top_reasons)
        summary = (
            f"{len(warning_events)} warning events found. Top reasons: {reasons_str}"
        )
        namespace = namespaces[0] if namespaces else "default"
        top_reason_names = ", ".join(r for r, _ in top_reasons)
        remediation = {
            "what_happened": (
                f"{len(warning_events)} Kubernetes Warning events detected in namespace "
                f"{namespace}. Top reasons: {top_reason_names}."
            ),
            "why_it_matters": (
                "Warning events indicate cluster components are reporting problems that may "
                "lead to or already be causing outages."
            ),
            "how_to_fix": (
                "Review the warning events and address the underlying causes."
            ),
            "cli_commands": [
                f"kubectl get events -n {namespace} --field-selector type=Warning --sort-by=.lastTimestamp",
                "kubectl get events --all-namespaces --field-selector type=Warning",
            ],
        }
        return [
            self._make_finding(
                bundle_id,
                summary,
                evidence_ids=warning_ids,
                remediation=remediation,
            )
        ]
