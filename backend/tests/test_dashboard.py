"""
Tests for GET /api/v1/dashboard endpoint.
"""
import uuid

import pytest
import pytest_asyncio

from app.core.auth import create_access_token, hash_password
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User


def _make_headers(user: User) -> dict:
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role, "tenant_id": user.tenant_id}
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": user.tenant_id}


@pytest_asyncio.fixture()
async def tenant_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"dash-{uuid.uuid4().hex[:8]}@test.example.com",
        hashed_password=hash_password("testpass1"),
        role="analyst",
        tenant_id="tenant-dash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def other_tenant_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.example.com",
        hashed_password=hash_password("testpass1"),
        role="analyst",
        tenant_id="tenant-other",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def ready_bundle(db_session, tenant_user):
    b = Bundle(
        id=uuid.uuid4(),
        filename="bundle1.tar.gz",
        original_filename="bundle1.tar.gz",
        size_bytes=1024,
        status="ready",
        tenant_id=tenant_user.tenant_id,
        s3_key="test/bundle1.tar.gz",
    )
    db_session.add(b)
    await db_session.flush()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture()
async def other_tenant_bundle(db_session, other_tenant_user):
    b = Bundle(
        id=uuid.uuid4(),
        filename="other-bundle.tar.gz",
        original_filename="other-bundle.tar.gz",
        size_bytes=512,
        status="ready",
        tenant_id=other_tenant_user.tenant_id,
        s3_key="test/other-bundle.tar.gz",
    )
    db_session.add(b)
    await db_session.flush()
    await db_session.refresh(b)
    return b


@pytest.mark.asyncio
async def test_dashboard_returns_200_correct_shape(client, tenant_user, ready_bundle):
    """GET /dashboard returns 200 with the expected top-level keys."""
    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_bundles" in data
    assert "bundles_ready" in data
    assert "bundles_processing" in data
    assert "bundles_error" in data
    assert "total_open_findings" in data
    assert "findings_by_severity" in data
    assert "most_recent_critical" in data
    assert "bundles" in data
    assert isinstance(data["bundles"], list)


@pytest.mark.asyncio
async def test_health_score_100_no_findings(client, tenant_user, ready_bundle):
    """A bundle with no findings should have health_score of 100 and color 'green'."""
    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    bundle_entry = next(
        (b for b in data["bundles"] if b["bundle_id"] == str(ready_bundle.id)), None
    )
    assert bundle_entry is not None
    assert bundle_entry["health_score"] == 100
    assert bundle_entry["health_color"] == "green"
    assert bundle_entry["open_findings"] == 0


@pytest.mark.asyncio
async def test_health_score_decreases_with_critical_findings(
    client, db_session, tenant_user, ready_bundle
):
    """Critical findings should reduce health score by 30 each."""
    # Add 2 critical findings → 100 - 30 - 30 = 40 → "orange"
    for _ in range(2):
        f = Finding(
            id=uuid.uuid4(),
            bundle_id=ready_bundle.id,
            rule_id="node_not_ready",
            title="Node Not Ready",
            severity="critical",
            summary="A node is not ready.",
            evidence_ids=[],
            status="open",
        )
        db_session.add(f)
    await db_session.flush()

    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    bundle_entry = next(
        (b for b in data["bundles"] if b["bundle_id"] == str(ready_bundle.id)), None
    )
    assert bundle_entry is not None
    assert bundle_entry["health_score"] == 40
    assert bundle_entry["health_color"] == "orange"
    assert bundle_entry["open_findings"] == 2
    assert bundle_entry["findings_by_severity"]["critical"] == 2


@pytest.mark.asyncio
async def test_most_recent_critical_populated(client, db_session, tenant_user, ready_bundle):
    """most_recent_critical should include critical open findings."""
    f = Finding(
        id=uuid.uuid4(),
        bundle_id=ready_bundle.id,
        rule_id="node_not_ready",
        title="Critical Issue",
        severity="critical",
        summary="Something critical happened.",
        evidence_ids=[],
        status="open",
    )
    db_session.add(f)
    await db_session.flush()

    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["most_recent_critical"]) >= 1
    entry = data["most_recent_critical"][0]
    assert "bundle_id" in entry
    assert "filename" in entry
    assert "finding_title" in entry
    assert "rule_id" in entry
    assert "created_at" in entry
    assert entry["finding_title"] == "Critical Issue"


@pytest.mark.asyncio
async def test_most_recent_critical_capped_at_5(client, db_session, tenant_user, ready_bundle):
    """most_recent_critical should never return more than 5 entries."""
    for i in range(8):
        f = Finding(
            id=uuid.uuid4(),
            bundle_id=ready_bundle.id,
            rule_id=f"rule_{i}",
            title=f"Critical Issue {i}",
            severity="critical",
            summary="Critical.",
            evidence_ids=[],
            status="open",
        )
        db_session.add(f)
    await db_session.flush()

    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["most_recent_critical"]) <= 5


@pytest.mark.asyncio
async def test_resolved_findings_excluded_from_score(client, db_session, tenant_user, ready_bundle):
    """Resolved findings should not affect the health score."""
    f = Finding(
        id=uuid.uuid4(),
        bundle_id=ready_bundle.id,
        rule_id="node_not_ready",
        title="Resolved Critical",
        severity="critical",
        summary="Already fixed.",
        evidence_ids=[],
        status="resolved",
    )
    db_session.add(f)
    await db_session.flush()

    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    bundle_entry = next(
        (b for b in data["bundles"] if b["bundle_id"] == str(ready_bundle.id)), None
    )
    assert bundle_entry is not None
    assert bundle_entry["health_score"] == 100
    assert bundle_entry["open_findings"] == 0


@pytest.mark.asyncio
async def test_tenant_isolation(
    client, db_session, tenant_user, other_tenant_user, ready_bundle, other_tenant_bundle
):
    """Each tenant should only see their own bundles."""
    # Tenant A sees their bundle
    resp_a = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    bundle_ids_a = {b["bundle_id"] for b in data_a["bundles"]}
    assert str(ready_bundle.id) in bundle_ids_a
    assert str(other_tenant_bundle.id) not in bundle_ids_a

    # Tenant B sees their bundle
    resp_b = await client.get("/api/v1/dashboard", headers=_make_headers(other_tenant_user))
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    bundle_ids_b = {b["bundle_id"] for b in data_b["bundles"]}
    assert str(other_tenant_bundle.id) in bundle_ids_b
    assert str(ready_bundle.id) not in bundle_ids_b


@pytest.mark.asyncio
async def test_aggregate_stats_counts(client, db_session, tenant_user, ready_bundle):
    """Aggregate stat counts should reflect actual data."""
    f1 = Finding(
        id=uuid.uuid4(),
        bundle_id=ready_bundle.id,
        rule_id="rule_high",
        title="High Finding",
        severity="high",
        summary="High severity.",
        evidence_ids=[],
        status="open",
    )
    f2 = Finding(
        id=uuid.uuid4(),
        bundle_id=ready_bundle.id,
        rule_id="rule_medium",
        title="Medium Finding",
        severity="medium",
        summary="Medium severity.",
        evidence_ids=[],
        status="open",
    )
    db_session.add(f1)
    db_session.add(f2)
    await db_session.flush()

    resp = await client.get("/api/v1/dashboard", headers=_make_headers(tenant_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_open_findings"] >= 2
    assert data["findings_by_severity"]["high"] >= 1
    assert data["findings_by_severity"]["medium"] >= 1
    assert data["total_bundles"] >= 1
    assert data["bundles_ready"] >= 1
