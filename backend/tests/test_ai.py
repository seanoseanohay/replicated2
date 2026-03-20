"""
Tests for AI explain endpoint.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.models.bundle import Bundle
from app.models.finding import Finding


@pytest_asyncio.fixture()
async def bundle(db_session):
    b = Bundle(
        id=uuid.uuid4(),
        filename="test.tar.gz",
        original_filename="test.tar.gz",
        size_bytes=1024,
        status="ready",
        tenant_id="tenant-ai",
        s3_key="test/test.tar.gz",
    )
    db_session.add(b)
    await db_session.flush()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture()
async def finding(db_session, bundle):
    f = Finding(
        id=uuid.uuid4(),
        bundle_id=bundle.id,
        rule_id="node_not_ready",
        title="Node Not Ready",
        severity="critical",
        summary="Node node-1 is not in Ready state.",
        evidence_ids=[],
        status="open",
    )
    db_session.add(f)
    await db_session.flush()
    await db_session.refresh(f)
    return f


@pytest.mark.asyncio
async def test_explain_returns_503_when_ai_disabled(client, bundle, finding):
    """When AI_ENABLED=False, explain endpoint returns 503."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.AI_ENABLED = False
        mock_settings.ANTHROPIC_API_KEY = ""
        mock_settings.AI_MODEL = "claude-opus-4-6"

        resp = await client.post(
            f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/explain",
            headers={"X-Tenant-ID": "tenant-ai"},
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_explain_returns_200_with_mocked_client(client, bundle, finding):
    """When AI is enabled and client is mocked, returns 200 with updated finding."""
    # Build a mock Anthropic response
    mock_content = MagicMock()
    mock_content.text = (
        "The node is failing its readiness check due to kubelet issues.\n\n"
        "## Remediation Steps\n\n"
        "1. SSH to the node and check kubelet logs.\n"
        "2. Restart kubelet if it is hung."
    )
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("app.core.config.settings") as mock_settings, \
         patch("app.ai.explainer.get_client", return_value=mock_client), \
         patch("app.api.routes.findings.settings") as route_settings, \
         patch("app.ai.explainer.settings") as explainer_settings:
        mock_settings.AI_ENABLED = True
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-opus-4-6"
        route_settings.AI_ENABLED = True
        explainer_settings.AI_ENABLED = True
        explainer_settings.AI_MODEL = "claude-opus-4-6"

        resp = await client.post(
            f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/explain",
            headers={"X-Tenant-ID": "tenant-ai"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_explained_at"] is not None
