"""
Tests for the remediation feature: detection rules produce findings with
non-null remediation dicts containing all required keys.
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.evidence import Evidence
from app.detection.rules.pod_crashloop import PodCrashLoopRule
from app.detection.rules.oom_killed import OOMKilledRule
from app.detection.rules.image_pull_error import ImagePullErrorRule
from app.detection.rules.pvc_pending import PVCPendingRule
from app.detection.rules.missing_resource_limits import MissingResourceLimitsRule

REQUIRED_KEYS = {"what_happened", "why_it_matters", "how_to_fix", "cli_commands"}


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


def add_pod(session, bundle_id, name, namespace="production", raw_data=None):
    ev = Evidence(
        bundle_id=bundle_id,
        kind="Pod",
        name=name,
        namespace=namespace,
        source_path="cluster-resources/pods.json",
        raw_data=raw_data or {},
    )
    session.add(ev)
    session.flush()
    return ev


def add_pvc(session, bundle_id, name, namespace="production", raw_data=None):
    ev = Evidence(
        bundle_id=bundle_id,
        kind="PersistentVolumeClaim",
        name=name,
        namespace=namespace,
        source_path="cluster-resources/pvcs.yaml",
        raw_data=raw_data or {},
    )
    session.add(ev)
    session.flush()
    return ev


# ── pod_crashloop ─────────────────────────────────────────────────────────────

def test_pod_crashloop_has_remediation(session):
    bundle_id = make_bundle_id()
    add_pod(session, bundle_id, "crash-pod", raw_data={
        "status": {
            "phase": "Running",
            "containerStatuses": [{
                "name": "app",
                "restartCount": 15,
                "ready": False,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                "lastState": {"terminated": {"reason": "Error", "exitCode": 1}},
            }],
        }
    })
    findings = PodCrashLoopRule().evaluate(bundle_id, session)
    assert len(findings) == 1
    rem = findings[0].remediation
    assert rem is not None, "remediation should not be None"
    for key in REQUIRED_KEYS:
        assert key in rem, f"remediation missing key: {key}"
    assert isinstance(rem["cli_commands"], list)
    assert len(rem["cli_commands"]) >= 1
    # Commands should reference the pod name and namespace
    assert "crash-pod" in " ".join(rem["cli_commands"])
    assert "production" in " ".join(rem["cli_commands"])


# ── oom_killed ───────────────────────────────────────────────────────────────

def test_oom_killed_has_remediation(session):
    bundle_id = make_bundle_id()
    add_pod(session, bundle_id, "oom-pod-abc12-xyz34", raw_data={
        "status": {
            "phase": "Running",
            "containerStatuses": [{
                "name": "worker",
                "restartCount": 3,
                "ready": False,
                "state": {"running": {"startedAt": "2026-03-24T10:30:00Z"}},
                "lastState": {"terminated": {"reason": "OOMKilled", "exitCode": 137}},
            }],
        }
    })
    findings = OOMKilledRule().evaluate(bundle_id, session)
    assert len(findings) == 1
    rem = findings[0].remediation
    assert rem is not None
    for key in REQUIRED_KEYS:
        assert key in rem, f"remediation missing key: {key}"
    # OOM rule should have patch_yaml
    assert "patch_yaml" in rem
    assert rem["patch_yaml"]  # non-empty
    # patch should reference container name
    assert "worker" in rem["patch_yaml"]


# ── image_pull_error ──────────────────────────────────────────────────────────

def test_image_pull_error_has_remediation(session):
    bundle_id = make_bundle_id()
    add_pod(session, bundle_id, "imagepull-pod", raw_data={
        "status": {
            "phase": "Pending",
            "containerStatuses": [{
                "name": "app",
                "image": "registry.example.com/myapp:v99",
                "restartCount": 0,
                "ready": False,
                "state": {
                    "waiting": {
                        "reason": "ImagePullBackOff",
                        "message": "Back-off pulling image",
                    }
                },
            }],
        }
    })
    findings = ImagePullErrorRule().evaluate(bundle_id, session)
    assert len(findings) == 1
    rem = findings[0].remediation
    assert rem is not None
    for key in REQUIRED_KEYS:
        assert key in rem, f"remediation missing key: {key}"
    # what_happened should mention the image
    assert "registry.example.com/myapp:v99" in rem["what_happened"]


# ── pvc_pending ───────────────────────────────────────────────────────────────

def test_pvc_pending_has_remediation(session):
    bundle_id = make_bundle_id()
    add_pvc(session, bundle_id, "data-pvc", raw_data={
        "status": {"phase": "Pending"}
    })
    findings = PVCPendingRule().evaluate(bundle_id, session)
    assert len(findings) == 1
    rem = findings[0].remediation
    assert rem is not None
    for key in REQUIRED_KEYS:
        assert key in rem, f"remediation missing key: {key}"
    # CLI commands should include kubectl describe pvc and kubectl get storageclass
    cmds = " ".join(rem["cli_commands"])
    assert "data-pvc" in cmds
    assert "storageclass" in cmds.lower()


# ── missing_resource_limits ───────────────────────────────────────────────────

def test_missing_resource_limits_has_remediation(session):
    bundle_id = make_bundle_id()
    add_pod(session, bundle_id, "no-limits-pod-abc12-def34", raw_data={
        "metadata": {"name": "no-limits-pod-abc12-def34", "namespace": "production"},
        "spec": {
            "containers": [{
                "name": "server",
                "image": "nginx:latest",
                "resources": {},
            }]
        },
        "status": {"phase": "Running"},
    })
    findings = MissingResourceLimitsRule().evaluate(bundle_id, session)
    assert len(findings) == 1
    rem = findings[0].remediation
    assert rem is not None
    for key in REQUIRED_KEYS:
        assert key in rem, f"remediation missing key: {key}"
    # Should include patch_yaml with resource limits
    assert "patch_yaml" in rem
    assert "512Mi" in rem["patch_yaml"]


# ── remediation dict shape ────────────────────────────────────────────────────

@pytest.mark.parametrize("rule_cls,pod_data", [
    (
        PodCrashLoopRule,
        {
            "status": {
                "containerStatuses": [{
                    "name": "c",
                    "restartCount": 10,
                    "ready": False,
                    "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                    "lastState": {"terminated": {"reason": "Error"}},
                }]
            }
        },
    ),
    (
        OOMKilledRule,
        {
            "status": {
                "containerStatuses": [{
                    "name": "c",
                    "restartCount": 2,
                    "ready": False,
                    "state": {},
                    "lastState": {"terminated": {"reason": "OOMKilled"}},
                }]
            }
        },
    ),
    (
        ImagePullErrorRule,
        {
            "status": {
                "containerStatuses": [{
                    "name": "c",
                    "image": "bad:image",
                    "restartCount": 0,
                    "ready": False,
                    "state": {"waiting": {"reason": "ImagePullBackOff"}},
                }]
            }
        },
    ),
])
def test_remediation_all_required_keys(session, rule_cls, pod_data):
    bundle_id = make_bundle_id()
    add_pod(session, bundle_id, f"test-pod-{rule_cls.__name__}", raw_data=pod_data)
    findings = rule_cls().evaluate(bundle_id, session)
    assert findings, f"{rule_cls.__name__} produced no findings"
    rem = findings[0].remediation
    assert rem is not None, f"{rule_cls.__name__} finding has no remediation"
    for key in REQUIRED_KEYS:
        assert key in rem, f"{rule_cls.__name__} remediation missing '{key}'"
    assert isinstance(rem["cli_commands"], list), "cli_commands must be a list"
    assert len(rem["cli_commands"]) >= 1, "cli_commands must be non-empty"
