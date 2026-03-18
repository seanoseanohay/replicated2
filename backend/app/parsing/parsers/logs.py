import uuid
from pathlib import Path
from typing import Iterator

from app.core.logging import get_logger
from app.models.evidence import Evidence
from app.parsing.parsers.base import BaseParser

logger = get_logger(__name__)

MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_TAIL_LINES = 500


class LogsParser(BaseParser):
    """Parses pod-logs/ or logs/ directories of a support bundle."""

    def parse(self, bundle_root: Path, bundle_id: uuid.UUID) -> Iterator[Evidence]:
        # Try pod-logs/ first, then logs/
        log_dir = bundle_root / "pod-logs"
        if not log_dir.is_dir():
            log_dir = bundle_root / "logs"
        if not log_dir.is_dir():
            logger.info("logs_dir_missing", bundle_root=str(bundle_root))
            return

        for log_file in sorted(log_dir.rglob("*.log")):
            if not log_file.is_file():
                continue

            rel_path = str(log_file.relative_to(bundle_root))

            try:
                file_size = log_file.stat().st_size
                if file_size > MAX_LOG_SIZE_BYTES:
                    logger.info(
                        "log_file_skipped_too_large",
                        path=rel_path,
                        size=file_size,
                    )
                    continue

                text = log_file.read_text(errors="replace")
                all_lines = text.splitlines()
                total_lines = len(all_lines)
                tail_lines = all_lines[-MAX_TAIL_LINES:]

                # Infer namespace/pod/container from path structure:
                # <log_dir>/<namespace>/<pod>/<container>.log
                # or just <log_dir>/<pod>/<container>.log
                parts = log_file.relative_to(log_dir).parts
                namespace = None
                if len(parts) >= 3:
                    namespace = parts[0]
                    container = log_file.stem
                elif len(parts) == 2:
                    container = log_file.stem
                else:
                    container = log_file.stem

                yield self._make_evidence(
                    bundle_id=bundle_id,
                    kind="Log",
                    name=container,
                    namespace=namespace,
                    raw_data={
                        "lines": tail_lines,
                        "total_lines": total_lines,
                        "path": rel_path,
                    },
                    source_path=rel_path,
                )
            except Exception as exc:
                logger.warning(
                    "log_parse_error",
                    file=rel_path,
                    error=str(exc),
                )
