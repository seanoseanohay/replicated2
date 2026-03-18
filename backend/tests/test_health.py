import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client):
    """Readiness check — mock Redis and S3 so only DB (SQLite) is checked."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    mock_redis_module = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis

    mock_storage = MagicMock()
    mock_storage.ensure_bucket_exists = MagicMock()

    with patch.dict("sys.modules", {"redis.asyncio": mock_redis_module}), \
         patch("app.services.storage.storage_service", mock_storage):
        response = await client.get("/health/ready")

    # Should have a checks key regardless of status
    data = response.json()
    assert "checks" in data
    assert "status" in data
