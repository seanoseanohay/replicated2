"""Tests for license enforcement middleware (Phase 2.6 — License Validation)."""

import uuid
from unittest.mock import patch

import pytest

from app.core.auth import create_access_token, hash_password
from app.models.user import User


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


async def _create_user(db_session, email, role="user", tenant_id="default") -> User:
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


@pytest.mark.asyncio
async def test_license_valid_allows_access(client, db_session):
    """When license is valid, protected routes work normally."""
    user = await _create_user(db_session, "licensed@example.com")

    with patch("app.main.is_license_valid", return_value=True):
        resp = await client.get("/api/v1/bundles", headers=_auth_headers(user))

    # May be 200 or 404 depending on data, but should NOT be 403
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_license_invalid_blocks_access(client, db_session):
    """When license is expired/invalid, protected routes return 403."""
    user = await _create_user(db_session, "expired@example.com")

    with patch("app.main.is_license_valid", return_value=False):
        resp = await client.get("/api/v1/bundles", headers=_auth_headers(user))

    assert resp.status_code == 403
    data = resp.json()
    assert data["code"] == "LICENSE_INVALID"
    assert "expired" in data["detail"].lower() or "invalid" in data["detail"].lower()


@pytest.mark.asyncio
async def test_license_check_allows_auth_routes(client, db_session):
    """Auth routes are allowlisted and work even with invalid license."""
    await _create_user(db_session, "authuser@example.com")

    with patch("app.main.is_license_valid", return_value=False):
        # Login should still work
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "authuser@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_license_check_allows_health_routes(client):
    """Health routes are allowlisted and work without license check."""
    with patch("app.main.is_license_valid", return_value=False):
        resp = await client.get("/health/live")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_license_check_allows_license_status_endpoint(client, db_session):
    """License status endpoint is allowlisted so the frontend can read it."""
    user = await _create_user(db_session, "licensecheck@example.com")

    with patch("app.main.is_license_valid", return_value=False):
        resp = await client.get("/api/v1/license/status", headers=_auth_headers(user))
        # Should return 200 with valid:false, not 403
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


@pytest.mark.asyncio
async def test_license_check_allows_updates_endpoint(client, db_session):
    """Updates endpoint is allowlisted so banner can still show license issues."""
    user = await _create_user(db_session, "updatescheck@example.com")

    with patch("app.main.is_license_valid", return_value=False):
        with patch("app.services.update_service._fetch_app_info", return_value=None):
            with patch(
                "app.services.update_service._fetch_available_updates", return_value=None
            ):
                resp = await client.get(
                    "/api/v1/updates/status", headers=_auth_headers(user)
                )
                assert resp.status_code == 200


@pytest.mark.asyncio
async def test_license_status_reflects_expiry(client, db_session):
    """License status endpoint returns valid=false when expired."""
    user = await _create_user(db_session, "expirecheck@example.com")

    expired_info = {
        "licenseType": "trial",
        "customerName": "Test Customer",
        "entitlements": {
            "expires_at": {
                "title": "Expiration",
                "value": "2020-01-01T00:00:00Z",
                "valueType": "String",
            }
        },
    }

    with patch("app.services.license_service._fetch_license_info", return_value=expired_info):
        resp = await client.get("/api/v1/license/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert data["expires_at"] == "2020-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_license_status_reflects_valid_license(client, db_session):
    """License status endpoint returns valid=true for active license."""
    user = await _create_user(db_session, "validlicense@example.com")

    valid_info = {
        "licenseType": "trial",
        "customerName": "Test Customer",
        "entitlements": {
            "expires_at": {
                "title": "Expiration",
                "value": "",  # empty = no expiry
                "valueType": "String",
            }
        },
    }

    with patch("app.services.license_service._fetch_license_info", return_value=valid_info):
        resp = await client.get("/api/v1/license/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["license_type"] == "trial"
