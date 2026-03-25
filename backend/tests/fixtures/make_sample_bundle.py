#!/usr/bin/env python3
"""
Generate a sample-bundle.tar.gz that reliably triggers at least 8 detection rules.
Run from the fixtures directory:
    python make_sample_bundle.py
"""
import io
import json
import os
import tarfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "sample-bundle.tar.gz")

# ── Pods JSON ────────────────────────────────────────────────────────────────

PODS = {
    "apiVersion": "v1",
    "kind": "PodList",
    "items": [
        # 1. CrashLoopBackOff pod → triggers pod_crashloop
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "crashloop-pod",
                "namespace": "production",
                "labels": {"app": "crashloop-pod"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "app",
                        "image": "myapp:latest",
                        "resources": {},
                    }
                ]
            },
            "status": {
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "app",
                        "image": "myapp:latest",
                        "ready": False,
                        "restartCount": 15,
                        "state": {
                            "waiting": {
                                "reason": "CrashLoopBackOff",
                                "message": "back-off 5m0s restarting failed container",
                            }
                        },
                        "lastState": {
                            "terminated": {
                                "reason": "Error",
                                "exitCode": 1,
                                "finishedAt": "2026-03-24T10:00:00Z",
                            }
                        },
                    }
                ],
            },
        },
        # 2. Pending pod → triggers pod_pending
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "pending-pod",
                "namespace": "production",
                "labels": {"app": "pending-pod"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "app",
                        "image": "myapp:latest",
                        "resources": {},
                    }
                ]
            },
            "status": {
                "phase": "Pending",
                "conditions": [
                    {
                        "type": "PodScheduled",
                        "status": "False",
                        "reason": "Unschedulable",
                        "message": "0/3 nodes are available: 3 Insufficient cpu.",
                    }
                ],
            },
        },
        # 3. OOMKilled pod → triggers oom_killed
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "oom-pod-abc12-xyz34",
                "namespace": "production",
                "labels": {"app": "oom-app"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "worker",
                        "image": "worker:v2",
                        "resources": {
                            "limits": {"memory": "128Mi"},
                            "requests": {"memory": "64Mi"},
                        },
                    }
                ]
            },
            "status": {
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "worker",
                        "image": "worker:v2",
                        "ready": False,
                        "restartCount": 3,
                        "state": {"running": {"startedAt": "2026-03-24T10:30:00Z"}},
                        "lastState": {
                            "terminated": {
                                "reason": "OOMKilled",
                                "exitCode": 137,
                                "finishedAt": "2026-03-24T10:29:00Z",
                            }
                        },
                    }
                ],
            },
        },
        # 4. ImagePullBackOff pod → triggers image_pull_error
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "imagepull-pod",
                "namespace": "production",
                "labels": {"app": "imagepull-pod"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "app",
                        "image": "private-registry.example.com/myapp:v99",
                        "resources": {},
                    }
                ]
            },
            "status": {
                "phase": "Pending",
                "containerStatuses": [
                    {
                        "name": "app",
                        "image": "private-registry.example.com/myapp:v99",
                        "ready": False,
                        "restartCount": 0,
                        "state": {
                            "waiting": {
                                "reason": "ImagePullBackOff",
                                "message": "Back-off pulling image \"private-registry.example.com/myapp:v99\"",
                            }
                        },
                    }
                ],
            },
        },
        # 5. Stuck terminating pod → triggers pod_terminating
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "terminating-pod",
                "namespace": "production",
                "deletionTimestamp": "2026-03-24T09:00:00Z",
                "deletionGracePeriodSeconds": 30,
                "labels": {"app": "terminating-pod"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "app",
                        "image": "myapp:latest",
                        "resources": {},
                    }
                ]
            },
            "status": {"phase": "Running"},
        },
        # 6. No resource limits pod → triggers missing_resource_limits
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "no-limits-pod-abc12-def34",
                "namespace": "production",
                "labels": {"app": "no-limits-app"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "server",
                        "image": "nginx:latest",
                        "resources": {},
                    }
                ]
            },
            "status": {"phase": "Running"},
        },
        # 7. Init container failed pod → triggers init_container_failed
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "init-fail-pod",
                "namespace": "production",
                "labels": {"app": "init-fail-pod"},
            },
            "spec": {
                "initContainers": [
                    {
                        "name": "init-db",
                        "image": "busybox:latest",
                        "resources": {},
                    }
                ],
                "containers": [
                    {
                        "name": "app",
                        "image": "myapp:latest",
                        "resources": {},
                    }
                ],
            },
            "status": {
                "phase": "Pending",
                "initContainerStatuses": [
                    {
                        "name": "init-db",
                        "ready": False,
                        "restartCount": 5,
                        "state": {
                            "waiting": {
                                "reason": "CrashLoopBackOff",
                                "message": "back-off 5m0s restarting failed container",
                            }
                        },
                        "lastState": {
                            "terminated": {
                                "reason": "Error",
                                "exitCode": 1,
                            }
                        },
                    }
                ],
            },
        },
    ],
}

