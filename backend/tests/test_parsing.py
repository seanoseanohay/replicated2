"""Tests for Phase 2 parsing package."""
import json
import uuid


from app.parsing.parsers.cluster_resources import ClusterResourcesParser
from app.parsing.parsers.logs import LogsParser
from app.parsing.parsers.cluster_info import ClusterInfoParser
from app.parsing.parsers.host import HostParser
from app.parsing.registry import run_all_parsers


BUNDLE_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# ClusterResourcesParser
# ---------------------------------------------------------------------------


def test_cluster_resources_parser_pod(tmp_path):
    resources_dir = tmp_path / "cluster-resources" / "namespaces" / "default"
    resources_dir.mkdir(parents=True)

    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "my-pod",
            "namespace": "default",
        },
        "spec": {"containers": [{"name": "app", "image": "nginx:latest"}]},
        "status": {"phase": "Running"},
    }
    (resources_dir / "pods.json").write_text(json.dumps(pod))

    parser = ClusterResourcesParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.kind == "Pod"
    assert ev.name == "my-pod"
    assert ev.namespace == "default"
    assert ev.bundle_id == BUNDLE_ID
    # status must be preserved
    assert ev.raw_data.get("status", {}).get("phase") == "Running"


def test_cluster_resources_parser_pod_list(tmp_path):
    resources_dir = tmp_path / "cluster-resources"
    resources_dir.mkdir(parents=True)

    pod_list = {
        "apiVersion": "v1",
        "kind": "PodList",
        "items": [
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "pod-a", "namespace": "kube-system"},
                "status": {"phase": "Running"},
            },
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "pod-b", "namespace": "kube-system"},
                "status": {"phase": "Pending"},
            },
        ],
    }
    (resources_dir / "pods.json").write_text(json.dumps(pod_list))

    parser = ClusterResourcesParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    assert len(evidence_list) == 2
    names = {e.name for e in evidence_list}
    assert names == {"pod-a", "pod-b"}


def test_cluster_resources_parser_bad_file(tmp_path):
    """Parser should skip files that fail to parse, not raise."""
    resources_dir = tmp_path / "cluster-resources"
    resources_dir.mkdir(parents=True)
    (resources_dir / "broken.json").write_text("{ not valid json }")

    parser = ClusterResourcesParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))
    assert evidence_list == []


def test_cluster_resources_parser_missing_dir(tmp_path):
    """Parser should return empty iterator if directory is absent."""
    parser = ClusterResourcesParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))
    assert evidence_list == []


# ---------------------------------------------------------------------------
# LogsParser
# ---------------------------------------------------------------------------


def test_logs_parser_basic(tmp_path):
    log_dir = tmp_path / "pod-logs" / "default" / "my-pod"
    log_dir.mkdir(parents=True)
    log_lines = ["line one", "line two", "line three"]
    (log_dir / "app.log").write_text("\n".join(log_lines))

    parser = LogsParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.kind == "Log"
    assert ev.name == "app"
    assert ev.namespace == "default"
    assert ev.raw_data["total_lines"] == 3
    assert ev.raw_data["lines"] == log_lines


def test_logs_parser_tail_500(tmp_path):
    log_dir = tmp_path / "pod-logs" / "ns" / "pod"
    log_dir.mkdir(parents=True)
    all_lines = [f"line {i}" for i in range(600)]
    (log_dir / "container.log").write_text("\n".join(all_lines))

    parser = LogsParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.raw_data["total_lines"] == 600
    assert len(ev.raw_data["lines"]) == 500
    assert ev.raw_data["lines"][0] == "line 100"


def test_logs_parser_missing_dir(tmp_path):
    parser = LogsParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))
    assert evidence_list == []


def test_logs_parser_skips_large_file(tmp_path):
    log_dir = tmp_path / "pod-logs"
    log_dir.mkdir(parents=True)
    big_log = log_dir / "big.log"
    # Write > 10 MB
    big_log.write_bytes(b"x" * (11 * 1024 * 1024))

    parser = LogsParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))
    assert evidence_list == []


