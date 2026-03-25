"""
Integration tests for the findings API endpoints.
Uses the in-memory SQLite DB wired up in conftest.py.
"""

import uuid

import pytest
import pytest_asyncio

from app.core.auth import hash_password
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User
from tests.conftest import make_manager_headers


@pytest_asyncio.fixture()
async def bundle(db_session):
    b = Bundle(
        id=uuid.uuid4(),
        filename="test.tar.gz",
        original_filename="test.tar.gz",
        size_bytes=1024,
        status="ready",
        tenant_id="tenant-1",
        s3_key="test/test.tar.gz",
    )
    db_session.add(b)
    await db_session.flush()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture()
async def finding(db_session, bundle):
    f = Finding(
        id=uuid.uuid4(),
        bundle_id=bundle.id,
        rule_id="pod_crashloop",
        title="Pod CrashLoopBackOff Detected",
        severity="high",
        summary="Pod default/my-pod has containers in crash loop.",
        evidence_ids=[],
        status="open",
    )
    db_session.add(f)
    await db_session.flush()
    await db_session.refresh(f)
    return f


@pytest_asyncio.fixture()
async def eng_user(db_session):
    """Analyst user whose email is used to stamp reviewed_by."""
    u = User(
        id=uuid.uuid4(),
        email="eng@example.com",
        hashed_password=hash_password("password"),
        full_name="Test Engineer",
        role="analyst",
        tenant_id="tenant-1",
        is_active=True,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest.mark.asyncio
async def test_list_findings_empty(client, bundle):
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_findings_with_results(client, bundle, finding):
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["rule_id"] == "pod_crashloop"
    assert data["items"][0]["severity"] == "high"


@pytest.mark.asyncio
async def test_list_findings_severity_filter(client, bundle, finding):
    # Filter by matching severity
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings?severity=high",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Filter by non-matching severity
    resp2 = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings?severity=critical",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_patch_finding_status(client, bundle, finding, eng_user):
    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        headers=make_manager_headers(eng_user, tenant_id="tenant-1"),
        json={"status": "acknowledged"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "acknowledged"
    assert data["reviewed_by"] == "eng@example.com"
    assert data["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_patch_finding_reviewer_notes(client, bundle, finding):
    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        headers={"X-Tenant-ID": "tenant-1"},
        json={"reviewer_notes": "Investigated, pod is restarting due to OOM."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviewer_notes"] == "Investigated, pod is restarting due to OOM."


@pytest.mark.asyncio
async def test_patch_finding_tenant_isolation(client, bundle, finding):
    """Cannot update a finding belonging to a different tenant's bundle."""
    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        headers={"X-Tenant-ID": "other-tenant"},
        json={"status": "resolved"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_findings_tenant_isolation(client, bundle):
    """Different tenant gets empty list for the same bundle_id."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings",
        headers={"X-Tenant-ID": "other-tenant"},
    )
    assert resp.status_code == 404


# ── remediation download endpoint tests ─────────────────────────────────────

@pytest_asyncio.fixture()
async def finding_with_remediation(db_session, bundle):
    """A finding that has remediation data including a patch_yaml."""
    f = Finding(
        id=uuid.uuid4(),
        bundle_id=bundle.id,
        rule_id="oom_killed",
        title="Pod OOMKilled Detected",
        severity="high",
        summary="Pod production/oom-pod has OOMKilled containers: worker",
        evidence_ids=[],
        status="open",
        remediation={
            "what_happened": "Container worker in pod production/oom-pod was killed by the OOM killer.",
            "why_it_matters": "OOM kills cause abrupt process termination.",
            "how_to_fix": "Increase the memory limit for this container.",
            "patch_yaml": (
                "apiVersion: apps/v1\n"
                "kind: Deployment\n"
                "metadata:\n"
                "  name: oom\n"
                "  namespace: production\n"
                "spec:\n"
                "  template:\n"
                "    spec:\n"
                "      containers:\n"
                "      - name: worker\n"
                "        resources:\n"
                "          limits:\n"
                "            memory: \"512Mi\"\n"
            ),
            "patch_filename": "fix-oom-oom-pod-memory.yaml",
            "cli_commands": [
                "kubectl top pod oom-pod -n production",
            ],
        },
    )
    db_session.add(f)
    await db_session.flush()
    await db_session.refresh(f)
    return f


@pytest_asyncio.fixture()
async def finding_no_remediation(db_session, bundle):
    """A finding without any remediation data."""
    f = Finding(
        id=uuid.uuid4(),
        bundle_id=bundle.id,
        rule_id="pod_pending",
        title="Pods Stuck in Pending State",
        severity="medium",
        summary="1 pod(s) stuck in Pending state",
        evidence_ids=[],
        status="open",
        remediation=None,
    )
    db_session.add(f)
    await db_session.flush()
    await db_session.refresh(f)
    return f


@pytest.mark.asyncio
async def test_download_remediation_shell(client, bundle, finding_with_remediation):
    """Shell download returns a .sh file with correct Content-Disposition."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding_with_remediation.id}"
        f"/remediation/download?format=shell",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    assert "fix-oom-killed.sh" in resp.headers.get("content-disposition", "")
    body = resp.text
    # Should contain at least one of the CLI commands
    assert "kubectl" in body


@pytest.mark.asyncio
async def test_download_remediation_yaml(client, bundle, finding_with_remediation):
    """YAML download returns the patch with correct Content-Disposition."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding_with_remediation.id}"
        f"/remediation/download?format=yaml",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "fix-oom-oom-pod-memory.yaml" in cd
    assert "memory" in resp.text


@pytest.mark.asyncio
async def test_download_remediation_patch(client, bundle, finding_with_remediation):
    """Patch download returns a unified diff."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding_with_remediation.id}"
        f"/remediation/download?format=patch",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    # Unified diff starts with ---
    assert "---" in resp.text or "+++" in resp.text


@pytest.mark.asyncio
async def test_download_remediation_no_remediation(client, bundle, finding_no_remediation):
    """404 when finding has no remediation data."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding_no_remediation.id}"
        f"/remediation/download?format=shell",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_remediation_not_found(client, bundle):
    """404 when finding_id does not exist."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{uuid.uuid4()}"
        f"/remediation/download?format=shell",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_finding_read_includes_remediation(client, bundle, finding_with_remediation):
    """FindingRead schema includes the remediation field."""
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Find our specific finding
    target = next((i for i in items if i["id"] == str(finding_with_remediation.id)), None)
    assert target is not None
    assert "remediation" in target
    assert target["remediation"] is not None
    assert target["remediation"]["what_happened"] != ""
