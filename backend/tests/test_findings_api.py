"""
Integration tests for the findings API endpoints.
Uses the in-memory SQLite DB wired up in conftest.py.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

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
