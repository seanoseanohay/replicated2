import logging
import uuid

from sqlalchemy.orm import Session

from app.detection.rules.image_pull_error import ImagePullErrorRule
from app.detection.rules.node_not_ready import NodeNotReadyRule
from app.detection.rules.oom_killed import OOMKilledRule
from app.detection.rules.pod_crashloop import PodCrashLoopRule
from app.detection.rules.pod_pending import PodPendingRule
from app.detection.rules.pvc_pending import PVCPendingRule
from app.detection.rules.resource_quota import ResourceQuotaRule
from app.detection.rules.warning_events import WarningEventsRule
from app.detection.rules.node_pressure import NodePressureRule
from app.detection.rules.deployment_unavailable import DeploymentUnavailableRule
from app.detection.rules.statefulset_unavailable import StatefulSetUnavailableRule
from app.detection.rules.hpa_maxed import HPAMaxedRule
from app.detection.rules.warning_event_reasons import WarningEventReasonsRule
from app.detection.rules.pod_terminating import PodTerminatingRule
from app.detection.rules.init_container_failed import InitContainerFailedRule
from app.detection.rules.high_restart_count import HighRestartCountRule
from app.detection.rules.failed_jobs import FailedJobsRule
from app.detection.rules.daemonset_unavailable import DaemonSetUnavailableRule
from app.detection.rules.missing_resource_limits import MissingResourceLimitsRule
from app.detection.rules.kots_low_replicas import KotsLowReplicasRule
from app.detection.rules.kots_debug_enabled import KotsDebugEnabledRule
from app.detection.rules.kots_tls_disabled import KotsTlsDisabledRule
from app.detection.rules.kots_low_storage import KotsLowStorageRule
from app.detection.rules.kots_missing_s3 import KotsMissingS3Rule
from app.models.finding import Finding

logger = logging.getLogger(__name__)

ALL_RULES = [
    # Critical node / cluster health
    NodeNotReadyRule(),
    NodePressureRule(),
    # Pod lifecycle problems
    PodCrashLoopRule(),
    OOMKilledRule(),
    ImagePullErrorRule(),
    PodPendingRule(),
    PodTerminatingRule(),
    InitContainerFailedRule(),
    HighRestartCountRule(),
    # Storage
    PVCPendingRule(),
    # Workload capacity
    DeploymentUnavailableRule(),
    StatefulSetUnavailableRule(),
    DaemonSetUnavailableRule(),
    HPAMaxedRule(),
    # Jobs
    FailedJobsRule(),
    # Resource hygiene
    ResourceQuotaRule(),
    MissingResourceLimitsRule(),
    # Warning events (broad + specific)
    WarningEventsRule(),
    WarningEventReasonsRule(),
    # KOTS config analysis
    KotsLowReplicasRule(),
    KotsDebugEnabledRule(),
    KotsTlsDisabledRule(),
    KotsLowStorageRule(),
    KotsMissingS3Rule(),
]


def run_all_rules(bundle_id: uuid.UUID, session: Session) -> list[Finding]:
    findings: list[Finding] = []
    for rule in ALL_RULES:
        try:
            results = rule.evaluate(bundle_id, session)
            findings.extend(results)
        except Exception as e:
            logger.warning("rule_error rule=%s error=%s", rule.rule_id, str(e))
    return findings