# ---------------------------------------------------------------------------
# ClusterInfoParser
# ---------------------------------------------------------------------------


def test_cluster_info_parser_kubectl_output(tmp_path):
    info_dir = tmp_path / "cluster-info"
    info_dir.mkdir()
    (info_dir / "kubectl-cluster-info").write_text("Kubernetes control plane is running")

    parser = ClusterInfoParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    assert any(e.kind == "ClusterInfo" for e in evidence_list)
    ci = next(e for e in evidence_list if e.kind == "ClusterInfo")
    assert "Kubernetes" in ci.raw_data["output"]


def test_cluster_info_parser_version_json(tmp_path):
    info_dir = tmp_path / "cluster-info"
    info_dir.mkdir()
    version_data = {"major": "1", "minor": "27", "gitVersion": "v1.27.0"}
    (info_dir / "version.json").write_text(json.dumps(version_data))

    parser = ClusterInfoParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    versions = [e for e in evidence_list if e.kind == "ClusterVersion"]
    assert len(versions) == 1
    assert versions[0].raw_data["gitVersion"] == "v1.27.0"


def test_cluster_info_parser_nodes_json(tmp_path):
    info_dir = tmp_path / "cluster-info"
    info_dir.mkdir()
    node_list = {
        "kind": "NodeList",
        "items": [
            {"kind": "Node", "metadata": {"name": "node-1"}, "status": {"conditions": []}},
            {"kind": "Node", "metadata": {"name": "node-2"}, "status": {"conditions": []}},
        ],
    }
    (info_dir / "nodes.json").write_text(json.dumps(node_list))

    parser = ClusterInfoParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    nodes = [e for e in evidence_list if e.kind == "Node"]
    assert len(nodes) == 2
    names = {n.name for n in nodes}
    assert names == {"node-1", "node-2"}


# ---------------------------------------------------------------------------
# HostParser
# ---------------------------------------------------------------------------


def test_host_parser_basic(tmp_path):
    host_dir = tmp_path / "host-collectors"
    host_dir.mkdir()
    data = {"cpu_count": 8, "memory_gb": 32}
    (host_dir / "system-info.json").write_text(json.dumps(data))

    parser = HostParser()
    evidence_list = list(parser.parse(tmp_path, BUNDLE_ID))

    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.kind == "HostInfo"
    assert ev.name == "system-info"
    assert ev.raw_data["cpu_count"] == 8


# ---------------------------------------------------------------------------
# run_all_parsers smoke test
# ---------------------------------------------------------------------------


def test_run_all_parsers_empty_bundle(tmp_path):
    """run_all_parsers on an empty directory should return an empty list without error."""
    result = run_all_parsers(tmp_path, BUNDLE_ID)
    assert isinstance(result, list)


def test_run_all_parsers_with_data(tmp_path):
    """run_all_parsers collects evidence from all parsers that have data."""
    # Set up minimal data for each parser
    (tmp_path / "cluster-info").mkdir()
    (tmp_path / "cluster-info" / "kubectl-cluster-info").write_text("k8s running")

    resources_dir = tmp_path / "cluster-resources"
    resources_dir.mkdir()
    pod = {
        "kind": "Pod",
        "metadata": {"name": "smoke-pod", "namespace": "smoke"},
        "status": {"phase": "Running"},
    }
    (resources_dir / "pods.json").write_text(json.dumps(pod))

    log_dir = tmp_path / "pod-logs" / "smoke" / "smoke-pod"
    log_dir.mkdir(parents=True)
    (log_dir / "app.log").write_text("hello\nworld")

    host_dir = tmp_path / "host-collectors"
    host_dir.mkdir()
    (host_dir / "cpu.json").write_text(json.dumps({"cores": 4}))

    result = run_all_parsers(tmp_path, BUNDLE_ID)
    assert len(result) >= 4

    kinds = {e.kind for e in result}
    assert "ClusterInfo" in kinds
    assert "Pod" in kinds
    assert "Log" in kinds
    assert "HostInfo" in kinds