# ── Nodes JSON ───────────────────────────────────────────────────────────────

NODES = {
    "apiVersion": "v1",
    "kind": "NodeList",
    "items": [
        # NotReady node → triggers node_not_ready
        {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": "node-1-notready",
                "labels": {"kubernetes.io/hostname": "node-1-notready"},
            },
            "status": {
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "False",
                        "reason": "KubeletNotReady",
                        "message": "PLEG is not healthy",
                        "lastTransitionTime": "2026-03-24T08:00:00Z",
                    },
                    {
                        "type": "MemoryPressure",
                        "status": "False",
                        "reason": "KubeletHasSufficientMemory",
                    },
                ]
            },
        },
        # MemoryPressure node → triggers node_pressure
        {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": "node-2-pressure",
                "labels": {"kubernetes.io/hostname": "node-2-pressure"},
            },
            "status": {
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "KubeletReady",
                    },
                    {
                        "type": "MemoryPressure",
                        "status": "True",
                        "reason": "KubeletHasInsufficientMemory",
                        "message": "kubelet has insufficient memory available",
                        "lastTransitionTime": "2026-03-24T09:00:00Z",
                    },
                ]
            },
        },
        # Healthy node (no findings expected)
        {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": "node-3-healthy",
                "labels": {"kubernetes.io/hostname": "node-3-healthy"},
            },
            "status": {
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "KubeletReady",
                    }
                ]
            },
        },
    ],
}

# ── Events YAML ──────────────────────────────────────────────────────────────
# 15 Warning events to trigger warning_events rule (threshold=10)

def make_events_yaml() -> str:
    events = []
    reasons = ["BackOff", "Failed", "FailedMount", "BackOff", "Failed",
               "BackOff", "Failed", "FailedMount", "BackOff", "Failed",
               "BackOff", "Failed", "FailedMount", "BackOff", "Failed"]
    for i, reason in enumerate(reasons):
        events.append(f"""- apiVersion: v1
  kind: Event
  metadata:
    name: warning-event-{i}
    namespace: production
  type: Warning
  reason: {reason}
  message: "Sample warning event {i} with reason {reason}"
  count: {i + 1}
  involvedObject:
    kind: Pod
    name: crashloop-pod
    namespace: production
  firstTimestamp: "2026-03-24T08:00:00Z"
  lastTimestamp: "2026-03-24T10:00:00Z"
""")
    return "apiVersion: v1\nkind: EventList\nitems:\n" + "".join(events)


# ── PVCs YAML ────────────────────────────────────────────────────────────────

PVC_YAML = """apiVersion: v1
kind: PersistentVolumeClaimList
items:
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: data-pvc
    namespace: production
  spec:
    accessModes:
    - ReadWriteOnce
    resources:
      requests:
        storage: 10Gi
    storageClassName: fast-ssd
  status:
    phase: Pending
"""

# ── Deployments YAML ─────────────────────────────────────────────────────────

DEPLOYMENTS_YAML = """apiVersion: apps/v1
kind: DeploymentList
items:
- apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: api-server
    namespace: production
  spec:
    replicas: 3
    selector:
      matchLabels:
        app: api-server
    template:
      metadata:
        labels:
          app: api-server
      spec:
        containers:
        - name: api
          image: myapi:v1.2.3
          resources:
            limits:
              memory: "512Mi"
              cpu: "500m"
  status:
    replicas: 3
    availableReplicas: 1
    readyReplicas: 1
    unavailableReplicas: 2
"""

