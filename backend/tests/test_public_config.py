from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_public_config_reflects_registration_flag(client):
    with patch("app.api.routes.public_config.settings.ALLOW_REGISTRATION", False):
        resp = await client.get("/api/v1/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["allow_registration"] is False


@pytest.mark.asyncio
async def test_register_blocked_when_registration_disabled(client):
    with patch("app.api.routes.auth.settings.ALLOW_REGISTRATION", False):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "blocked@example.com", "password": "securepassword"},
        )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Registration is disabled"
