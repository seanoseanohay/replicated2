"""
Complex eval tests (10 cases).

Scenarios with multiple interacting issues or ambiguous root causes where
mechanical keyword checks are insufficient. LLM-as-judge evaluates whether
the model recognises the complexity rather than oversimplifying.

Run with:  pytest -m eval tests/evals/test_complex.py
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
# 1. CrashLoopBackOff with alternating OOM + app-crash exit codes
# ---------------------------------------------------------------------------
def test_complex_crashloop_ambiguous_oom_and_app_error():
    """Two distinct failure modes (OOM and app error) must both be addressed."""
    finding = make_finding(
        title="Pod CrashLoopBackOff — Ambiguous Exit Codes",
        severity="critical",
        summary=(
            "Pod worker-7f4d-abc in production is crashing with alternating "
            "exit codes 137 (OOMKilled) and 1 (app error)."
        ),
        rule_id="crashloop_backoff",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="worker-7f4d-abc",
            namespace="production",
            raw_data={
                "status": {
                    "containerStatuses": [{
                        "name": "worker",
                        "restartCount": 23,
                        "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                        "lastState": {
                            "terminated": {"exitCode": 1, "reason": "Error", "finishedAt": "2026-03-19T10:10:00Z"}
                        },
                    }],
                },
                "spec": {
                    "containers": [{
                        "name": "worker",
                        "image": "worker:v3.1.0",
                        "resources": {"limits": {"memory": "256Mi"}, "requests": {"memory": "128Mi"}},
                    }]
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="worker-7f4d-abc.oom",
            namespace="production",
            raw_data={
                "reason": "OOMKilling",
                "message": "Memory cgroup out of memory: Kill process 1042 (worker) score 1982 or sacrifice child",
                "count": 8,
                "type": "Warning",
            },
        ),
        make_evidence(
            kind="Event",
            name="worker-7f4d-abc.err",
            namespace="production",
            raw_data={
                "reason": "BackOff",
                "message": (
                    "Back-off restarting failed container worker; Last exit code: 1; "
                    "container logs show: 'FATAL: database connection refused'"
                ),
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response acknowledge TWO distinct failure modes — OOM kill AND "
            "application error (database connection refused) — and provide remediation "
            "for both? A high-quality response should not treat this as a single-cause issue."
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 2. Multiple nodes NotReady — cascading pod pending
# ---------------------------------------------------------------------------
def test_complex_multinode_notready_cascade():
    """3/5 nodes down, 47 pods pending; model must address cluster-wide impact."""
    finding = make_finding(
        title="Multiple Nodes Not Ready — Cascading Pod Failures",
        severity="critical",
        summary=(
            "3 of 5 worker nodes are NotReady, causing 47 pods to be Pending "
            "across all namespaces."
        ),
        rule_id="node_not_ready",
    )
    evidence = [
        make_evidence(
            kind="Node",
            name="worker-node-2",
            namespace="",
            raw_data={
                "status": {
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "False",
                            "reason": "NodeStatusUnknown",
                            "lastHeartbeatTime": "2026-03-19T08:00:00Z",
                        },
                        {"type": "DiskPressure", "status": "False"},
                    ]
                }
            },
        ),
        make_evidence(
            kind="Node",
            name="worker-node-4",
            namespace="",
            raw_data={
                "status": {
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "False",
                            "reason": "KubeletNotReady",
                            "message": "container runtime is down",
                        },
                    ]
                }
            },
        ),
        make_evidence(
            kind="Event",
            name="cluster.nodedown",
            namespace="kube-system",
            raw_data={
                "reason": "NodeNotReady",
                "message": "Node worker-node-2 status is now: NodeNotReady",
                "type": "Normal",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response address the cluster-wide blast radius (multiple nodes, cascading "
            "pod rescheduling), not just single-node recovery? Does it mention investigating "
            "the common failure mode across nodes and the impact on running workloads?"
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 3. Init container blocked by missing Secret
# ---------------------------------------------------------------------------
def test_complex_init_container_missing_secret():
    """Init container can't mount Secret; main container never starts."""
    finding = make_finding(
        title="Pod Stuck in Init — Secret Not Found",
        severity="high",
        summary=(
            "Pod api-server-6d4f-xyz in production is stuck in Init:0/1; "
            "init container cannot mount the required secret."
        ),
        rule_id="pod_init_failing",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="api-server-6d4f-xyz",
            namespace="production",
            raw_data={
                "status": {
                    "phase": "Pending",
                    "initContainerStatuses": [{
                        "name": "init-db-creds",
                        "state": {"waiting": {"reason": "PodInitializing"}},
                        "ready": False,
                    }],
                    "containerStatuses": [],
                },
                "spec": {
                    "initContainers": [{
                        "name": "init-db-creds",
                        "image": "busybox:1.35",
                        "command": ["sh", "-c", "cp /secrets/db-password /config/db-password"],
                        "volumeMounts": [{"name": "db-secret", "mountPath": "/secrets", "readOnly": True}],
                    }],
                    "volumes": [{"name": "db-secret", "secret": {"secretName": "postgres-credentials"}}],
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="api-server-6d4f-xyz.secret",
            namespace="production",
            raw_data={
                "reason": "Failed",
                "message": (
                    'MountVolume.SetUp failed for volume "db-secret": '
                    'secret "postgres-credentials" not found'
                ),
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["secret", "postgres-credentials", "init", "volume"],
        min_matches=3,
    )


# ---------------------------------------------------------------------------
# 4. Rolling update blocked by PodDisruptionBudget
# ---------------------------------------------------------------------------
def test_complex_rolling_update_stuck_pdb():
    """PDB minAvailable=3 with only 3 healthy pods prevents rolling drain."""
    finding = make_finding(
        title="Deployment Rollout Stuck — PodDisruptionBudget Blocking Drain",
        severity="high",
        summary=(
            "Deployment elasticsearch in namespace logging has been stuck rolling out for 45 "
            "minutes; 1/3 old pods cannot be evicted."
        ),
        rule_id="deployment_unavailable",
    )
    evidence = [
        make_evidence(
            kind="Deployment",
            name="elasticsearch",
            namespace="logging",
            raw_data={
                "spec": {
                    "replicas": 3,
                    "strategy": {"type": "RollingUpdate", "rollingUpdate": {"maxUnavailable": 1}},
                },
                "status": {
                    "replicas": 4,
                    "updatedReplicas": 2,
                    "readyReplicas": 3,
                    "unavailableReplicas": 1,
                },
            },
        ),
        make_evidence(
            kind="PodDisruptionBudget",
            name="elasticsearch-pdb",
            namespace="logging",
            raw_data={
                "spec": {
                    "minAvailable": 3,
                    "selector": {"matchLabels": {"app": "elasticsearch"}},
                },
                "status": {
                    "currentHealthy": 3,
                    "desiredHealthy": 3,
                    "disruptionsAllowed": 0,
                    "expectedPods": 3,
                },
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["PodDisruptionBudget", "PDB", "evict", "minAvailable"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 5. NetworkPolicy blocking DNS (port 53 egress not allowed)
# ---------------------------------------------------------------------------
def test_complex_networkpolicy_dns_blocked():
    """Egress policy missing port 53; pods can't resolve service names."""
    finding = make_finding(
        title="Pod Cannot Resolve DNS — NetworkPolicy Blocking",
        severity="high",
        summary=(
            "Pods in namespace api-gateway cannot resolve internal service names. "
            "DNS queries to kube-dns are timing out."
        ),
        rule_id="network_connectivity",
    )
    evidence = [
        make_evidence(
            kind="NetworkPolicy",
            name="api-gateway-strict",
            namespace="api-gateway",
            raw_data={
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [{
                        "from": [{"namespaceSelector": {"matchLabels": {"name": "ingress-nginx"}}}]
                    }],
                    "egress": [{
                        "to": [{"ipBlock": {"cidr": "10.0.0.0/8"}}],
                        "ports": [{"port": 443}],
                    }],
                }
            },
        ),
        make_evidence(
            kind="Event",
            name="dns-timeout.pod",
            namespace="api-gateway",
            raw_data={
                "reason": "Failed",
                "message": (
                    "dial tcp: lookup user-service.default.svc.cluster.local "
                    "on 10.96.0.10:53: i/o timeout"
                ),
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["NetworkPolicy", "DNS", "egress", "port 53"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 6. Expired TLS cert causing admission webhook failures
# ---------------------------------------------------------------------------
def test_complex_tls_cert_expired_webhook():
    """Cluster-wide pod creation blocked because admission webhook cert expired."""
    finding = make_finding(
        title="Admission Webhook Failures — TLS Certificate Expired",
        severity="critical",
        summary=(
            "Multiple admission webhooks are failing due to expired TLS certificates, "
            "blocking pod creation cluster-wide."
        ),
        rule_id="webhook_failure",
    )
    evidence = [
        make_evidence(
            kind="Event",
            name="pod-admission-fail",
            namespace="default",
            raw_data={
                "reason": "FailedCreate",
                "message": (
                    "Internal error occurred: failed calling webhook "
                    '"validate.example.com": failed to call webhook: Post '
                    '"https://webhook-service.webhook-system.svc:443/validate": '
                    "x509: certificate has expired or is not yet valid: "
                    "current time 2026-03-19T10:00:00Z is after 2026-01-01T00:00:00Z"
                ),
                "type": "Warning",
            },
        ),
        make_evidence(
            kind="ValidatingWebhookConfiguration",
            name="app-validator",
            namespace="",
            raw_data={
                "webhooks": [{
                    "name": "validate.example.com",
                    "clientConfig": {
                        "service": {
                            "name": "webhook-service",
                            "namespace": "webhook-system",
                            "port": 443,
                        }
                    },
                    "failurePolicy": "Fail",
                    "timeoutSeconds": 10,
                }]
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["certificate", "expired", "TLS", "webhook", "x509"],
        min_matches=3,
    )


# ---------------------------------------------------------------------------
# 7. etcd high latency → API server degradation cascade
# ---------------------------------------------------------------------------
def test_complex_etcd_latency_api_cascade():
    """etcd latency >500ms causing API server timeouts; root cause and downstream impact."""
    finding = make_finding(
        title="etcd High Latency — API Server Degradation",
        severity="critical",
        summary=(
            "etcd response latency has exceeded 500ms p99, causing API server request "
            "timeouts and controller manager backlog."
        ),
        rule_id="etcd_latency",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="etcd-control-plane-1",
            namespace="kube-system",
            raw_data={
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{"name": "etcd", "ready": True, "restartCount": 0}],
                },
                "spec": {
                    "containers": [{
                        "name": "etcd",
                        "command": [
                            "etcd",
                            "--data-dir=/var/lib/etcd",
                            "--quota-backend-bytes=8589934592",
                        ],
                    }]
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="apiserver-timeout",
            namespace="kube-system",
            raw_data={
                "reason": "Timeout",
                "message": (
                    "Timeout: request did not complete within requested timeout 30s — "
                    "context deadline exceeded; etcd took 892ms for last watch response"
                ),
                "type": "Warning",
                "count": 142,
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response address both the etcd performance issue AND its downstream "
            "impact on the API server? Does it suggest concrete etcd diagnostics "
            "(e.g., defragmentation, disk I/O, quota usage check, compaction)?"
        ),
        min_score=3,
    )


# ---------------------------------------------------------------------------
# 8. PV CSI provisioner down — multiple PVCs stuck
# ---------------------------------------------------------------------------
def test_complex_pv_provisioner_down_multiclaim():
    """CSI controller pod crashed; 12 PVCs across 4 namespaces can't provision."""
    finding = make_finding(
        title="Multiple PVCs Pending — CSI Provisioner Unavailable",
        severity="high",
        summary=(
            "12 PersistentVolumeClaims across 4 namespaces are stuck Pending because "
            "the EBS CSI controller pod is down."
        ),
        rule_id="pvc_pending",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="ebs-csi-controller-0",
            namespace="kube-system",
            raw_data={
                "status": {
                    "phase": "Failed",
                    "containerStatuses": [{
                        "name": "ebs-plugin",
                        "state": {"terminated": {"exitCode": 1, "reason": "Error"}},
                        "restartCount": 5,
                    }],
                }
            },
        ),
        make_evidence(
            kind="StorageClass",
            name="gp2",
            namespace="",
            raw_data={
                "provisioner": "ebs.csi.aws.com",
                "reclaimPolicy": "Delete",
                "volumeBindingMode": "WaitForFirstConsumer",
            },
        ),
        make_evidence(
            kind="Event",
            name="pvc-provision-fail",
            namespace="default",
            raw_data={
                "reason": "ProvisioningFailed",
                "message": (
                    "failed to provision volume: rpc error: code = Unavailable "
                    "desc = connection error: transport: connection refused"
                ),
                "type": "Warning",
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["provisioner", "CSI", "StorageClass", "controller"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 9. StatefulSet partially degraded — taint + insufficient memory
# ---------------------------------------------------------------------------
def test_complex_statefulset_mixed_pod_states():
    """kafka-0 and kafka-1 running; kafka-2 Unschedulable due to taint + memory."""
    finding = make_finding(
        title="StatefulSet Partially Degraded",
        severity="high",
        summary=(
            "StatefulSet kafka in namespace messaging has pods kafka-0 and kafka-1 running "
            "but kafka-2 is stuck in Pending."
        ),
        rule_id="statefulset_unavailable",
    )
    evidence = [
        make_evidence(
            kind="StatefulSet",
            name="kafka",
            namespace="messaging",
            raw_data={
                "spec": {
                    "replicas": 3,
                    "serviceName": "kafka-headless",
                    "volumeClaimTemplates": [{
                        "spec": {
                            "storageClassName": "fast-ssd",
                            "resources": {"requests": {"storage": "100Gi"}},
                        }
                    }],
                },
                "status": {"readyReplicas": 2, "replicas": 3},
            },
        ),
        make_evidence(
            kind="Pod",
            name="kafka-2",
            namespace="messaging",
            raw_data={
                "status": {
                    "phase": "Pending",
                    "conditions": [{
                        "type": "PodScheduled",
                        "status": "False",
                        "reason": "Unschedulable",
                        "message": (
                            "0/3 nodes are available: 1 Insufficient memory, "
                            "2 node(s) had untolerated taint {dedicated: kafka}"
                        ),
                    }],
                }
            },
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    assert_keywords(
        explanation + remediation,
        ["StatefulSet", "taint", "memory", "node"],
        min_matches=2,
    )


# ---------------------------------------------------------------------------
# 10. Namespace-wide cascade — pods, service, ingress all failing
# ---------------------------------------------------------------------------
def test_complex_namespace_wide_cascading_failure():
    """Five pods crashing, service has no endpoints, ingress returning 502; root is DB."""
    finding = make_finding(
        title="Namespace-Wide Degradation — Multiple Resource Failures",
        severity="critical",
        summary=(
            "Namespace checkout is experiencing cascading failures: 5 pods crashing, "
            "service has no endpoints, and ingress returns 502."
        ),
        rule_id="namespace_degraded",
    )
    evidence = [
        make_evidence(
            kind="Pod",
            name="checkout-api-xxx",
            namespace="checkout",
            raw_data={
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{
                        "name": "api",
                        "ready": False,
                        "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                        "restartCount": 9,
                    }],
                },
                "spec": {
                    "containers": [{
                        "name": "api",
                        "image": "checkout:v1.5.0",
                        "env": [{"name": "DB_HOST", "value": "postgres.checkout.svc.cluster.local"}],
                    }]
                },
            },
        ),
        make_evidence(
            kind="Event",
            name="checkout-api-xxx.db",
            namespace="checkout",
            raw_data={
                "reason": "BackOff",
                "message": "dial tcp 10.100.5.20:5432: connect: connection refused",
                "type": "Warning",
            },
        ),
        make_evidence(
            kind="Service",
            name="checkout-api",
            namespace="checkout",
            raw_data={"spec": {"selector": {"app": "checkout-api"}}, "status": {}},
        ),
    ]
    explanation, remediation = explain_finding(finding, evidence, None)
    assert_has_sections(explanation, remediation)
    judge_response(
        finding_context=f"{finding.title}: {finding.summary}",
        full_response=explanation + "\n" + remediation,
        criteria=(
            "Does the response identify database connectivity (connection refused on port 5432) "
            "as the likely root cause driving the cascading failures, rather than treating each "
            "symptom (pods, service, ingress) independently?"
        ),
        min_score=3,
    )
