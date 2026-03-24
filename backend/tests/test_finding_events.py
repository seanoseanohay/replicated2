"""Tests for Phase 9 — Audit Trail & Finding Events."""

import uuid

import pytest
import pytest_asyncio

from app.core.auth import create_access_token, hash_password
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.finding_event import FindingEvent
from app.models.user import User


def _make_manager_token(user: User) -> dict:
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": user.tenant_id}


def _make_analyst_token(user: User) -> dict:
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": user.tenant_id}


@pytest_asyncio.fixture()
async def manager(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"mgr-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="manager",
        tenant_id="tenant-events",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def bundle_with_finding(db_session):
    bundle = Bundle(
        id=uuid.uuid4(),
        filename="test.tar.gz",
        original_filename="test.tar.gz",
        size_bytes=100,
        status="ready",
        tenant_id="tenant-events",
        s3_key="test/test.tar.gz",
    )
    db_session.add(bundle)
    await db_session.flush()

    finding = Finding(
        id=uuid.uuid4(),
        bundle_id=bundle.id,
        rule_id="test_rule",
        title="Test Finding",
        severity="high",
        summary="Test summary",
        evidence_ids=[],
        status="open",
    )
    db_session.add(finding)
    await db_session.flush()
    await db_session.refresh(bundle)
    await db_session.refresh(finding)
    return bundle, finding


@pytest.mark.asyncio
async def test_patch_finding_creates_status_changed_event(
    client, db_session, manager, bundle_with_finding
):
    bundle, finding = bundle_with_finding
    headers = _make_manager_token(manager)

    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        json={"status": "acknowledged"},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify event was created
    from sqlalchemy import select

    result = await db_session.execute(
        select(FindingEvent).where(
            FindingEvent.finding_id == finding.id,
            FindingEvent.event_type == "status_changed",
        )
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].old_value == "open"
    assert events[0].new_value == "acknowledged"
    assert events[0].actor == manager.email


@pytest.mark.asyncio
async def test_patch_finding_creates_note_added_event(
    client, db_session, manager, bundle_with_finding
):
    bundle, finding = bundle_with_finding
    headers = _make_manager_token(manager)

    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        json={"reviewer_notes": "Some notes here"},
        headers=headers,
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    result = await db_session.execute(
        select(FindingEvent).where(
            FindingEvent.finding_id == finding.id,
            FindingEvent.event_type == "note_added",
        )
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].new_value == "Some notes here"


@pytest.mark.asyncio
async def test_get_events_returns_correct_history(
    client, db_session, manager, bundle_with_finding
):
    bundle, finding = bundle_with_finding
    headers = _make_manager_token(manager)

    # Create multiple events via PATCH
    await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        json={"status": "acknowledged"},
        headers=headers,
    )
    await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        json={"reviewer_notes": "Investigating"},
        headers=headers,
    )

    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/events",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    event_types = [e["event_type"] for e in data]
    assert "status_changed" in event_types
    assert "note_added" in event_types


@pytest.mark.asyncio
async def test_events_tenant_isolation(client, db_session, bundle_with_finding):
    """Events should not be accessible from a different tenant."""
    bundle, finding = bundle_with_finding

    # Use headers for a different tenant
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/events",
        headers={"X-Tenant-ID": "other-tenant"},
    )
    assert resp.status_code == 404
