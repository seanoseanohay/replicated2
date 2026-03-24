import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from app.models.evidence import Evidence


class BaseParser(ABC):
    """Yields Evidence instances from an extracted bundle directory."""

    @abstractmethod
    def parse(self, bundle_root: Path, bundle_id: uuid.UUID) -> Iterator[Evidence]: ...

    def _make_evidence(
        self,
        bundle_id: uuid.UUID,
        kind: str,
        name: str,
        raw_data: dict,
        namespace: str | None = None,
        source_path: str = "",
    ) -> Evidence:
        return Evidence(
            bundle_id=bundle_id,
            kind=kind,
            namespace=namespace,
            name=name,
            source_path=source_path,
            raw_data=raw_data,
        )
