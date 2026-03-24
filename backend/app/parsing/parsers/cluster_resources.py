import json
import uuid
from pathlib import Path
from typing import Iterator

import yaml

from app.core.logging import get_logger
from app.models.evidence import Evidence
from app.parsing.parsers.base import BaseParser

logger = get_logger(__name__)

# Kinds for which we want full spec preserved; truncate spec for others if large
TARGET_KINDS = {
    "Pod",
    "Deployment",
    "ReplicaSet",
    "StatefulSet",
    "DaemonSet",
    "Service",
    "ConfigMap",
    "Event",
    "Namespace",
    "PersistentVolumeClaim",
    "PersistentVolume",
    "Node",
}

MAX_SPEC_BYTES = 32 * 1024  # 32 KB — truncate spec beyond this


class ClusterResourcesParser(BaseParser):
    """Parses the cluster-resources/ directory of a support bundle."""

    def parse(self, bundle_root: Path, bundle_id: uuid.UUID) -> Iterator[Evidence]:
        resources_dir = bundle_root / "cluster-resources"
        if not resources_dir.is_dir():
            logger.info("cluster_resources_dir_missing", bundle_root=str(bundle_root))
            return

        for file_path in sorted(resources_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix not in (".json", ".yaml", ".yml"):
                continue

            rel_path = str(file_path.relative_to(bundle_root))
            try:
                raw = file_path.read_text(errors="replace")
                if file_path.suffix == ".json":
                    data = json.loads(raw)
                else:
                    data = yaml.safe_load(raw)
            except Exception as exc:
                logger.warning(
                    "cluster_resources_parse_error",
                    file=rel_path,
                    error=str(exc),
                )
                continue

            if not isinstance(data, dict):
                continue

            yield from self._yield_from_object(data, bundle_id, rel_path)

    def _yield_from_object(
        self, data: dict, bundle_id: uuid.UUID, source_path: str
    ) -> Iterator[Evidence]:
        kind = data.get("kind", "")
        if not kind:
            return

        # Handle list types
        if kind.endswith("List") or (
            isinstance(data.get("items"), list)
            and "metadata" not in data.get("items", [{}])[0]
            if data.get("items")
            else False
        ):
            items = data.get("items") or []
            item_kind = kind[:-4] if kind.endswith("List") else kind
            for item in items:
                if not isinstance(item, dict):
                    continue
                if not item.get("kind"):
                    item = dict(item)
                    item.setdefault("kind", item_kind)
                yield from self._yield_single(item, bundle_id, source_path)
            return

        yield from self._yield_single(data, bundle_id, source_path)

    def _yield_single(
        self, obj: dict, bundle_id: uuid.UUID, source_path: str
    ) -> Iterator[Evidence]:
        kind = obj.get("kind", "")
        metadata = obj.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        name = metadata.get("name") or metadata.get("generateName") or "unknown"
        namespace = metadata.get("namespace") or None

        raw_data = _prepare_raw_data(obj)

        yield self._make_evidence(
            bundle_id=bundle_id,
            kind=kind,
            name=name,
            namespace=namespace,
            raw_data=raw_data,
            source_path=source_path,
        )


def _prepare_raw_data(obj: dict) -> dict:
    """Strip managedFields and optionally truncate spec to keep raw_data bounded."""
    result = dict(obj)

    if "metadata" in result and isinstance(result["metadata"], dict):
        metadata = dict(result["metadata"])
        metadata.pop("managedFields", None)
        result["metadata"] = metadata

    # Truncate spec for non-Event kinds if spec is very large
    kind = result.get("kind", "")
    if kind != "Event" and "spec" in result:
        try:
            spec_size = len(json.dumps(result["spec"]))
            if spec_size > MAX_SPEC_BYTES:
                result["spec"] = {"_truncated": True, "_original_size_bytes": spec_size}
        except Exception:
            pass

    return result
