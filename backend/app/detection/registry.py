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
from app.models.finding import Finding

logger = logging.getLogger(__name__)

ALL_RULES = [
    NodeNotReadyRule(),
    PodCrashLoopRule(),
    OOMKilledRule(),
    ImagePullErrorRule(),
    PodPendingRule(),
    PVCPendingRule(),
    WarningEventsRule(),
    ResourceQuotaRule(),
    NodePressureRule(),
    DeploymentUnavailableRule(),
    StatefulSetUnavailableRule(),
    HPAMaxedRule(),
    WarningEventReasonsRule(),
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
