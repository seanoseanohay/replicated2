import json
import uuid
from pathlib import Path
from typing import Iterator

import yaml

from app.core.logging import get_logger
from app.models.evidence import Evidence
from app.parsing.parsers.base import BaseParser

logger = get_logger(__name__)


class ClusterInfoParser(BaseParser):
    """Parses the cluster-info/ directory of a support bundle."""

    def parse(self, bundle_root: Path, bundle_id: uuid.UUID) -> Iterator[Evidence]:
        cluster_info_dir = bundle_root / "cluster-info"
        if not cluster_info_dir.is_dir():
            logger.info("cluster_info_dir_missing", bundle_root=str(bundle_root))
            return

        # kubectl-cluster-info plaintext output
        kubectl_file = cluster_info_dir / "kubectl-cluster-info"
        if kubectl_file.exists():
            try:
                text = kubectl_file.read_text(errors="replace")
                yield self._make_evidence(
                    bundle_id=bundle_id,
                    kind="ClusterInfo",
                    name="kubectl-cluster-info",
                    raw_data={"output": text},
                    source_path=str(kubectl_file.relative_to(bundle_root)),
                )
            except Exception as exc:
                logger.warning(
                    "cluster_info_parse_error",
                    file="kubectl-cluster-info",
                    error=str(exc),
                )

        # nodes.json or nodes.yaml — one Evidence per node
        nodes_json = cluster_info_dir / "nodes.json"
        nodes_yaml = cluster_info_dir / "nodes.yaml"

        nodes_file = None
        if nodes_json.exists():
            nodes_file = nodes_json
        elif nodes_yaml.exists():
            nodes_file = nodes_yaml

        if nodes_file is not None:
            try:
                raw = nodes_file.read_text(errors="replace")
                if nodes_file.suffix == ".json":
                    data = json.loads(raw)
                else:
                    data = yaml.safe_load(raw)

                items = []
                if isinstance(data, dict):
                    if data.get("kind") == "NodeList" and "items" in data:
                        items = data["items"]
                    elif data.get("kind") == "Node":
                        items = [data]
                elif isinstance(data, list):
                    items = data

                for node in items:
                    if not isinstance(node, dict):
                        continue
                    metadata = node.get("metadata", {})
                    node_name = metadata.get("name", "unknown")
                    yield self._make_evidence(
                        bundle_id=bundle_id,
                        kind="Node",
                        name=node_name,
                        raw_data=_strip_managed_fields(node),
                        source_path=str(nodes_file.relative_to(bundle_root)),
                    )
            except Exception as exc:
                logger.warning(
                    "cluster_info_parse_error",
                    file=str(nodes_file),
                    error=str(exc),
                )

        # version.json — k8s version info
        version_file = cluster_info_dir / "version.json"
        if version_file.exists():
            try:
                data = json.loads(version_file.read_text(errors="replace"))
                yield self._make_evidence(
                    bundle_id=bundle_id,
                    kind="ClusterVersion",
                    name="version",
                    raw_data=data if isinstance(data, dict) else {"raw": data},
                    source_path=str(version_file.relative_to(bundle_root)),
                )
            except Exception as exc:
                logger.warning(
                    "cluster_info_parse_error",
                    file="version.json",
                    error=str(exc),
                )


def _strip_managed_fields(obj: dict) -> dict:
    """Remove managedFields from metadata to reduce noise, preserving status."""
    result = dict(obj)
    if "metadata" in result and isinstance(result["metadata"], dict):
        metadata = dict(result["metadata"])
        metadata.pop("managedFields", None)
        result["metadata"] = metadata
    return result
