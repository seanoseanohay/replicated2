"""Tests for Phase 7 — Authentication & Roles."""

import uuid

import pytest

from app.core.auth import create_access_token, hash_password
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(
    db_session, email="analyst@example.com", role="analyst", tenant_id="default"
):
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("password123"),
        role=role,
        tenant_id=tenant_id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_returns_tokens(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "securepassword"},
        headers={"X-Tenant-ID": "default"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "analyst"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dup@example.com", "password": "securepassword"}
    resp1 = await client.post(
        "/api/v1/auth/register", json=payload, headers={"X-Tenant-ID": "default"}
    )
    assert resp1.status_code == 201
    resp2 = await client.post(
        "/api/v1/auth/register", json=payload, headers={"X-Tenant-ID": "default"}
    )
    assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_correct_credentials(client, db_session):
    await _create_user(db_session, email="logintest@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "logintest@example.com", "password": "password123"},
        headers={"X-Tenant-ID": "default"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, db_session):
    await _create_user(db_session, email="wrongpw@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "wrongpassword"},
        headers={"X-Tenant-ID": "default"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_with_valid_token(client, db_session):
    user = await _create_user(db_session, email="me@example.com")
    resp = await client.get("/api/v1/auth/me", headers=_auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert data["role"] == "analyst"


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Role guards on findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyst_cannot_resolve_finding(client, db_session):
    """An analyst trying to resolve a finding should get 403."""
    from app.models.bundle import Bundle
    from app.models.finding import Finding

    # Create bundle + finding
    bundle = Bundle(
        id=uuid.uuid4(),
        filename="test.tar.gz",
        original_filename="test.tar.gz",
        size_bytes=1024,
        status="ready",
        tenant_id="default",
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

    analyst = await _create_user(
        db_session, email="analyst_role@example.com", role="analyst"
    )

    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        json={"status": "resolved"},
        headers={**_auth_headers(analyst), "X-Tenant-ID": "default"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_resolve_finding(client, db_session):
    """A manager can resolve a finding."""
    from app.models.bundle import Bundle
    from app.models.finding import Finding

    bundle = Bundle(
        id=uuid.uuid4(),
        filename="test2.tar.gz",
        original_filename="test2.tar.gz",
        size_bytes=1024,
        status="ready",
        tenant_id="default",
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

    manager = await _create_user(
        db_session, email="manager_role@example.com", role="manager"
    )

    resp = await client.patch(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}",
        json={"status": "resolved"},
        headers={**_auth_headers(manager), "X-Tenant-ID": "default"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backward_compat_x_tenant_id_header(client):
    """Requests with only X-Tenant-ID header (no JWT) should still work for read endpoints."""
    resp = await client.get(
        "/api/v1/bundles",
        headers={"X-Tenant-ID": "legacy-tenant"},
    )
    # Should succeed (200) or at least not fail with auth error
    assert resp.status_code == 200
