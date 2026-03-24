"""
Tests for the new detection rules added in the warnings expansion.
"""
import uuid
from unittest.mock import MagicMock


from app.detection.rules.daemonset_unavailable import DaemonSetUnavailableRule
from app.detection.rules.failed_jobs import FailedJobsRule
from app.detection.rules.high_restart_count import HighRestartCountRule
from app.detection.rules.init_container_failed import InitContainerFailedRule
from app.detection.rules.missing_resource_limits import MissingResourceLimitsRule
from app.detection.rules.pod_terminating import PodTerminatingRule
from app.detection.rules.warning_event_reasons import (
    CRITICAL_THRESHOLD_ONE,
    WarningEventReasonsRule,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_session(evidence_list):
    """Return a mock SQLAlchemy Session that yields evidence_list for any query."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = evidence_list
    session = MagicMock()
    session.execute.return_value = mock_result
    return session


def _evidence(kind, raw_data):
    e = MagicMock()
    e.id = uuid.uuid4()
    e.kind = kind
    e.raw_data = raw_data
    return e


BUNDLE = uuid.uuid4()


# ---------------------------------------------------------------------------
# pod_terminating
# ---------------------------------------------------------------------------

class TestPodTerminatingRule:
    rule = PodTerminatingRule()

    def test_detects_terminating_pod(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "my-pod", "namespace": "default", "deletionTimestamp": "2026-01-01T00:00:00Z", "deletionGracePeriodSeconds": 30},
            "status": {"phase": "Running"},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert len(findings) == 1
        assert "my-pod" in findings[0].summary

    def test_ignores_running_pod(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "healthy", "namespace": "default"},
            "status": {"phase": "Running"},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []

    def test_multiple_terminating_pods(self):
        pods = [
            _evidence("Pod", {"metadata": {"name": f"pod-{i}", "namespace": "default", "deletionTimestamp": "2026-01-01T00:00:00Z"}, "status": {}})
            for i in range(3)
        ]
        findings = self.rule.evaluate(BUNDLE, _mock_session(pods))
        assert len(findings) == 1
        assert "3 pod(s)" in findings[0].summary


# ---------------------------------------------------------------------------
# init_container_failed
# ---------------------------------------------------------------------------

class TestInitContainerFailedRule:
    rule = InitContainerFailedRule()

    def test_detects_crashloop_init_container(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "init-fail", "namespace": "default"},
            "status": {
                "initContainerStatuses": [{
                    "name": "migrate",
                    "ready": False,
                    "restartCount": 5,
                    "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                    "lastState": {},
                }]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert len(findings) == 1
        assert "init-fail" in findings[0].summary

    def test_ignores_ready_init_container(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "ok-pod", "namespace": "default"},
            "status": {
                "initContainerStatuses": [{
                    "name": "migrate",
                    "ready": True,
                    "restartCount": 0,
                    "state": {"running": {}},
                    "lastState": {},
                }]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []

    def test_detects_oom_killed_init_container(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "oom-init", "namespace": "default"},
            "status": {
                "initContainerStatuses": [{
                    "name": "setup",
                    "ready": False,
                    "restartCount": 2,
                    "state": {"waiting": {"reason": "OOMKilled"}},
                    "lastState": {},
                }]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# high_restart_count
# ---------------------------------------------------------------------------

class TestHighRestartCountRule:
    rule = HighRestartCountRule()

    def test_detects_high_restart(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "restarter", "namespace": "default"},
            "status": {
                "containerStatuses": [{
                    "name": "app",
                    "restartCount": 5,
                    "ready": True,
                    "state": {"running": {}},
                }]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert len(findings) == 1
        assert "5" in findings[0].summary

    def test_detects_not_ready_with_any_restarts(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "not-ready", "namespace": "default"},
            "status": {
                "containerStatuses": [{
                    "name": "app",
                    "restartCount": 1,
                    "ready": False,
                    "state": {"running": {}},
                }]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert len(findings) == 1

    def test_ignores_low_restart_and_ready(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "stable", "namespace": "default"},
            "status": {
                "containerStatuses": [{"name": "app", "restartCount": 2, "ready": True, "state": {"running": {}}}]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []

    def test_ignores_crashloop_already_handled(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "crasher", "namespace": "default"},
            "status": {
                "containerStatuses": [{
                    "name": "app",
                    "restartCount": 50,
                    "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                }]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []


# ---------------------------------------------------------------------------
# failed_jobs
# ---------------------------------------------------------------------------

class TestFailedJobsRule:
    rule = FailedJobsRule()

    def test_detects_failed_job(self):
        job = _evidence("Job", {
            "metadata": {"name": "batch-job", "namespace": "default"},
            "spec": {"completions": 1},
            "status": {"failed": 3, "active": 0, "succeeded": 0},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([job]))
        assert len(findings) == 1
        assert "batch-job" in findings[0].summary

    def test_detects_job_with_failed_condition(self):
        job = _evidence("Job", {
            "metadata": {"name": "cron-job", "namespace": "default"},
            "spec": {"completions": 1},
            "status": {
                "failed": 0,
                "active": 0,
                "succeeded": 0,
                "conditions": [{"type": "Failed", "status": "True"}],
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([job]))
        assert len(findings) == 1

    def test_ignores_successful_job(self):
        job = _evidence("Job", {
            "metadata": {"name": "done-job", "namespace": "default"},
            "spec": {"completions": 1},
            "status": {"failed": 0, "active": 0, "succeeded": 1},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([job]))
        assert findings == []


# ---------------------------------------------------------------------------
# daemonset_unavailable
# ---------------------------------------------------------------------------

class TestDaemonSetUnavailableRule:
    rule = DaemonSetUnavailableRule()

    def test_detects_partially_unavailable_daemonset(self):
        ds = _evidence("DaemonSet", {
            "metadata": {"name": "fluentd", "namespace": "kube-system"},
            "status": {"desiredNumberScheduled": 5, "numberReady": 3, "numberUnavailable": 2, "numberMisscheduled": 0},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([ds]))
        assert len(findings) == 1
        assert "fluentd" in findings[0].summary

    def test_ignores_fully_ready_daemonset(self):
        ds = _evidence("DaemonSet", {
            "metadata": {"name": "healthy-ds", "namespace": "default"},
            "status": {"desiredNumberScheduled": 3, "numberReady": 3, "numberUnavailable": 0, "numberMisscheduled": 0},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([ds]))
        assert findings == []

    def test_detects_misscheduled_daemonset(self):
        ds = _evidence("DaemonSet", {
            "metadata": {"name": "mis-ds", "namespace": "default"},
            "status": {"desiredNumberScheduled": 3, "numberReady": 3, "numberUnavailable": 0, "numberMisscheduled": 1},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([ds]))
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# missing_resource_limits
# ---------------------------------------------------------------------------

class TestMissingResourceLimitsRule:
    rule = MissingResourceLimitsRule()

    def test_detects_missing_limits(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "limitless", "namespace": "default"},
            "status": {"phase": "Running"},
            "spec": {
                "containers": [{"name": "app", "resources": {}}]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert len(findings) == 1
        assert "limitless" in findings[0].summary

    def test_ignores_pod_with_limits(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "limited", "namespace": "default"},
            "status": {"phase": "Running"},
            "spec": {
                "containers": [{"name": "app", "resources": {"limits": {"memory": "256Mi", "cpu": "500m"}}}]
            },
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []

    def test_ignores_kube_system(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "coredns", "namespace": "kube-system"},
            "status": {"phase": "Running"},
            "spec": {"containers": [{"name": "coredns", "resources": {}}]},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []

    def test_ignores_completed_pods(self):
        pod = _evidence("Pod", {
            "metadata": {"name": "done", "namespace": "default"},
            "status": {"phase": "Succeeded"},
            "spec": {"containers": [{"name": "job", "resources": {}}]},
        })
        findings = self.rule.evaluate(BUNDLE, _mock_session([pod]))
        assert findings == []


# ---------------------------------------------------------------------------
# warning_event_reasons — expanded list + critical threshold
# ---------------------------------------------------------------------------

class TestWarningEventReasonsExpanded:
    rule = WarningEventReasonsRule()

    def _make_events(self, reason, count, obj_name="pod/my-pod"):
        return [
            _evidence("Event", {
                "type": "Warning",
                "reason": reason,
                "involvedObject": {"kind": "Pod", "name": obj_name},
            })
            for _ in range(count)
        ]

    def test_critical_reason_fires_on_one_event(self):
        for reason in CRITICAL_THRESHOLD_ONE:
            events = self._make_events(reason, 1)
            findings = self.rule.evaluate(BUNDLE, _mock_session(events))
            assert len(findings) == 1, f"Expected finding for {reason} with 1 event"

    def test_unhealthy_fires_at_two(self):
        events = self._make_events("Unhealthy", 2)
        findings = self.rule.evaluate(BUNDLE, _mock_session(events))
        assert len(findings) == 1

    def test_unhealthy_does_not_fire_on_one(self):
        events = self._make_events("Unhealthy", 1)
        findings = self.rule.evaluate(BUNDLE, _mock_session(events))
        assert findings == []

    def test_oom_killing_fires_on_one(self):
        events = self._make_events("OOMKilling", 1)
        findings = self.rule.evaluate(BUNDLE, _mock_session(events))
        assert len(findings) == 1
        assert findings[0].severity == "high"

    def test_failed_binding_fires_after_threshold(self):
        events = self._make_events("FailedBinding", 3)
        findings = self.rule.evaluate(BUNDLE, _mock_session(events))
        assert len(findings) == 1

    def test_provisioning_failed_fires_after_threshold(self):
        events = self._make_events("ProvisioningFailed", 3)
        findings = self.rule.evaluate(BUNDLE, _mock_session(events))
        assert len(findings) == 1
