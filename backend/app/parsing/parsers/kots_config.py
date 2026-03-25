import uuid
from pathlib import Path
from typing import Iterator

import yaml

from app.core.logging import get_logger
from app.models.evidence import Evidence
from app.parsing.parsers.base import BaseParser

logger = get_logger(__name__)

# KOTS config filenames we look for
KOTS_CONFIG_FILES = {
    "configvalues.yaml",
    "config.yaml",
    "app.yaml",
    "installation.yaml",
    "license.yaml",
}


class KotsConfigParser(BaseParser):
    """Parses KOTS configuration files from a support bundle."""

    def parse(self, bundle_root: Path, bundle_id: uuid.UUID) -> Iterator[Evidence]:
        # Walk entire bundle looking for KOTS config files
        for file_path in sorted(bundle_root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name not in KOTS_CONFIG_FILES:
                continue

            rel_path = str(file_path.relative_to(bundle_root))
            try:
                raw = file_path.read_text(errors="replace")
                data = yaml.safe_load(raw)
            except Exception as exc:
                logger.warning(
                    "kots_config_parse_error",
                    file=rel_path,
                    error=str(exc),
                )
                continue

            if not isinstance(data, dict):
                continue

            api_version = data.get("apiVersion", "")
            kind = data.get("kind", "")

            # Store the full parsed content as KotsConfig evidence
            raw_data = dict(data)
            raw_data["_source_file"] = file_path.name

            yield self._make_evidence(
                bundle_id=bundle_id,
                kind="KotsConfig",
                name=f"{kind or file_path.stem}:{file_path.name}",
                raw_data=raw_data,
                source_path=rel_path,
            )

            # For configvalues.yaml, also store the values dict as KotsConfigValues
            if (
                file_path.name == "configvalues.yaml"
                and api_version.startswith("kots.io/")
                and kind == "ConfigValues"
            ):
                spec = data.get("spec") or {}
                values = spec.get("values") or {}
                app_name = (data.get("metadata") or {}).get("name") or "unknown"

                yield self._make_evidence(
                    bundle_id=bundle_id,
                    kind="KotsConfigValues",
                    name=app_name,
                    raw_data={
                        "values": values,
                        "_source_file": file_path.name,
                        "_configvalues_raw": data,
                    },
                    source_path=rel_path,
                )
                logger.info(
                    "kots_configvalues_parsed",
                    bundle_id=str(bundle_id),
                    app_name=app_name,
                    key_count=len(values),
                )
