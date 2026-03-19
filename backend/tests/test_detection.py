"""
Unit tests for detection rules.
Uses an in-memory SQLite database (no Celery or Postgres needed).
"""
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.evidence import Evidence
from app.detection.rules.pod_crashloop import PodCrashLoopRule
from app.detection.rules.oom_killed import OOMKilledRule
from app.detection.rules.pod_pending import PodPendingRule
from app.detection.rules.node_not_ready import NodeNotReadyRule
from app.detection.rules.image_pull_error import ImagePullErrorRule
from app.detection.rules.pvc_pending import PVCPendingRule
from app.detection.rules.warning_events import WarningEventsRule
from app.detection.rules.resource_quota import ResourceQuotaRule
from app.detection.rules.node_pressure import NodePressureRule
from app.detection.rules.deployment_unavailable import DeploymentUnavailableRule
from app.detection.rules.statefulset_unavailable import StatefulSetUnavailableRule
from app.detection.rules.hpa_maxed import HPAMaxedRule
from app.detection.rules.warning_event_reasons import WarningEventReasonsRule


@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(sync_engine):
    SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
    sess = SessionLocal()
    try:
        yield sess
        sess.rollback()
    finally:
        sess.close()


def make_bundle_id() -> uuid.UUID:
    return uuid.uuid4()


def make_pod_evidence(bundle_id, name, namespace="default", raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="Pod",
        namespace=namespace,
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


def make_node_evidence(bundle_id, name, raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="Node",
        namespace=None,
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


def make_event_evidence(bundle_id, name, raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="Event",
        namespace="default",
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


def make_pvc_evidence(bundle_id, name, namespace="default", raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="PersistentVolumeClaim",
        namespace=namespace,
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


# ── PodCrashLoopRule ──────────────────────────────────────────────────────────

class TestPodCrashLoopRule:
    def test_fires_for_high_restart_count(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "bad-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {"name": "app", "restartCount": 10, "lastState": {}}
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = PodCrashLoopRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "bad-pod" in findings[0].summary
        assert findings[0].severity == "high"

    def test_does_not_fire_for_low_restart_count(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "ok-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {"name": "app", "restartCount": 2, "lastState": {}}
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = PodCrashLoopRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0

    def test_fires_for_crashloop_reason(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "crashloop-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {
                            "name": "app",
                            "restartCount": 1,
                            "lastState": {
                                "terminated": {"reason": "CrashLoopBackOff"}
                            },
                        }
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = PodCrashLoopRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1


# ── OOMKilledRule ─────────────────────────────────────────────────────────────

class TestOOMKilledRule:
    def test_fires_for_oomkilled_container(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "oom-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {
                            "name": "app",
                            "restartCount": 3,
                            "lastState": {
                                "terminated": {"reason": "OOMKilled"}
                            },
                        }
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = OOMKilledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "OOMKilled" in findings[0].title or "oom-pod" in findings[0].summary

    def test_does_not_fire_for_normal_pod(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "normal-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {"name": "app", "restartCount": 0, "lastState": {}}
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = OOMKilledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── NodeNotReadyRule ──────────────────────────────────────────────────────────

class TestNodeNotReadyRule:
    def test_fires_for_not_ready_node(self, session):
        bundle_id = make_bundle_id()
        node = make_node_evidence(
            bundle_id,
            "node-1",
            raw_data={
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "False"}
                    ]
                }
            },
        )
        session.add(node)
        session.commit()

        rule = NodeNotReadyRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "node-1" in findings[0].summary

    def test_does_not_fire_for_ready_node(self, session):
        bundle_id = make_bundle_id()
        node = make_node_evidence(
            bundle_id,
            "node-ready",
            raw_data={
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"}
                    ]
                }
            },
        )
        session.add(node)
        session.commit()

        rule = NodeNotReadyRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── ImagePullErrorRule ────────────────────────────────────────────────────────

class TestImagePullErrorRule:
    def test_fires_for_imagepullbackoff(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "pull-fail-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {
                            "name": "app",
                            "image": "bad-image:latest",
                            "restartCount": 0,
                            "state": {
                                "waiting": {"reason": "ImagePullBackOff"}
                            },
                            "lastState": {},
                        }
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = ImagePullErrorRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "pull-fail-pod" in findings[0].summary

    def test_fires_for_errimagepull(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "err-pull-pod",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {
                            "name": "app",
                            "image": "missing:tag",
                            "restartCount": 0,
                            "state": {
                                "waiting": {"reason": "ErrImagePull"}
                            },
                            "lastState": {},
                        }
                    ]
                }
            },
        )
        session.add(pod)
        session.commit()

        rule = ImagePullErrorRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1


