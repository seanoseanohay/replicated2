import re

from app.ai.client import get_client
from app.ai.prompts import EXPLAIN_FINDING_SYSTEM, build_explain_prompt
from app.core.config import settings


def explain_finding(finding, evidence_list: list, session) -> tuple[str, str]:
    """
    Returns (explanation, remediation) strings.
    Raises ValueError if AI_ENABLED is False.
    Raises other exceptions if the API call fails.
    """
    if not settings.AI_ENABLED:
        raise ValueError("AI is not enabled")

    client = get_client()
    prompt = build_explain_prompt(finding, [
        {
            "kind": e.kind,
            "namespace": e.namespace,
            "name": e.name,
            "raw_data": e.raw_data,
        }
        for e in evidence_list
    ])

    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=2048,
        system=EXPLAIN_FINDING_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    full_text = response.content[0].text
    # Split on "remediation" heading if present, otherwise return full text as explanation
    parts = re.split(
        r"\n(?:#+\s*)?(?:remediation|remediation steps|steps to resolve)[:\s]*\n",
        full_text,
        flags=re.IGNORECASE,
        maxsplit=1,
    )
    explanation = parts[0].strip()
    remediation = parts[1].strip() if len(parts) > 1 else ""

    return explanation, remediation
