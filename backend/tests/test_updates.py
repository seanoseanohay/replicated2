"""Tests for GET /api/v1/updates/status (Phase 2.6 — Update Available Banner)."""

import uuid
from unittest.mock import patch

import pytest

from app.core.auth import create_access_token, hash_password
from app.models.user import User
from app.services.update_service import clear_cache


@pytest.fixture(autouse=True)
def _clear_update_cache():
    """Reset the update-service cache before every test to avoid cross-test leaks."""
    clear_cache()


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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_no_update_available(client, db_session):
    """When app info and updates match, no update is advertised."""
    user = await _create_user(db_session, "updateuser@example.com")

    app_info = {"versionLabel": "1.0.0", "appVersion": "1.0.0", "license": {"isValid": True}}
    updates = [{"versionLabel": "1.0.0", "createdAt": "2024-01-01T00:00:00Z", "releaseNotes": ""}]

    with patch("app.services.update_service._fetch_app_info", return_value=app_info):
        with patch("app.services.update_service._fetch_available_updates", return_value=updates):
            resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["current_version"] == "1.0.0"
    assert data["version"] == "1.0.0"
    assert data["license_valid"] is True


@pytest.mark.asyncio
async def test_update_status_new_version_available(client, db_session):
    """When a newer version exists, the banner signals availability."""
    user = await _create_user(db_session, "updateavail@example.com")

    app_info = {"versionLabel": "1.0.0", "license": {"isValid": True}}
    updates = [
        {"versionLabel": "1.1.0", "createdAt": "2024-02-01T00:00:00Z", "releaseNotes": "Bug fixes"}
    ]

    with patch("app.services.update_service._fetch_app_info", return_value=app_info):
        with patch("app.services.update_service._fetch_available_updates", return_value=updates):
            resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["current_version"] == "1.0.0"
    assert data["version"] == "1.1.0"
    assert data["notes"] == "Bug fixes"
    assert data["license_valid"] is True


@pytest.mark.asyncio
async def test_update_status_license_invalid(client, db_session):
    """An invalid license is surfaced so the banner can warn."""
    user = await _create_user(db_session, "badlicense@example.com")

    app_info = {"versionLabel": "1.0.0", "license": {"isValid": False}}
    updates = []

    with patch("app.services.update_service._fetch_app_info", return_value=app_info):
        with patch("app.services.update_service._fetch_available_updates", return_value=updates):
            with patch("app.services.update_service._is_license_valid", return_value=False):
                resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["license_valid"] is False
    assert data["available"] is False


@pytest.mark.asyncio
async def test_update_status_no_app_info(client, db_session):
    """When the SDK is unreachable (local dev), gracefully report nothing available."""
    user = await _create_user(db_session, "noinfo@example.com")

    with patch("app.services.update_service._fetch_app_info", return_value=None):
        with patch("app.services.update_service._fetch_available_updates", return_value=None):
            resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["version"] is None
    assert data["current_version"] is None
    assert data["license_valid"] is None


@pytest.mark.asyncio
async def test_update_status_no_updates_list(client, db_session):
    """App info present but no updates list means nothing available."""
    user = await _create_user(db_session, "noupdates@example.com")

    app_info = {"versionLabel": "1.0.0", "license": {"isValid": True}}

    with patch("app.services.update_service._fetch_app_info", return_value=app_info):
        with patch("app.services.update_service._fetch_available_updates", return_value=None):
            resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["current_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_update_status_empty_updates_list(client, db_session):
    """Empty updates list means nothing available."""
    user = await _create_user(db_session, "emptyupdates@example.com")

    app_info = {"versionLabel": "1.0.0", "license": {"isValid": True}}

    with patch("app.services.update_service._fetch_app_info", return_value=app_info):
        with patch("app.services.update_service._fetch_available_updates", return_value=[]):
            resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False


@pytest.mark.asyncio
async def test_update_status_picks_newest_update(client, db_session):
    """When multiple updates exist, the newest (by createdAt) is chosen."""
    user = await _create_user(db_session, "multupdates@example.com")

    app_info = {"versionLabel": "1.0.0", "license": {"isValid": True}}
    updates = [
        {"versionLabel": "1.0.1", "createdAt": "2024-01-15T00:00:00Z", "releaseNotes": "Hotfix"},
        {"versionLabel": "1.2.0", "createdAt": "2024-03-01T00:00:00Z", "releaseNotes": "Major"},
        {"versionLabel": "1.1.0", "createdAt": "2024-02-01T00:00:00Z", "releaseNotes": "Minor"},
    ]

    with patch("app.services.update_service._fetch_app_info", return_value=app_info):
        with patch("app.services.update_service._fetch_available_updates", return_value=updates):
            resp = await client.get("/api/v1/updates/status", headers=_auth_headers(user))

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["version"] == "1.2.0"
    assert data["notes"] == "Major"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_requires_auth(client):
    """No token should return 401 (UpdateBanner is inside ProtectedLayout)."""
    resp = await client.get("/api/v1/updates/status")
    assert resp.status_code == 401
