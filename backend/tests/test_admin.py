"""Tests for admin routes — user management and stats (Phase 7+)."""

import uuid

import pytest

from app.core.auth import create_access_token, hash_password
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(db_session, email, role="analyst", tenant_id="default") -> User:
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


def _headers(user: User) -> dict:
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
# Admin guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_requires_admin(client, db_session) -> None:
    """An analyst cannot access the admin user list."""
    analyst = await _create_user(db_session, "nonadmin@example.com", role="analyst")
    resp = await client.get("/api/v1/admin/users", headers=_headers(analyst))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_access_admin(client, db_session) -> None:
    """A manager (not admin) cannot access admin routes."""
    manager = await _create_user(
        db_session, "manager-noadmin@example.com", role="manager"
    )
    resp = await client.get("/api/v1/admin/users", headers=_headers(manager))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(client, db_session) -> None:
    """An admin user gets a 200 from /admin/users."""
    admin = await _create_user(db_session, "adminlist@example.com", role="admin")
    resp = await client.get("/api/v1/admin/users", headers=_headers(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Role update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_update_user_role(client, db_session) -> None:
    """Admin can promote an analyst to manager."""
    admin = await _create_user(db_session, "adminrole@example.com", role="admin")
    target = await _create_user(db_session, "targetrole@example.com", role="analyst")

    resp = await client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        json={"role": "manager"},
        headers=_headers(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_admin_role_update_invalid_role(client, db_session) -> None:
    """Invalid role value returns 400."""
    admin = await _create_user(db_session, "adminbadrole@example.com", role="admin")
    target = await _create_user(db_session, "targetbadrole@example.com", role="analyst")

    resp = await client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        json={"role": "superuser"},
        headers=_headers(admin),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_deactivate_user(client, db_session) -> None:
    """Admin can deactivate another user account."""
    admin = await _create_user(db_session, "adminstatus@example.com", role="admin")
    target = await _create_user(db_session, "targetstatus@example.com", role="analyst")

    resp = await client.patch(
        f"/api/v1/admin/users/{target.id}/status",
        json={"is_active": False},
        headers=_headers(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client, db_session) -> None:
    """Admin cannot deactivate their own account."""
    admin = await _create_user(db_session, "adminself@example.com", role="admin")

    resp = await client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        json={"is_active": False},
        headers=_headers(admin),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_stats_returns_counts(client, db_session) -> None:
    """Admin stats endpoint returns total_users, total_bundles, total_findings."""
    admin = await _create_user(db_session, "adminstats@example.com", role="admin")
    resp = await client.get("/api/v1/admin/stats", headers=_headers(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_bundles" in data
    assert "total_findings" in data
    assert "users_by_role" in data
    assert data["total_users"] >= 1  # at least the admin itself


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_returns_new_access_token(client, db_session) -> None:
    """POST /auth/refresh with a valid refresh token returns new tokens."""
    from app.core.auth import create_refresh_token

    user = await _create_user(db_session, "refresh@example.com", role="analyst")
    refresh_token = create_refresh_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "analyst"


@pytest.mark.asyncio
async def test_refresh_token_rejects_access_token(client, db_session) -> None:
    """Using an access token as a refresh token should return 401."""
    user = await _create_user(db_session, "refreshwrong@example.com", role="analyst")
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401
