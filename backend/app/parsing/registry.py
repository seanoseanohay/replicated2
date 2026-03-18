import uuid
from pathlib import Path

from app.core.logging import get_logger
from app.models.evidence import Evidence
from app.parsing.parsers.cluster_info import ClusterInfoParser
from app.parsing.parsers.cluster_resources import ClusterResourcesParser
from app.parsing.parsers.host import HostParser
from app.parsing.parsers.logs import LogsParser

logger = get_logger(__name__)

ALL_PARSERS = [
    ClusterInfoParser(),
    ClusterResourcesParser(),
    LogsParser(),
    HostParser(),
]


def run_all_parsers(bundle_root: Path, bundle_id: uuid.UUID) -> list[Evidence]:
    evidence: list[Evidence] = []
    for parser in ALL_PARSERS:
        try:
            for item in parser.parse(bundle_root, bundle_id):
                evidence.append(item)
        except Exception as exc:
            logger.warning(
                "parser_error",
                parser=type(parser).__name__,
                error=str(exc),
            )
    return evidence
