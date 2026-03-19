"""Tests for Phase 12 — Bundle Comparison."""
import uuid

import pytest
import pytest_asyncio

from app.core.auth import create_access_token, hash_password
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User


TENANT = "compare-tenant"


def _headers(tenant: str = TENANT) -> dict:
    return {"X-Tenant-ID": tenant}


def _make_bundle(tenant_id: str = TENANT) -> Bundle:
    return Bundle(
        id=uuid.uuid4(),
        filename=f"compare-{uuid.uuid4().hex[:6]}.tar.gz",
        original_filename=f"compare-{uuid.uuid4().hex[:6]}.tar.gz",
        size_bytes=100,
        status="ready",
        tenant_id=tenant_id,
        s3_key=f"compare/{uuid.uuid4().hex}.tar.gz",
    )


def _make_finding(bundle_id: uuid.UUID, rule_id: str, severity: str = "high") -> Finding:
    return Finding(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        rule_id=rule_id,
        title=f"Finding {rule_id}",
        severity=severity,
        summary="Summary",
        evidence_ids=[],
        status="open",
    )


@pytest_asyncio.fixture()
async def two_identical_bundles(db_session):
    b1 = _make_bundle()
    b2 = _make_bundle()
    db_session.add(b1)
    db_session.add(b2)
    await db_session.flush()

    # Same rules in both
    for rule_id in ["rule_a", "rule_b", "rule_c"]:
        db_session.add(_make_finding(b1.id, rule_id))
        db_session.add(_make_finding(b2.id, rule_id))

    await db_session.flush()
    await db_session.refresh(b1)
    await db_session.refresh(b2)
    return b1, b2


@pytest_asyncio.fixture()
async def empty_and_populated(db_session):
    b_empty = _make_bundle()
    b_full = _make_bundle()
    db_session.add(b_empty)
    db_session.add(b_full)
    await db_session.flush()

    for rule_id in ["rule_x", "rule_y"]:
        db_session.add(_make_finding(b_full.id, rule_id))

    await db_session.flush()
    await db_session.refresh(b_empty)
    await db_session.refresh(b_full)
    return b_empty, b_full


@pytest.mark.asyncio
async def test_compare_identical_bundles_all_persisting(client, two_identical_bundles):
    b1, b2 = two_identical_bundles
    resp = await client.get(
        f"/api/v1/bundles/compare?bundle_a={b1.id}&bundle_b={b2.id}",
        headers=_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["new"] == 0
    assert data["summary"]["resolved"] == 0
    assert data["summary"]["persisting"] == 3
    assert len(data["new_findings"]) == 0
    assert len(data["resolved_findings"]) == 0
    assert len(data["persisting_findings"]) == 3


@pytest.mark.asyncio
async def test_compare_empty_vs_populated_all_new(client, empty_and_populated):
    b_empty, b_full = empty_and_populated
    resp = await client.get(
        f"/api/v1/bundles/compare?bundle_a={b_empty.id}&bundle_b={b_full.id}",
        headers=_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["new"] == 2
    assert data["summary"]["resolved"] == 0
    assert data["summary"]["persisting"] == 0


@pytest.mark.asyncio
async def test_compare_populated_vs_empty_all_resolved(client, empty_and_populated):
    b_empty, b_full = empty_and_populated
    resp = await client.get(
        f"/api/v1/bundles/compare?bundle_a={b_full.id}&bundle_b={b_empty.id}",
        headers=_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["new"] == 0
    assert data["summary"]["resolved"] == 2
    assert data["summary"]["persisting"] == 0


@pytest.mark.asyncio
async def test_compare_tenant_isolation(client, two_identical_bundles):
    b1, b2 = two_identical_bundles
    # Use a different tenant — both bundles should not be found
    resp = await client.get(
        f"/api/v1/bundles/compare?bundle_a={b1.id}&bundle_b={b2.id}",
        headers={"X-Tenant-ID": "other-tenant"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_cross_tenant_bundle_b_not_found(client, db_session):
    """Bundle B in a different tenant than Bundle A should 404."""
    b1 = _make_bundle(tenant_id=TENANT)
    b2 = _make_bundle(tenant_id="other-tenant-compare")
    db_session.add(b1)
    db_session.add(b2)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/bundles/compare?bundle_a={b1.id}&bundle_b={b2.id}",
        headers=_headers(TENANT),
    )
    assert resp.status_code == 404
