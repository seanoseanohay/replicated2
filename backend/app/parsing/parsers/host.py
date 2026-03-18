import json
import uuid
from pathlib import Path
from typing import Iterator

import yaml

from app.core.logging import get_logger
from app.models.evidence import Evidence
from app.parsing.parsers.base import BaseParser

logger = get_logger(__name__)


class HostParser(BaseParser):
    """Parses host-collectors/ directory of a support bundle."""

    def parse(self, bundle_root: Path, bundle_id: uuid.UUID) -> Iterator[Evidence]:
        host_dir = bundle_root / "host-collectors"
        if not host_dir.is_dir():
            logger.info("host_collectors_dir_missing", bundle_root=str(bundle_root))
            return

        for file_path in sorted(host_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix not in (".json", ".yaml", ".yml"):
                continue

            rel_path = str(file_path.relative_to(bundle_root))
            name = file_path.stem

            try:
                raw = file_path.read_text(errors="replace")
                if file_path.suffix == ".json":
                    data = json.loads(raw)
                else:
                    data = yaml.safe_load(raw)

                if not isinstance(data, (dict, list)):
                    data = {"raw": data}

                yield self._make_evidence(
                    bundle_id=bundle_id,
                    kind="HostInfo",
                    name=name,
                    raw_data=data if isinstance(data, dict) else {"items": data},
                    source_path=rel_path,
                )
            except Exception as exc:
                logger.warning(
                    "host_parse_error",
                    file=rel_path,
                    error=str(exc),
                )
