import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone

import redis

from app.ai.client import get_client
from app.ai.prompts import EXPLAIN_FINDING_SYSTEM, build_explain_prompt
from app.core.config import settings

log = logging.getLogger(__name__)

# Redis TTL for cached AI explanations (24 hours)
_CACHE_TTL = 86400


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _cache_key(finding, ev_dicts: list) -> str:
    """Stable hash over rule_id + severity + sorted evidence fingerprints."""
    ev_fingerprint = json.dumps(
        sorted(
            [{"kind": e.get("kind"), "namespace": e.get("namespace"), "name": e.get("name")}
             for e in ev_dicts],
            key=lambda e: (e.get("kind", ""), e.get("name", "")),
        ),
        sort_keys=True,
    )
    raw = f"{finding.rule_id}:{finding.severity}:{ev_fingerprint}"
    return f"ai:explain:{hashlib.sha256(raw.encode()).hexdigest()}"


def explain_finding(finding, evidence_list: list, session) -> tuple[str, str]:
    """
    Returns (explanation, remediation) strings.
    Checks Redis cache first; falls back to API call on miss.
    Raises ValueError if AI_ENABLED is False.
    """
    if not settings.AI_ENABLED:
        raise ValueError("AI is not enabled")

    ev_dicts = [
        {"kind": e.kind, "namespace": e.namespace, "name": e.name, "raw_data": e.raw_data}
        for e in evidence_list
    ]

    # Cache lookup
    try:
        r = _get_redis()
        key = _cache_key(finding, ev_dicts)
        cached = r.get(key)
        if cached:
            data = json.loads(cached)
            log.info(f"ai_explain_cache_hit rule_id={finding.rule_id}")
            return data["explanation"], data["remediation"]
    except Exception as exc:
        log.warning(f"ai_explain_cache_lookup_failed: {exc}")

    # API call
    client = get_client()
    prompt = build_explain_prompt(finding, ev_dicts)
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=2048,
        system=EXPLAIN_FINDING_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    full_text = response.content[0].text
    parts = re.split(
        r"\n(?:#+\s*)?(?:remediation|remediation steps|steps to resolve)[:\s]*\n",
        full_text,
        flags=re.IGNORECASE,
        maxsplit=1,
    )
    explanation = parts[0].strip()
    remediation = parts[1].strip() if len(parts) > 1 else ""

    # Cache store
    try:
        r = _get_redis()
        key = _cache_key(finding, ev_dicts)
        r.setex(key, _CACHE_TTL, json.dumps({"explanation": explanation, "remediation": remediation}))
    except Exception as exc:
        log.warning(f"ai_explain_cache_store_failed: {exc}")

    return explanation, remediation


def auto_explain_bundle(bundle_id: str, session) -> int:
    """
    Explain all un-explained findings for a bundle synchronously.
    Designed for use inside Celery tasks. Returns count explained.
    """
    if not settings.AI_ENABLED:
        return 0

    from app.models.evidence import Evidence
    from app.models.finding import Finding
    from app.models.finding_event import FindingEvent

    findings = (
        session.query(Finding)
        .filter(
            Finding.bundle_id == uuid.UUID(bundle_id),
            Finding.ai_explanation.is_(None),
        )
        .all()
    )

    explained = 0
    for finding in findings:
        try:
            evidence_list = []
            if finding.evidence_ids:
                evidence_uuids = [uuid.UUID(str(eid)) for eid in finding.evidence_ids[:5]]
                evidence_list = (
                    session.query(Evidence).filter(Evidence.id.in_(evidence_uuids)).all()
                )

            explanation, remediation = explain_finding(finding, evidence_list, session)
            finding.ai_explanation = explanation
            finding.ai_remediation = remediation
            finding.ai_explained_at = datetime.now(timezone.utc)
            finding.updated_at = datetime.now(timezone.utc)

            event = FindingEvent(finding_id=finding.id, actor="system", event_type="ai_explained")
            session.add(event)
            explained += 1
        except Exception as exc:
            log.warning(f"auto_explain skipped finding {finding.id}: {exc}")

    if explained:
        session.commit()

    return explained
