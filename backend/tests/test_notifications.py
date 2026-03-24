"""Tests for Phase 10 — Notifications."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.core.auth import create_access_token, hash_password
from app.models.user import User


def _token(user: User) -> dict:
    tok = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role, "tenant_id": user.tenant_id}
    )
    return {"Authorization": f"Bearer {tok}", "X-Tenant-ID": user.tenant_id}


@pytest_asyncio.fixture()
async def manager_notif(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"mgr-notif-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="manager",
        tenant_id="notif-tenant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def analyst_notif(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"analyst-notif-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="analyst",
        tenant_id="notif-tenant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_config_forbidden_for_analyst(client, analyst_notif):
    headers = _token(analyst_notif)
    resp = await client.get("/api/v1/notifications/config", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_config_forbidden_for_analyst(client, analyst_notif):
    headers = _token(analyst_notif)
    resp = await client.post(
        "/api/v1/notifications/config",
        json={"email_enabled": True},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_config_updates_for_manager(client, db_session, manager_notif):
    headers = _token(manager_notif)
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
async def test_get_config_returns_existing_for_manager(client, db_session, manager_notif):
    headers = _token(manager_notif)
    # Create config
    await client.post(
        "/api/v1/notifications/config",
        json={"slack_enabled": True, "slack_webhook_url": "https://hooks.slack.com/test"},
        headers=headers,
    )
    resp = await client.get("/api/v1/notifications/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["slack_enabled"] is True


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
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_finding]

    with patch("app.services.notifications.send_email_notification") as mock_email, \
         patch("app.services.notifications.send_slack_notification") as mock_slack:
        notify_bundle_findings(str(mock_bundle.id), mock_session)
        mock_email.assert_called_once()
        mock_slack.assert_called_once()
