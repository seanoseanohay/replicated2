"""
Golden-path eval tests (10 cases).

Classic, well-understood Kubernetes issues where the correct explanation and
remediation terms are known ahead of time. Assertions use structural checks
and keyword matching — no judge needed.

Run with:  pytest -m eval tests/evals/test_golden.py
"""

import os

import pytest

from app.ai.explainer import explain_finding

from .helpers import assert_has_sections, assert_keywords, make_evidence, make_finding

pytestmark = [
    pytest.mark.eval,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set — skipping live eval tests",
    ),
]


# ---------------------------------------------------------------------------
# 1. CrashLoopBackOff — OOMKilled (exit 137)
# ---------------------------------------------------------------------------
def test_golden_crashloop_oomkilled():
    """Pod repeatedly OOMKilled; model must identify memory limits and suggest increase."""
    finding = make_finding(
        title="Pod CrashLoopBackOff",
        severity="critical",
        summary="Pod web-7f9d5b-xkp2r in namespace production is in CrashLoopBackOff with 18 restarts.",
        rule_id="crashloop_backoff",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="web-7f9d5b-xkp2r",
            namespace="production",
            raw_data={
                "status": {
                    "containerStatuses": [
                        {
                            "name": "web",
                            "restartCount": 18,
                            "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                            "lastState": {
                                "terminated": {
                                    "exitCode": 137,
                                    "reason": "OOMKilled",
                                    "finishedAt": "2026-03-19T09:45:00Z",
                                }
                            },
                        }
                    ],
                },
                "spec": {
                    "containers": [
                        {
                            "name": "web",
                            "image": "myapp:v2.3.1",
                            "resources": {
                                "limits": {"memory": "128Mi", "cpu": "500m"},
                                "requests": {"memory": "64Mi", "cpu": "250m"},
                            },
                        }
                    ]
                },
            },
        )
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["OOMKilled", "memory", "137", "limit"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 2. ImagePullBackOff — bad image tag
# ---------------------------------------------------------------------------
def test_golden_imagepullbackoff_bad_tag():
    """Pod cannot pull image; model must identify the bad reference and suggest fix."""
    finding = make_finding(
        title="Pod ImagePullBackOff",
        severity="high",
        summary="Pod api-deploy-5c8f7d-mn3jp in namespace staging cannot pull its container image.",
        rule_id="image_pull_error",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="api-deploy-5c8f7d-mn3jp",
            namespace="staging",
            raw_data={
                "status": {
                    "phase": "Pending",
                    "containerStatuses": [
                        {
                            "name": "api",
                            "state": {
                                "waiting": {
                                    "reason": "ImagePullBackOff",
                                    "message": 'Back-off pulling image "registry.example.com/api:v99.0.0"',
                                }
                            },
                            "restartCount": 0,
                        }
                    ],
                },
                "spec": {
                    "containers": [
                        {"name": "api", "image": "registry.example.com/api:v99.0.0"}
                    ]
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="api-deploy-5c8f7d-mn3jp.imagepull",
            namespace="staging",
            raw_data={
                "reason": "Failed",
                "message": (
                    'Failed to pull image "registry.example.com/api:v99.0.0": '
                    "rpc error: code = NotFound desc = failed to pull and unpack image: not found"
                ),
                "type": "Warning",
                "count": 5,
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["image", "registry", "tag", "pull"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 3. Node NotReady — disk pressure
# ---------------------------------------------------------------------------
def test_golden_node_notready_disk_pressure():
    """Node down with DiskPressure condition; model must mention disk cleanup."""
    finding = make_finding(
        title="Node Not Ready",
        severity="critical",
        summary="Node worker-node-3 has been in NotReady state for 12 minutes.",
        rule_id="node_not_ready",
    )
    evidence = [
        make_evidence(
            kind="Node",
            name="worker-node-3",
            namespace="",
            raw_data={
                "status": {
                    "conditions": [
                        {
                            "type": "DiskPressure",
                            "status": "True",
                            "message": "disk usage is above threshold",
                        },
                        {"type": "MemoryPressure", "status": "False"},
                        {"type": "PIDPressure", "status": "False"},
                        {
                            "type": "Ready",
                            "status": "False",
                            "reason": "KubeletNotReady",
                            "message": "PLEG is not healthy",
                        },
                    ],
                    "allocatable": {
                        "cpu": "4",
                        "memory": "8Gi",
                        "ephemeral-storage": "20Gi",
                    },
                }
            },
        )
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["disk", "pressure", "kubelet", "storage"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 4. PVC Pending — StorageClass not found
# ---------------------------------------------------------------------------
def test_golden_pvc_pending_no_storageclass():
    """PVC cannot bind because referenced StorageClass doesn't exist."""
    finding = make_finding(
        title="PersistentVolumeClaim Pending",
        severity="high",
        summary="PVC data-postgres-0 in namespace database has been Pending for 30 minutes.",
        rule_id="pvc_pending",
    )
    evidence = [
        make_evidence(
            kind="PersistentVolumeClaim",
            name="data-postgres-0",
            namespace="database",
            raw_data={
                "spec": {
                    "storageClassName": "fast-ssd",
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "50Gi"}},
                },
                "status": {"phase": "Pending"},
            },
        ),
        make_evidence(
            kind="Event",
            name="data-postgres-0.pvc",
            namespace="database",
            raw_data={
                "reason": "ProvisioningFailed",
                "message": 'storageclass.storage.k8s.io "fast-ssd" not found',
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["StorageClass", "fast-ssd", "provision"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 5. Deployment unavailable — 0 ready replicas
# ---------------------------------------------------------------------------
def test_golden_deployment_unavailable():
    """Deployment with 0/3 available replicas; model must explain and guide fix."""
    finding = make_finding(
        title="Deployment Unavailable",
        severity="critical",
        summary="Deployment backend in namespace production has 0/3 available replicas.",
        rule_id="deployment_unavailable",
    )
    evidence = [
        make_evidence(
            kind="Deployment",
            name="backend",
            namespace="production",
            raw_data={
                "spec": {"replicas": 3},
                "status": {
                    "availableReplicas": 0,
                    "readyReplicas": 0,
                    "replicas": 3,
                    "unavailableReplicas": 3,
                    "conditions": [
                        {
                            "type": "Available",
                            "status": "False",
                            "reason": "MinimumReplicasUnavailable",
                            "message": "Deployment does not have minimum availability.",
                        }
                    ],
                },
            },
        )
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["replica", "available", "deployment"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 6. ResourceQuota exceeded — new pods blocked
# ---------------------------------------------------------------------------
def test_golden_resource_quota_exceeded():
    """Namespace quota at capacity; model must explain quota mechanics and remediation."""
    finding = make_finding(
        title="ResourceQuota Exceeded",
        severity="high",
        summary="ResourceQuota prod-quota in namespace production is at capacity, blocking new pod creation.",
        rule_id="resource_quota_exceeded",
    )
    evidence = [
        make_evidence(
            kind="ResourceQuota",
            name="prod-quota",
            namespace="production",
            raw_data={
                "spec": {
                    "hard": {
                        "pods": "20",
                        "requests.cpu": "8",
                        "requests.memory": "16Gi",
                    }
                },
                "status": {
                    "hard": {
                        "pods": "20",
                        "requests.cpu": "8",
                        "requests.memory": "16Gi",
                    },
                    "used": {
                        "pods": "20",
                        "requests.cpu": "7900m",
                        "requests.memory": "15900Mi",
                    },
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="new-pod-blocked.quota",
            namespace="production",
            raw_data={
                "reason": "FailedCreate",
                "message": (
                    'Error creating: pods "worker-xyz" is forbidden: exceeded quota: prod-quota, '
                    "requested: pods=1, used: pods=20, limited: pods=20"
                ),
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["quota", "pods", "limit"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 7. Service has no endpoints — label selector mismatch
# ---------------------------------------------------------------------------
def test_golden_service_no_endpoints_selector_mismatch():
    """Service selector doesn't match any pod labels; model must identify the mismatch."""
    finding = make_finding(
        title="Service Has No Endpoints",
        severity="high",
        summary="Service frontend-svc in namespace production has no healthy endpoints.",
        rule_id="service_no_endpoints",
    )
    evidence = [
        make_evidence(
            kind="Service",
            name="frontend-svc",
            namespace="production",
            raw_data={
                "spec": {
                    "selector": {"app": "frontend", "version": "v2"},
                    "ports": [{"port": 80, "targetPort": 8080}],
                    "type": "ClusterIP",
                }
            },
        ),
        make_evidence(
            kind="Endpoints",
            name="frontend-svc",
            namespace="production",
            raw_data={"subsets": []},
        ),
        make_evidence(
            kind="Pod",
            name="frontend-6d8f5c-abc",
            namespace="production",
            raw_data={
                "metadata": {"labels": {"app": "frontend", "version": "v1"}},
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                },
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["selector", "label", "endpoint", "version"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 8. HPA maxed out — sustained high CPU
# ---------------------------------------------------------------------------
def test_golden_hpa_maxed_out():
    """HPA at max replicas with CPU still high; model must address scaling ceiling."""
    finding = make_finding(
        title="HorizontalPodAutoscaler at Maximum Replicas",
        severity="medium",
        summary="HPA web-hpa in namespace production has been at max replicas (20) for over 15 minutes.",
        rule_id="hpa_maxed",
    )
    evidence = [
        make_evidence(
            kind="HorizontalPodAutoscaler",
            name="web-hpa",
            namespace="production",
            raw_data={
                "spec": {
                    "scaleTargetRef": {"name": "web", "kind": "Deployment"},
                    "minReplicas": 3,
                    "maxReplicas": 20,
                    "metrics": [
                        {
                            "type": "Resource",
                            "resource": {
                                "name": "cpu",
                                "target": {"averageUtilization": 70},
                            },
                        }
                    ],
                },
                "status": {
                    "currentReplicas": 20,
                    "desiredReplicas": 20,
                    "currentMetrics": [
                        {"resource": {"current": {"averageUtilization": 94}}}
                    ],
                    "conditions": [
                        {
                            "type": "ScalingLimited",
                            "status": "True",
                            "reason": "TooManyReplicas",
                        }
                    ],
                },
            },
        )
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["HPA", "replica", "maximum", "CPU", "scale"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 9. Pod evicted — node memory pressure
# ---------------------------------------------------------------------------
def test_golden_pod_evicted_memory_pressure():
    """Pod evicted by kubelet due to memory pressure; model must explain eviction policy."""
    finding = make_finding(
        title="Pod Evicted",
        severity="high",
        summary="Pod cache-worker-2 in namespace production was evicted due to memory pressure.",
        rule_id="pod_evicted",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="cache-worker-2",
            namespace="production",
            raw_data={
                "status": {
                    "phase": "Failed",
                    "reason": "Evicted",
                    "message": "The node was low on resource: memory. Threshold quantity: 100Mi, available: 45Mi.",
                },
                "spec": {
                    "containers": [
                        {
                            "name": "cache",
                            "resources": {
                                "requests": {"memory": "512Mi"},
                                "limits": {"memory": "1Gi"},
                            },
                        }
                    ]
                },
            },
        ),
        make_evidence(
            kind="Node",
            name="worker-node-1",
            namespace="",
            raw_data={
                "status": {
                    "conditions": [
                        {
                            "type": "MemoryPressure",
                            "status": "True",
                            "message": "memory available(45Mi) is less than the desired threshold(100Mi)",
                        },
                        {"type": "Ready", "status": "True"},
                    ]
                }
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["evict", "memory", "pressure", "node"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 10. Missing ConfigMap — pod volume mount fails
# ---------------------------------------------------------------------------
def test_golden_missing_configmap_volume_mount():
    """Pod stuck because ConfigMap referenced as volume doesn't exist."""
    finding = make_finding(
        title="Pod Pending: Missing ConfigMap",
        severity="high",
        summary=(
            "Pod app-7b9f5c-xmn2p in namespace staging cannot start "
            "due to a missing ConfigMap volume."
        ),
        rule_id="missing_config",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="app-7b9f5c-xmn2p",
            namespace="staging",
            raw_data={
                "status": {
                    "phase": "Pending",
                    "conditions": [{"type": "PodScheduled", "status": "True"}],
                },
                "spec": {
                    "volumes": [
                        {"name": "app-config", "configMap": {"name": "app-settings"}}
                    ],
                    "containers": [
                        {
                            "name": "app",
                            "volumeMounts": [
                                {"name": "app-config", "mountPath": "/etc/config"}
                            ],
                        }
                    ],
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="app-7b9f5c-xmn2p.configmap",
            namespace="staging",
            raw_data={
                "reason": "Failed",
                "message": (
                    'MountVolume.SetUp failed for volume "app-config": '
                    'configmap "app-settings" not found'
                ),
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["ConfigMap", "app-settings", "volume", "mount"],
        min_matches=2,
    )
