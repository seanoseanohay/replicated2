"""
Multi-step eval tests (10 cases).

Scenarios that require the model to reason through a causal chain from
symptom → intermediate cause → root cause, and produce ordered remediation
steps. LLM-as-judge assesses whether the chain was traced correctly.

Run with:  pytest -m eval tests/evals/test_multistep.py
"""
import os

import pytest

from app.ai.explainer import explain_finding

from .helpers import (
    assert_has_sections,
    assert_keywords,
    judge_response,
    make_evidence,
    make_finding,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set — skipping live eval tests",
    ),
]


# ---------------------------------------------------------------------------
# 1. Service 503 → pods not ready → readiness probe failing → DB unreachable
# ---------------------------------------------------------------------------
def test_multistep_service_503_trace_to_probe():
    """Chain: 503 → unhealthy endpoints → readiness probe → DB unreachable."""
    finding = make_finding(
        title="Service Returning 503 — Unhealthy Endpoints",
        severity="high",
        summary=(
            "Service user-api in production is returning 503. All 3 pods are Running "
            "but marked NotReady by readiness probe."
        ),
        rule_id="service_no_endpoints",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="user-api-6d5f-abc",
            namespace="production",
            raw_data={
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{
                        "name": "api",
                        "ready": False,
                        "state": {"running": {"startedAt": "2026-03-19T09:00:00Z"}},
                        "restartCount": 0,
                    }],
                    "conditions": [
                        {"type": "Ready", "status": "False"},
                        {"type": "ContainersReady", "status": "False"},
                    ],
                },
                "spec": {
                    "containers": [{
                        "name": "api",
                        "readinessProbe": {
                            "httpGet": {"path": "/health/ready", "port": 8080},
                            "initialDelaySeconds": 5,
                            "periodSeconds": 10,
                            "failureThreshold": 3,
                        },
                    }]
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="user-api-probe-fail",
            namespace="production",
            raw_data={
                "reason": "Unhealthy",
                "message": (
                    "Readiness probe failed: HTTP probe failed with statuscode: 503; "
                    'body: {"status":"not ready","db":"unreachable"}'
                ),
                "type": "Warning",
                "count": 48,
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response trace the full causal chain: "
            "(1) service returning 503 because pods are not in endpoints, "
            "(2) pods removed from endpoints because readiness probe fails, "
            "(3) probe fails because the application cannot reach its database? "
            "Does it suggest investigating the database dependency as the root fix?"
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 2. Deployment rollout stuck → new pods crash → missing ConfigMap
# ---------------------------------------------------------------------------
def test_multistep_deployment_rollout_bad_configmap():
    """Chain: rollout stuck → new pods CrashLoopBackOff → ConfigMap for v2 missing."""
    finding = make_finding(
        title="Deployment Rollout Stuck — New Pods Crash on Start",
        severity="high",
        summary=(
            "Deployment payment-service in production is stuck rolling out v2.0.0. "
            "New pods immediately crash with exit code 1."
        ),
        rule_id="deployment_unavailable",
    )
    evidence = [
        make_evidence(
            kind="Deployment",
            name="payment-service",
            namespace="production",
            raw_data={
                "spec": {"replicas": 3},
                "status": {
                    "replicas": 4,
                    "updatedReplicas": 1,
                    "readyReplicas": 3,
                    "unavailableReplicas": 1,
                },
            },
        ),
        make_evidence(
            kind="Pod",
            name="payment-service-v2-xyz",
            namespace="production",
            raw_data={
                "spec": {
                    "containers": [{
                        "name": "payment",
                        "image": "payment-service:v2.0.0",
                        "volumeMounts": [{"name": "config", "mountPath": "/etc/payment"}],
                    }],
                    "volumes": [{"name": "config", "configMap": {"name": "payment-config-v2"}}],
                },
                "status": {
                    "containerStatuses": [{
                        "name": "payment",
                        "restartCount": 4,
                        "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                        "lastState": {
                            "terminated": {
                                "exitCode": 1,
                                "message": "Error: config file not found at /etc/payment/config.yaml",
                            }
                        },
                    }]
                },
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["rollout", "ConfigMap", "payment-config-v2", "rollback"],
        min_matches=2,
    )
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response identify the missing ConfigMap 'payment-config-v2' as the "
            "root cause and suggest EITHER creating the missing ConfigMap OR rolling back "
            "the deployment as remediation options?"
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 3. HPA not scaling → metrics-server pod not ready
# ---------------------------------------------------------------------------
def test_multistep_hpa_inactive_metrics_server_down():
    """Chain: HPA reports FailedGetScale → metrics-server pod not ready → fix metrics-server."""
    finding = make_finding(
        title="HPA Not Scaling — Metrics API Unavailable",
        severity="medium",
        summary=(
            "HPA web-hpa in production is not scaling despite high CPU load. "
            "Metrics server is not returning data."
        ),
        rule_id="hpa_maxed",
    )
    evidence = [
        make_evidence(
            kind="HorizontalPodAutoscaler",
            name="web-hpa",
            namespace="production",
            raw_data={
                "spec": {
                    "minReplicas": 2,
                    "maxReplicas": 10,
                    "metrics": [{
                        "type": "Resource",
                        "resource": {"name": "cpu", "target": {"averageUtilization": 70}},
                    }],
                },
                "status": {
                    "currentReplicas": 2,
                    "desiredReplicas": 2,
                    "conditions": [{
                        "type": "ScalingActive",
                        "status": "False",
                        "reason": "FailedGetScale",
                        "message": (
                            "the HPA was unable to compute the replica count: "
                            "failed to get cpu utilization: unable to get metrics "
                            "for resource cpu: unable to fetch metrics from resource metrics API"
                        ),
                    }],
                },
            },
        ),
        make_evidence(
            kind="Pod",
            name="metrics-server-xxx",
            namespace="kube-system",
            raw_data={
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{
                        "name": "metrics-server",
                        "ready": False,
                        "state": {"running": {"startedAt": "2026-03-19T09:00:00Z"}},
                    }],
                }
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["metrics-server", "HPA", "CPU", "scale"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 4. CronJob failing → pod exits 1 → env var from missing Secret
# ---------------------------------------------------------------------------
def test_multistep_cronjob_failing_missing_secret():
    """Chain: CronJob fails → exit code 1 → Secret not found → create Secret."""
    finding = make_finding(
        title="CronJob Failing — Missing Secret",
        severity="high",
        summary=(
            "CronJob db-backup in namespace ops has failed 6 consecutive times. "
            "Pod exits with code 1."
        ),
        rule_id="job_failing",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="db-backup-28990000-xyz",
            namespace="ops",
            raw_data={
                "spec": {
                    "containers": [{
                        "name": "backup",
                        "image": "backup-tool:v1.2.0",
                        "env": [{
                            "name": "DB_PASSWORD",
                            "valueFrom": {
                                "secretKeyRef": {"name": "db-backup-creds", "key": "password"}
                            },
                        }],
                    }]
                },
                "status": {
                    "phase": "Failed",
                    "containerStatuses": [{
                        "name": "backup",
                        "state": {"terminated": {"exitCode": 1}},
                        "restartCount": 0,
                    }],
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="db-backup-fail.secret",
            namespace="ops",
            raw_data={
                "reason": "Failed",
                "message": 'Error: secret "db-backup-creds" not found',
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["secret", "db-backup-creds", "password"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 5. StatefulSet pod stuck → PVC pending → StorageClass doesn't exist
# ---------------------------------------------------------------------------
def test_multistep_statefulset_pvc_missing_storageclass():
    """Chain: StatefulSet pod Pending → PVC Pending → StorageClass 'premium-ssd' not found."""
    finding = make_finding(
        title="StatefulSet Pod Stuck — PVC Cannot Provision",
        severity="high",
        summary=(
            "StatefulSet mongodb in namespace data has pod mongodb-2 stuck in Pending "
            "because its PVC cannot be provisioned."
        ),
        rule_id="statefulset_unavailable",
    )
    evidence = [
        make_evidence(
            kind="PersistentVolumeClaim",
            name="data-mongodb-2",
            namespace="data",
            raw_data={
                "spec": {
                    "storageClassName": "premium-ssd",
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "200Gi"}},
                },
                "status": {"phase": "Pending"},
            },
        ),
        make_evidence(
            kind="Event",
            name="data-mongodb-2.pvc",
            namespace="data",
            raw_data={
                "reason": "ProvisioningFailed",
                "message": 'storageclass.storage.k8s.io "premium-ssd" not found',
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["StorageClass", "premium-ssd", "PVC", "provision"],
        min_matches=2,
    )
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response trace StatefulSet pod stuck → PVC pending → missing StorageClass "
            "and suggest either creating the 'premium-ssd' StorageClass or updating the "
            "StatefulSet volumeClaimTemplate to reference an existing class?"
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 6. Ingress 404 → service misconfigured → pod label mismatch
# ---------------------------------------------------------------------------
def test_multistep_ingress_404_label_mismatch():
    """Chain: Ingress 404 → service empty endpoints → pod labels don't match selector."""
    finding = make_finding(
        title="Ingress Returning 404 — No Backend Endpoints",
        severity="high",
        summary=(
            "Ingress shop-ingress in namespace shop is returning 404 for all paths. "
            "The backend service has no endpoints."
        ),
        rule_id="service_no_endpoints",
    )
    evidence = [
        make_evidence(
            kind="Ingress",
            name="shop-ingress",
            namespace="shop",
            raw_data={
                "spec": {
                    "rules": [{
                        "host": "shop.example.com",
                        "http": {
                            "paths": [{
                                "path": "/",
                                "backend": {"service": {"name": "shop-svc", "port": {"number": 80}}},
                            }]
                        },
                    }]
                }
            },
        ),
        make_evidence(
            kind="Endpoints",
            name="shop-svc",
            namespace="shop",
            raw_data={"subsets": []},
        ),
        make_evidence(
            kind="Pod",
            name="shop-api-abc",
            namespace="shop",
            raw_data={
                "metadata": {"labels": {"app": "shop", "component": "api-v2"}},
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
        ["label", "selector", "endpoint", "ingress"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 7. Namespace stuck Terminating → finalizers → CRD instances blocking
# ---------------------------------------------------------------------------
def test_multistep_namespace_terminating_finalizer():
    """Chain: Namespace Terminating → finalizer blocking → CRD instances remain."""
    finding = make_finding(
        title="Namespace Stuck in Terminating",
        severity="medium",
        summary=(
            "Namespace old-project has been in Terminating state for 2 hours. "
            "Resources cannot be deleted."
        ),
        rule_id="namespace_stuck",
    )
    evidence = [
        make_evidence(
            kind="Namespace",
            name="old-project",
            namespace="",
            raw_data={
                "metadata": {
                    "name": "old-project",
                    "finalizers": ["kubernetes"],
                    "deletionTimestamp": "2026-03-19T08:00:00Z",
                },
                "status": {"phase": "Terminating"},
            },
        ),
        make_evidence(
            kind="Event",
            name="old-project.terminating",
            namespace="old-project",
            raw_data={
                "reason": "NamespaceFinalizersRemaining",
                "message": (
                    "old-project namespace is undergoing graceful termination; "
                    "Some content remains: [customresourcedefinitions.apiextensions.k8s.io "
                    "has 2 resource instances, myoperator.example.com has 1 resource instances]"
                ),
                "type": "Normal",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["finalizer", "Terminating", "custom resource"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 8. OOM loop → memory limit too low → increase limits
# ---------------------------------------------------------------------------
def test_multistep_oomkilled_loop_increase_limits():
    """Chain: repeated OOMKilled → limits too low → profile and increase memory."""
    finding = make_finding(
        title="Pod Repeatedly OOMKilled — Memory Limits Too Low",
        severity="high",
        summary=(
            "Pod ml-worker-5f6d-xyz in namespace ml is OOMKilled 3–4 times per hour. "
            "Memory usage consistently hits the 512Mi limit."
        ),
        rule_id="oom_killed",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="ml-worker-5f6d-xyz",
            namespace="ml",
            raw_data={
                "status": {
                    "containerStatuses": [{
                        "name": "worker",
                        "restartCount": 47,
                        "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                        "lastState": {"terminated": {"exitCode": 137, "reason": "OOMKilled"}},
                    }]
                },
                "spec": {
                    "containers": [{
                        "name": "worker",
                        "image": "ml-worker:v2.1.0",
                        "resources": {
                            "requests": {"memory": "256Mi", "cpu": "1"},
                            "limits": {"memory": "512Mi", "cpu": "2"},
                        },
                    }]
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="ml-worker-oom",
            namespace="ml",
            raw_data={
                "reason": "OOMKilling",
                "message": (
                    "Memory cgroup out of memory: Kill process 2048 (python) score 2048; "
                    "ml-worker consumed 511Mi before being killed"
                ),
                "type": "Warning",
                "count": 47,
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["OOMKilled", "memory", "limit", "512Mi"],
        min_matches=2,
    )
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response provide a concrete multi-step approach: "
            "(1) confirm memory limit is too low (exit 137), "
            "(2) suggest profiling actual memory usage to determine correct limit, "
            "(3) recommend increasing the limit in the pod/deployment spec? "
            "Bonus if it flags a possible memory leak."
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 9. Node disk pressure → pods evicted → root cause: unmanaged logs
# ---------------------------------------------------------------------------
def test_multistep_disk_pressure_log_accumulation():
    """Chain: disk pressure → pod evictions → logs/ephemeral storage overflowing."""
    finding = make_finding(
        title="Node Disk Pressure — Log Accumulation",
        severity="high",
        summary=(
            "Node worker-node-5 is experiencing disk pressure. Ephemeral storage at 94%. "
            "Multiple pods have been evicted."
        ),
        rule_id="node_disk_pressure",
    )
    evidence = [
        make_evidence(
            kind="Node",
            name="worker-node-5",
            namespace="",
            raw_data={
                "status": {
                    "conditions": [
                        {
                            "type": "DiskPressure",
                            "status": "True",
                            "message": "ephemeral storage usage: 94.2%",
                        },
                        {"type": "Ready", "status": "True"},
                    ],
                    "allocatable": {"ephemeral-storage": "50Gi"},
                }
            },
        ),
        make_evidence(
            kind="Event",
            name="node5-eviction",
            namespace="production",
            raw_data={
                "reason": "Evicted",
                "message": (
                    "The node was low on resource: ephemeral-storage. "
                    "Threshold quantity: 10%, available: 5.8%."
                ),
                "type": "Warning",
                "count": 12,
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["disk", "ephemeral", "log", "evict"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 10. RBAC denied in pod → service account has no binding → create RoleBinding
# ---------------------------------------------------------------------------
def test_multistep_rbac_denied_create_rolebinding():
    """Chain: Forbidden error → SA has no role → create RoleBinding with correct verbs."""
    finding = make_finding(
        title="RBAC Authorization Error in Pod",
        severity="medium",
        summary=(
            "Pod operator-7f8d-xyz in namespace ops is receiving Forbidden errors "
            "when calling the Kubernetes API."
        ),
        rule_id="rbac_error",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="operator-7f8d-xyz",
            namespace="ops",
            raw_data={
                "spec": {
                    "serviceAccountName": "ops-operator",
                    "containers": [{"name": "operator", "image": "my-operator:v1.0.0"}],
                },
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{"name": "operator", "ready": True, "restartCount": 0}],
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="operator-rbac-fail",
            namespace="ops",
            raw_data={
                "reason": "Forbidden",
                "message": (
                    'pods is forbidden: User "system:serviceaccount:ops:ops-operator" '
                    'cannot list resource "pods" in API group "" in the namespace "ops"'
                ),
                "type": "Warning",
                "count": 35,
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["RBAC", "RoleBinding", "serviceaccount", "ops-operator"],
        min_matches=2,
    )
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response trace: (1) pod uses service account 'ops-operator', "
            "(2) that account lacks permission to list pods, "
            "(3) solution is to create a Role and RoleBinding? "
            "Does it provide or describe the required kubectl/YAML?"
        ),
        min_score=3,
    )
