"""
Tests for report generation (unit) and report API endpoints (integration).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from app.models.bundle import Bundle
from app.models.finding import Finding
from app.reporting.report import build_markdown_report, build_report


# ── Unit tests for build_report / build_markdown_report ──────────────────────

def _make_mock_bundle():
    b = MagicMock()
    b.id = uuid.uuid4()
    b.original_filename = "my-bundle.tar.gz"
    b.updated_at = datetime(2026, 3, 17, 12, 0, 0, tzinfo=timezone.utc)
    return b


def _make_mock_finding(severity="high", status="open"):
    f = MagicMock()
    f.id = uuid.uuid4()
    f.rule_id = "pod_crashloop"
    f.title = "Pod CrashLoopBackOff Detected"
    f.severity = severity
    f.summary = "Pod default/my-pod is crashing."
    f.status = status
    f.reviewer_notes = None
    f.ai_explanation = None
    f.ai_remediation = None
    return f


def test_build_report_shape():
    bundle = _make_mock_bundle()
    findings = [_make_mock_finding("high"), _make_mock_finding("critical")]
    evidence_counts = {"total": 42}

    report = build_report(bundle, findings, evidence_counts)

    assert report["bundle_id"] == str(bundle.id)
    assert report["filename"] == "my-bundle.tar.gz"
    assert report["summary"]["total_findings"] == 2
    assert report["summary"]["by_severity"]["high"] == 1
    assert report["summary"]["by_severity"]["critical"] == 1
    assert report["summary"]["evidence_extracted"] == 42
    assert len(report["findings"]) == 2
    # Critical should appear before high (sorted by severity)
    assert report["findings"][0]["severity"] == "critical"
    assert report["findings"][1]["severity"] == "high"


def test_build_report_empty_findings():
    bundle = _make_mock_bundle()
    report = build_report(bundle, [], {"total": 0})
    assert report["summary"]["total_findings"] == 0
    assert report["findings"] == []


def test_build_markdown_report_contains_bundle_name():
    bundle = _make_mock_bundle()
    findings = [_make_mock_finding()]
    md = build_markdown_report(bundle, findings, {"total": 10})

    assert "# Bundle Analysis Report" in md
    assert "my-bundle.tar.gz" in md
    assert "Pod CrashLoopBackOff Detected" in md
    assert "HIGH" in md
    assert "Total evidence extracted: 10" in md


def test_build_markdown_report_ai_explanation():
    bundle = _make_mock_bundle()
    f = _make_mock_finding()
    f.ai_explanation = "The pod is crashing due to a missing config map."
    f.ai_remediation = "Create the missing config map."
    md = build_markdown_report(bundle, [f], {"total": 5})

    assert "The pod is crashing due to a missing config map." in md
    assert "Create the missing config map." in md


def test_build_markdown_report_reviewer_notes():
    bundle = _make_mock_bundle()
    f = _make_mock_finding(status="resolved")
    f.reviewer_notes = "Fixed by adding config map."
    md = build_markdown_report(bundle, [f], {"total": 0})

    assert "Fixed by adding config map." in md


# ── Integration tests for report API endpoints ────────────────────────────────

@pytest_asyncio.fixture()
async def bundle_with_finding(db_session):
    b = Bundle(
        id=uuid.uuid4(),
        filename="report-test.tar.gz",
        original_filename="report-test.tar.gz",
        size_bytes=2048,
        status="ready",
        tenant_id="tenant-report",
        s3_key="test/report-test.tar.gz",
    )
    db_session.add(b)
    await db_session.flush()

    f = Finding(
        id=uuid.uuid4(),
        bundle_id=b.id,
        rule_id="node_not_ready",
        title="Node Not Ready",
        severity="critical",
        summary="Node node-1 is not ready.",
        evidence_ids=[],
        status="open",
    )
    db_session.add(f)
    await db_session.flush()
    await db_session.refresh(b)
    return b


@pytest.mark.asyncio
async def test_get_report_json(client, bundle_with_finding):
    resp = await client.get(
        f"/api/v1/bundles/{bundle_with_finding.id}/report",
        headers={"X-Tenant-ID": "tenant-report"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bundle_id"] == str(bundle_with_finding.id)
    assert "summary" in data
    assert "findings" in data
    assert data["summary"]["total_findings"] == 1
    assert data["findings"][0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_get_report_markdown(client, bundle_with_finding):
    resp = await client.get(
        f"/api/v1/bundles/{bundle_with_finding.id}/report.md",
        headers={"X-Tenant-ID": "tenant-report"},
    )
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "# Bundle Analysis Report" in resp.text
    assert "Node Not Ready" in resp.text
    assert f"report-{bundle_with_finding.id}.md" in resp.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_get_report_tenant_isolation(client, bundle_with_finding):
    resp = await client.get(
        f"/api/v1/bundles/{bundle_with_finding.id}/report",
        headers={"X-Tenant-ID": "wrong-tenant"},
    )
    assert resp.status_code == 404
