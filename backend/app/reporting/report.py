SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def build_report(bundle, findings, evidence_counts: dict) -> dict:
    """Returns a structured dict report."""
    return {
        "bundle_id": str(bundle.id),
        "filename": bundle.original_filename,
        "analyzed_at": bundle.updated_at.isoformat(),
        "summary": {
            "total_findings": len(findings),
            "by_severity": {
                "critical": sum(1 for f in findings if f.severity == "critical"),
                "high": sum(1 for f in findings if f.severity == "high"),
                "medium": sum(1 for f in findings if f.severity == "medium"),
                "low": sum(1 for f in findings if f.severity == "low"),
                "info": sum(1 for f in findings if f.severity == "info"),
            },
            "by_status": {
                "open": sum(1 for f in findings if f.status == "open"),
                "acknowledged": sum(1 for f in findings if f.status == "acknowledged"),
                "resolved": sum(1 for f in findings if f.status == "resolved"),
            },
            "evidence_extracted": evidence_counts.get("total", 0),
        },
        "findings": [
            {
                "id": str(f.id),
                "rule_id": f.rule_id,
                "title": f.title,
                "severity": f.severity,
                "summary": f.summary,
                "status": f.status,
                "reviewer_notes": f.reviewer_notes,
                "ai_explanation": f.ai_explanation,
                "ai_remediation": f.ai_remediation,
            }
            for f in sorted(
                findings,
                key=lambda f: (
                    SEVERITY_ORDER.index(f.severity)
                    if f.severity in SEVERITY_ORDER
                    else len(SEVERITY_ORDER)
                ),
            )
        ],
    }


def build_markdown_report(bundle, findings, evidence_counts: dict) -> str:
    """Returns a markdown-formatted report string."""
    report = build_report(bundle, findings, evidence_counts)
    lines = [
        "# Bundle Analysis Report",
        "",
        f"**Bundle:** {report['filename']}  ",
        f"**Analyzed:** {report['analyzed_at']}  ",
        f"**Bundle ID:** {report['bundle_id']}",
        "",
        "## Summary",
        "",
        "| Severity | Count |",
        "|----------|-------|",
    ]
    for sev, count in report["summary"]["by_severity"].items():
        lines.append(f"| {sev.capitalize()} | {count} |")
    lines += [
        "",
        f"Total evidence extracted: {report['summary']['evidence_extracted']}",
        "",
    ]
    lines += ["## Findings", ""]
    for f in report["findings"]:
        lines += [
            f"### [{f['severity'].upper()}] {f['title']}",
            "",
            f"**Rule:** `{f['rule_id']}`  **Status:** {f['status']}",
            "",
            f"{f['summary']}",
            "",
        ]
        if f.get("ai_explanation"):
            lines += [f"**AI Explanation:** {f['ai_explanation']}", ""]
        if f.get("ai_remediation"):
            lines += [f"**Remediation:** {f['ai_remediation']}", ""]
        if f.get("reviewer_notes"):
            lines += [f"**Reviewer Notes:** {f['reviewer_notes']}", ""]
    return "\n".join(lines)
