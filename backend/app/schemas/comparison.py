from pydantic import BaseModel


class FindingSummary(BaseModel):
    rule_id: str
    title: str
    severity: str
    status: str


class ComparisonResult(BaseModel):
    bundle_a_id: str
    bundle_a_filename: str
    bundle_b_id: str
    bundle_b_filename: str
    new_findings: list[FindingSummary]  # in B, not in A
    resolved_findings: list[FindingSummary]  # in A, not in B
    persisting_findings: list[FindingSummary]  # in both
    summary: dict  # {"new": N, "resolved": N, "persisting": N}