# ── WarningEventsRule ─────────────────────────────────────────────────────────

class TestWarningEventsRule:
    def test_fires_when_more_than_10_warning_events(self, session):
        bundle_id = make_bundle_id()
        for i in range(12):
            event = make_event_evidence(
                bundle_id,
                f"event-{i}",
                raw_data={"type": "Warning", "reason": "BackOff", "message": "back-off"},
            )
            session.add(event)
        session.commit()

        rule = WarningEventsRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "12" in findings[0].summary or "warning" in findings[0].summary.lower()

    def test_does_not_fire_when_few_warning_events(self, session):
        bundle_id = make_bundle_id()
        for i in range(5):
            event = make_event_evidence(
                bundle_id,
                f"event-few-{i}",
                raw_data={"type": "Warning", "reason": "BackOff"},
            )
            session.add(event)
        session.commit()

        rule = WarningEventsRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── PodPendingRule ────────────────────────────────────────────────────────────

class TestPodPendingRule:
    def test_fires_for_pending_pod(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "pending-pod",
            raw_data={"status": {"phase": "Pending"}},
        )
        session.add(pod)
        session.commit()

        rule = PodPendingRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "pending-pod" in findings[0].summary

    def test_does_not_fire_for_running_pod(self, session):
        bundle_id = make_bundle_id()
        pod = make_pod_evidence(
            bundle_id,
            "running-pod",
            raw_data={"status": {"phase": "Running"}},
        )
        session.add(pod)
        session.commit()

        rule = PodPendingRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── NodePressureRule ──────────────────────────────────────────────────────────

def make_deployment_evidence(bundle_id, name, namespace="default", raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="Deployment",
        namespace=namespace,
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


def make_statefulset_evidence(bundle_id, name, namespace="default", raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="StatefulSet",
        namespace=namespace,
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


def make_hpa_evidence(bundle_id, name, namespace="default", raw_data=None):
    e = Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="HorizontalPodAutoscaler",
        namespace=namespace,
        name=name,
        source_path="test",
        raw_data=raw_data or {},
    )
    return e


class TestNodePressureRule:
    def test_fires_for_node_with_disk_pressure(self, session):
        bundle_id = make_bundle_id()
        node = make_node_evidence(
            bundle_id,
            "node-1",
            raw_data={
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "DiskPressure", "status": "True"},
                        {"type": "MemoryPressure", "status": "False"},
                        {"type": "PIDPressure", "status": "False"},
                    ]
                }
            },
        )
        session.add(node)
        session.commit()

        rule = NodePressureRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "node-1" in findings[0].summary
        assert "DiskPressure" in findings[0].summary
        assert findings[0].severity == "medium"

    def test_does_not_fire_for_node_with_all_pressures_false(self, session):
        bundle_id = make_bundle_id()
        node = make_node_evidence(
            bundle_id,
            "healthy-node",
            raw_data={
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "DiskPressure", "status": "False"},
                        {"type": "MemoryPressure", "status": "False"},
                        {"type": "PIDPressure", "status": "False"},
                    ]
                }
            },
        )
        session.add(node)
        session.commit()

        rule = NodePressureRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── DeploymentUnavailableRule ─────────────────────────────────────────────────

