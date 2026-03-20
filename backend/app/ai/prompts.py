import json

EXPLAIN_FINDING_SYSTEM = """You are an expert Kubernetes support engineer analyzing diagnostic findings from support bundles.
Your job is to explain findings clearly and provide actionable remediation steps.
Be concise, technical, and specific. Focus on what a support engineer needs to know to resolve the issue."""


def build_explain_prompt(finding, evidence_samples: list[dict]) -> str:
    evidence_text = "\n\n".join([
        f"Evidence [{e.get('kind', 'unknown')}] {e.get('namespace', '')}/{e.get('name', '')}:\n"
        f"{json.dumps(e.get('raw_data', {}), indent=2)[:2000]}"
        for e in evidence_samples[:3]
    ])
    return f"""Finding: {finding.title}
Severity: {finding.severity}
Summary: {finding.summary}

Supporting Evidence:
{evidence_text}

Please provide your response in exactly this format:

A clear explanation of what this finding means, why it matters, and the most likely root causes.

## Remediation Steps

Numbered, specific steps a support engineer can follow to resolve the issue.

Keep your response focused and actionable."""
