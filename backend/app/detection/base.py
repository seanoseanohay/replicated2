import uuid
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.models.finding import Finding


class BaseRule(ABC):
    rule_id: str  # must be set on subclass
    title: str  # must be set on subclass
    severity: str  # must be set on subclass

    @abstractmethod
    def evaluate(self, bundle_id: uuid.UUID, session: Session) -> list[Finding]:
        """Query evidence for bundle_id, return list of Finding objects (not yet committed)."""
        ...

    def _make_finding(
        self, bundle_id: uuid.UUID, summary: str, evidence_ids=None
    ) -> Finding:
        return Finding(
            bundle_id=bundle_id,
            rule_id=self.rule_id,
            title=self.title,
            severity=self.severity,
            summary=summary,
            evidence_ids=[str(e) for e in (evidence_ids or [])],
            status="open",
        )
