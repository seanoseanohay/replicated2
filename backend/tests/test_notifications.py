"""Tests for Phase 10 — Notifications."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.core.auth import create_access_token, hash_password
from app.models.user import User


def _token(user: User) -> dict:
    tok = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )
    return {"Authorization": f"Bearer {tok}", "X-Tenant-ID": user.tenant_id}


@pytest_asyncio.fixture()
async def admin_notif(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"admin-notif-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="admin",
        tenant_id="notif-tenant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def user_notif(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"user-notif-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="user",
        tenant_id="notif-tenant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_config_forbidden_for_user(client, user_notif):
    headers = _token(user_notif)
    resp = await client.get("/api/v1/notifications/config", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_config_forbidden_for_user(client, user_notif):
    headers = _token(user_notif)
    resp = await client.post(
        "/api/v1/notifications/config",
        json={"email_enabled": True},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_config_updates_for_admin(client, db_session, admin_notif):
    headers = _token(admin_notif)
    resp = await client.post(
        "/api/v1/notifications/config",
        json={
            "email_enabled": True,
            "email_recipients": "test@example.com",
            "notify_on_severities": "critical",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email_enabled"] is True
    assert data["email_recipients"] == "test@example.com"
    assert data["notify_on_severities"] == "critical"


@pytest.mark.asyncio
async def test_get_config_returns_existing_for_admin(
    client, db_session, admin_notif
):
    headers = _token(admin_notif)
    # Create config
    await client.post(
        "/api/v1/notifications/config",
        json={
            "slack_enabled": True,
            "slack_webhook_url": "https://hooks.slack.com/test",
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/notifications/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["slack_enabled"] is True


@pytest.mark.asyncio
async def test_get_config_uses_install_defaults_when_missing(client, admin_notif):
    headers = _token(admin_notif)
    with (
        patch("app.api.routes.notifications.settings.DEFAULT_EMAIL_NOTIFICATIONS_ENABLED", True),
        patch("app.api.routes.notifications.settings.DEFAULT_EMAIL_RECIPIENTS", "ops@example.com"),
        patch("app.api.routes.notifications.settings.DEFAULT_SLACK_NOTIFICATIONS_ENABLED", True),
        patch("app.api.routes.notifications.settings.DEFAULT_SLACK_WEBHOOK_URL", "https://hooks.slack.com/default"),
        patch("app.api.routes.notifications.settings.DEFAULT_NOTIFY_ON_SEVERITIES", "critical,high,medium"),
    ):
        resp = await client.get("/api/v1/notifications/config", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["email_enabled"] is True
    assert data["email_recipients"] == "ops@example.com"
    assert data["slack_enabled"] is True
    assert data["slack_webhook_url"] == "https://hooks.slack.com/default"
    assert data["notify_on_severities"] == "critical,high,medium"


def _session_ctx_factory(session):
    """Wrap an existing AsyncSession so AsyncSessionLocal() returns a no-op
    async context manager that yields it. Lets the test fully own the session
    the bootstrap function operates on."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


@pytest.mark.asyncio
async def test_bootstrap_hydrates_null_recipients_from_env(db_session):
    """If an earlier seed left email_recipients NULL, a later startup with a
    populated env var should fill it in. Covers the 'EC config screen filled in
    after first install' case."""
    from sqlalchemy import delete, select
    from app.main import _bootstrap_notification_defaults
    from app.models.notification_config import NotificationConfig

    await db_session.execute(
        delete(NotificationConfig).where(NotificationConfig.tenant_id == "default")
    )
    await db_session.flush()

    db_session.add(
        NotificationConfig(
            tenant_id="default",
            email_enabled=True,
            email_recipients=None,
            slack_enabled=False,
            slack_webhook_url=None,
            notify_on_severities="critical,high",
        )
    )
    await db_session.flush()

    with (
        patch("app.core.database.AsyncSessionLocal", _session_ctx_factory(db_session)),
        patch("app.main.settings.DEFAULT_EMAIL_RECIPIENTS", "ops@example.com"),
        patch("app.main.settings.DEFAULT_SLACK_WEBHOOK_URL", ""),
    ):
        await _bootstrap_notification_defaults()

    result = await db_session.execute(
        select(NotificationConfig).where(NotificationConfig.tenant_id == "default")
    )
    row = result.scalar_one()
    assert row.email_recipients == "ops@example.com"
    assert row.slack_webhook_url is None


@pytest.mark.asyncio
async def test_bootstrap_does_not_clobber_user_cleared_or_set_recipients(db_session):
    """User-cleared field stores '' (not NULL). Hydrate must not touch it.
    User-set field stores a value. Hydrate must not touch it either."""
    from sqlalchemy import delete, select
    from app.main import _bootstrap_notification_defaults
    from app.models.notification_config import NotificationConfig

    await db_session.execute(
        delete(NotificationConfig).where(NotificationConfig.tenant_id == "default")
    )
    await db_session.flush()

    db_session.add(
        NotificationConfig(
            tenant_id="default",
            email_enabled=True,
            email_recipients="",
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/user-set",
            notify_on_severities="critical",
        )
    )
    await db_session.flush()

    with (
        patch("app.core.database.AsyncSessionLocal", _session_ctx_factory(db_session)),
        patch("app.main.settings.DEFAULT_EMAIL_RECIPIENTS", "ops@example.com"),
        patch("app.main.settings.DEFAULT_SLACK_WEBHOOK_URL", "https://hooks.slack.com/install-default"),
    ):
        await _bootstrap_notification_defaults()

    result = await db_session.execute(
        select(NotificationConfig).where(NotificationConfig.tenant_id == "default")
    )
    row = result.scalar_one()
    assert row.email_recipients == ""
    assert row.slack_webhook_url == "https://hooks.slack.com/user-set"


@pytest.mark.asyncio
async def test_notify_bundle_findings_calls_send_functions():
    """notify_bundle_findings calls email and slack when enabled."""
    from app.services.notifications import notify_bundle_findings

    # Build mock objects
    mock_bundle = MagicMock()
    mock_bundle.id = uuid.uuid4()
    mock_bundle.tenant_id = "test-tenant"
    mock_bundle.original_filename = "test.tar.gz"

    mock_finding = MagicMock()
    mock_finding.severity = "critical"
    mock_finding.status = "open"
    mock_finding.rule_id = "test_rule"
    mock_finding.title = "Test Finding"

    mock_config = MagicMock()
    mock_config.email_enabled = True
    mock_config.slack_enabled = True
    mock_config.email_recipients = "test@example.com"
    mock_config.slack_webhook_url = "https://hooks.slack.com/test"
    mock_config.notify_on_severities = "critical,high"

    mock_session = MagicMock()
    mock_session.get.return_value = mock_bundle
    mock_session.query.return_value.filter.return_value.first.return_value = mock_config
    mock_session.query.return_value.filter.return_value.all.return_value = [
        mock_finding
    ]

    with (
        patch("app.services.notifications.send_email_notification") as mock_email,
        patch("app.services.notifications.send_slack_notification") as mock_slack,
    ):
        notify_bundle_findings(str(mock_bundle.id), mock_session)
        mock_email.assert_called_once()
        mock_slack.assert_called_once()
