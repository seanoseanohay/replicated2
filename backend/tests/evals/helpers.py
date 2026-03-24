"""
Shared utilities for LLM eval tests.
"""

import json
import types

from app.ai.client import get_client
from app.core.config import settings


# ---------------------------------------------------------------------------
# Lightweight stand-ins for ORM objects
# ---------------------------------------------------------------------------


def make_finding(title: str, severity: str, summary: str, rule_id: str = "eval_rule"):
    """Create a minimal Finding-like namespace for eval testing."""
    return types.SimpleNamespace(
        title=title,
        severity=severity,
        summary=summary,
        rule_id=rule_id,
    )


def make_evidence(kind: str, name: str, namespace: str, raw_data: dict):
    """Create a minimal Evidence-like namespace for eval testing."""
    return types.SimpleNamespace(
        kind=kind,
        name=name,
        namespace=namespace,
        raw_data=raw_data,
    )


# ---------------------------------------------------------------------------
# Structural / keyword assertions
# ---------------------------------------------------------------------------


def assert_has_sections(
    explanation: str, remediation: str, min_words: int = 15
) -> None:
    """Both explanation and remediation must be non-empty and substantive."""
    assert explanation and len(explanation.split()) >= min_words, (
        f"Explanation too short or empty ({len(explanation.split()) if explanation else 0} words, "
        f"expected >= {min_words})"
    )
    assert remediation and len(remediation.strip()) > 0, "Remediation section is empty"


def assert_keywords(text: str, keywords: list[str], min_matches: int = 1) -> None:
    """Assert that at least *min_matches* of *keywords* appear (case-insensitive)."""
    lower = text.lower()
    matched = [kw for kw in keywords if kw.lower() in lower]
    assert len(matched) >= min_matches, (
        f"Expected >= {min_matches} of {keywords!r} in response; found only {matched!r}"
    )


def assert_no_text(text: str, forbidden: list[str]) -> None:
    """Assert that none of the *forbidden* phrases appear (case-insensitive)."""
    lower = text.lower()
    found = [f for f in forbidden if f.lower() in lower]
    assert not found, f"Response contained forbidden content: {found!r}"


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------


def judge_response(
    finding_context: str,
    full_response: str,
    criteria: str,
    min_score: int = 3,
) -> None:
    """
    Use Claude itself as a judge to evaluate response quality against *criteria*.
    Asserts that the returned score is >= *min_score* (1–5 scale).
    Only called for complex / multi-step tests where mechanical assertions
    are insufficient.
    """
    client = get_client()
    judge_prompt = (
        "You are evaluating an AI assistant's response to a Kubernetes support bundle finding.\n\n"
        f"FINDING CONTEXT:\n{finding_context}\n\n"
        f"AI RESPONSE:\n{full_response}\n\n"
        f"EVALUATION CRITERIA:\n{criteria}\n\n"
        "Rate the response 1–5:\n"
        "  5 = Excellent: fully addresses the criteria with accuracy and specificity\n"
        "  4 = Good: mostly addresses the criteria with minor gaps\n"
        "  3 = Acceptable: partially addresses the criteria\n"
        "  2 = Poor: mostly fails the criteria\n"
        "  1 = Unacceptable: completely fails or is harmful\n\n"
        'Respond ONLY with valid JSON: {"score": <integer 1-5>, "reasoning": "<brief explanation>"}'
    )
    resp = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    result = json.loads(resp.content[0].text)
    score = result["score"]
    reasoning = result.get("reasoning", "")
    assert score >= min_score, (
        f"Judge score {score}/5 is below minimum {min_score}/5.\n"
        f"Reasoning: {reasoning}\n"
        f"Full response (first 600 chars):\n{full_response[:600]}"
    )
