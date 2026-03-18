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