class TestDeploymentUnavailableRule:
    def test_fires_when_available_replicas_less_than_desired(self, session):
        bundle_id = make_bundle_id()
        dep = make_deployment_evidence(
            bundle_id,
            "api-server",
            namespace="production",
            raw_data={
                "spec": {"replicas": 3},
                "status": {"availableReplicas": 1},
            },
        )
        session.add(dep)
        session.commit()

        rule = DeploymentUnavailableRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "api-server" in findings[0].summary
        assert "1/3" in findings[0].summary
        assert findings[0].severity == "medium"

    def test_does_not_fire_for_scaled_to_zero_deployment(self, session):
        bundle_id = make_bundle_id()
        dep = make_deployment_evidence(
            bundle_id,
            "paused-app",
            raw_data={
                "spec": {"replicas": 0},
                "status": {"availableReplicas": 0},
            },
        )
        session.add(dep)
        session.commit()

        rule = DeploymentUnavailableRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── StatefulSetUnavailableRule ────────────────────────────────────────────────

class TestStatefulSetUnavailableRule:
    def test_fires_when_ready_replicas_less_than_desired(self, session):
        bundle_id = make_bundle_id()
        sts = make_statefulset_evidence(
            bundle_id,
            "postgres",
            namespace="production",
            raw_data={
                "spec": {"replicas": 3},
                "status": {"readyReplicas": 0},
            },
        )
        session.add(sts)
        session.commit()

        rule = StatefulSetUnavailableRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "postgres" in findings[0].summary
        assert "0/3" in findings[0].summary
        assert findings[0].severity == "medium"

    def test_does_not_fire_for_scaled_to_zero_statefulset(self, session):
        bundle_id = make_bundle_id()
        sts = make_statefulset_evidence(
            bundle_id,
            "paused-db",
            raw_data={
                "spec": {"replicas": 0},
                "status": {"readyReplicas": 0},
            },
        )
        session.add(sts)
        session.commit()

        rule = StatefulSetUnavailableRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── HPAMaxedRule ──────────────────────────────────────────────────────────────

class TestHPAMaxedRule:
    def test_fires_when_current_replicas_equals_max_replicas(self, session):
        bundle_id = make_bundle_id()
        hpa = make_hpa_evidence(
            bundle_id,
            "api-hpa",
            namespace="production",
            raw_data={
                "spec": {"maxReplicas": 10},
                "status": {"currentReplicas": 10},
            },
        )
        session.add(hpa)
        session.commit()

        rule = HPAMaxedRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "api-hpa" in findings[0].summary
        assert "10/10" in findings[0].summary
        assert findings[0].severity == "medium"

    def test_does_not_fire_when_current_replicas_less_than_max(self, session):
        bundle_id = make_bundle_id()
        hpa = make_hpa_evidence(
            bundle_id,
            "api-hpa-ok",
            namespace="production",
            raw_data={
                "spec": {"maxReplicas": 10},
                "status": {"currentReplicas": 5},
            },
        )
        session.add(hpa)
        session.commit()

        rule = HPAMaxedRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── WarningEventReasonsRule ───────────────────────────────────────────────────

class TestWarningEventReasonsRule:
    def test_fires_for_failed_scheduling_with_count_at_threshold(self, session):
        bundle_id = make_bundle_id()
        for i in range(5):
            event = make_event_evidence(
                bundle_id,
                f"sched-event-{bundle_id}-{i}",
                raw_data={
                    "type": "Warning",
                    "reason": "FailedScheduling",
                    "involvedObject": {"kind": "Pod", "name": f"api-server-{i}"},
                },
            )
            session.add(event)
        session.commit()

        rule = WarningEventReasonsRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert "FailedScheduling" in findings[0].summary
        assert "5" in findings[0].summary
        assert findings[0].severity == "high"

    def test_does_not_fire_when_count_below_threshold(self, session):
        bundle_id = make_bundle_id()
        for i in range(2):
            event = make_event_evidence(
                bundle_id,
                f"sched-few-{bundle_id}-{i}",
                raw_data={
                    "type": "Warning",
                    "reason": "FailedScheduling",
                    "involvedObject": {"kind": "Pod", "name": f"pod-{i}"},
                },
            )
            session.add(event)
        session.commit()

        rule = WarningEventReasonsRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0