# ── Namespaces YAML ──────────────────────────────────────────────────────────

NAMESPACES_YAML = """apiVersion: v1
kind: NamespaceList
items:
- apiVersion: v1
  kind: Namespace
  metadata:
    name: production
  status:
    phase: Active
"""

# ── Jobs YAML ────────────────────────────────────────────────────────────────

JOBS_YAML = """apiVersion: batch/v1
kind: JobList
items:
- apiVersion: batch/v1
  kind: Job
  metadata:
    name: db-migration
    namespace: production
  spec:
    completions: 1
    backoffLimit: 3
    template:
      spec:
        containers:
        - name: migrate
          image: myapp:migrate
  status:
    failed: 4
    active: 0
    succeeded: 0
    conditions:
    - type: Failed
      status: "True"
      reason: BackoffLimitExceeded
      message: Job has reached the specified backoff limit
"""

# ── ReplicaSets YAML ─────────────────────────────────────────────────────────

REPLICASETS_YAML = """apiVersion: apps/v1
kind: ReplicaSetList
items:
- apiVersion: apps/v1
  kind: ReplicaSet
  metadata:
    name: api-server-7d9f8b5c6
    namespace: production
    ownerReferences:
    - apiVersion: apps/v1
      kind: Deployment
      name: api-server
  spec:
    replicas: 3
    selector:
      matchLabels:
        app: api-server
  status:
    replicas: 1
    availableReplicas: 1
    readyReplicas: 1
"""


# ── KOTS Config Files ─────────────────────────────────────────────────────────

KOTS_CONFIGVALUES_YAML = """apiVersion: kots.io/v1beta1
kind: ConfigValues
metadata:
  name: my-app
spec:
  values:
    replicas:
      value: "1"
    debug_mode:
      value: "true"
    tls_enabled:
      value: "false"
    storage_size:
      value: "5"
    s3_bucket:
      value: ""
    memory_limit:
      value: "256Mi"
"""

KOTS_CONFIG_YAML = """apiVersion: kots.io/v1beta1
kind: Config
metadata:
  name: my-app
spec:
  groups:
    - name: deployment
      title: Deployment Settings
      items:
        - name: replicas
          title: Replica Count
          type: text
          default: "2"
        - name: debug_mode
          title: Debug Mode
          type: bool
          default: "false"
        - name: tls_enabled
          title: Enable TLS
          type: bool
          default: "true"
        - name: storage_size
          title: Storage Size (Gi)
          type: text
          default: "20"
        - name: s3_bucket
          title: S3 Bucket Name
          type: text
        - name: memory_limit
          title: Memory Limit
          type: text
          default: "512Mi"
"""


def add_file(tf: tarfile.TarFile, path: str, content: str) -> None:
    encoded = content.encode("utf-8")
    info = tarfile.TarInfo(name=path)
    info.size = len(encoded)
    tf.addfile(info, io.BytesIO(encoded))


def main() -> None:
    with tarfile.open(OUTPUT_PATH, "w:gz") as tf:
        base = "sample-bundle/cluster-resources"

        add_file(tf, f"{base}/namespaces.yaml", NAMESPACES_YAML)
        add_file(tf, f"{base}/pods.json", json.dumps(PODS, indent=2))
        add_file(tf, f"{base}/nodes.json", json.dumps(NODES, indent=2))
        add_file(tf, f"{base}/events.yaml", make_events_yaml())
        add_file(tf, f"{base}/pvcs.yaml", PVC_YAML)
        add_file(tf, f"{base}/deployments.yaml", DEPLOYMENTS_YAML)
        add_file(tf, f"{base}/jobs.yaml", JOBS_YAML)
        add_file(tf, f"{base}/replicasets.yaml", REPLICASETS_YAML)

        # KOTS config files
        kots_base = "sample-bundle/kots"
        add_file(tf, f"{kots_base}/configvalues.yaml", KOTS_CONFIGVALUES_YAML)
        add_file(tf, f"{kots_base}/config.yaml", KOTS_CONFIG_YAML)

    print(f"Created {OUTPUT_PATH}")
    import os
    size = os.path.getsize(OUTPUT_PATH)
    print(f"File size: {size} bytes")


if __name__ == "__main__":
    main()
