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
    # probe failures
    "Unhealthy",
    # OOM at the node/container level
    "OOMKilling",
    # storage provisioning
    "FailedBinding",
    "ProvisioningFailed",
    # eviction / lifecycle
    "TaintManagerEviction",
    "ExceededGracePeriod",
    "Killing",
    # networking
    "NetworkNotReady",
    # jobs
    "DeadlineExceeded",
    "BackoffLimitExceeded",
]

# Surface on the very first occurrence — no need to wait for 3
CRITICAL_THRESHOLD_ONE = {
    "Evicted",
    "OOMKilling",
    "TaintManagerEviction",
    "DeadlineExceeded",
    "BackoffLimitExceeded",
    "NetworkNotReady",
}

# Surface after just 2 occurrences — active probe failures, backoff
THRESHOLD_TWO = {
    "Unhealthy",
    "BackOff",
    "Killing",
    "ExceededGracePeriod",
}

HIGH_SEVERITY_REASONS = {
    "FailedScheduling",
    "Evicted",
    "OOMKilling",
    "TaintManagerEviction",
    "DeadlineExceeded",
    "BackoffLimitExceeded",
    "NetworkNotReady",
    "Unhealthy",
}

REASON_THRESHOLD = 3  # default; critical reasons use threshold of 1

# Events from these namespaces are Kubernetes internals — downgrade to info
SYSTEM_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "local-path-storage"}


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

        # reason -> list of (evidence_id, involved_object_name, namespace)
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
                ns = event.namespace or raw.get("metadata", {}).get("namespace", "default")
                reason_data[reason].append((event.id, obj_ref, ns))
            except Exception:
                continue

        for reason, entries in reason_data.items():
            if reason in CRITICAL_THRESHOLD_ONE:
                threshold = 1
            elif reason in THRESHOLD_TWO:
                threshold = 2
            else:
                threshold = REASON_THRESHOLD
            if len(entries) < threshold:
                continue
            count = len(entries)
            unique_objects = list(dict.fromkeys(obj for _, obj, _ in entries))[:5]
            objects_str = ", ".join(unique_objects)
            summary = (
                f"{count} {reason} warning event(s) detected. "
                f"Affected objects: {objects_str}"
            )
            evidence_ids = [eid for eid, _, _ in entries]
            namespace = entries[0][2] if entries else "default"

            # Downgrade to info when all events are from system namespaces
            all_system = all(ns in SYSTEM_NAMESPACES for _, _, ns in entries)
            if all_system:
                severity = "info"
            elif reason in HIGH_SEVERITY_REASONS:
                severity = "high"
            else:
                severity = "medium"

            # Collect affected pod names for BackOff deduplication
            affected_pods = []
            if reason == "BackOff":
                for _, obj_ref, ns in entries:
                    if obj_ref.startswith("pod/"):
                        affected_pods.append(f"{ns}/{obj_ref[4:]}")

            remediation = {
                "what_happened": (
                    f"{count} Kubernetes Warning events detected in namespace {namespace}. "
                    f"Top reasons: {reason}."
                    + (" (System namespace — may be transient startup noise.)" if all_system else "")
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
                "_affected_pods": affected_pods,
                "_system_namespace_only": all_system,
            }
            finding = Finding(
                bundle_id=bundle_id,
                rule_id=self.rule_id,
                title=f"{reason} Events Detected",
                severity=severity,
                summary=summary,
                evidence_ids=[str(e) for e in evidence_ids],
                status="open",
                remediation=remediation,
            )
            findings.append(finding)

        return findings
