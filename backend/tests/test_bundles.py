import gzip
import io
import uuid
from unittest.mock import MagicMock, patch

import pytest


def make_gzip_bytes(content: bytes = b"fake content") -> bytes:
    """Create a valid gzip archive in memory."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_list_bundles_empty(client):
    response = await client.get(
        "/api/v1/bundles", headers={"X-Tenant-ID": "test-tenant-empty"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_bundle_not_found(client):
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v1/bundles/{fake_id}", headers={"X-Tenant-ID": "default"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_bundle(client):
    mock_storage = MagicMock()
    mock_storage.upload_bundle.return_value = "test-tenant/file.tar.gz"

    file_content = make_gzip_bytes(b"fake tar.gz content for testing")

    with patch("app.api.routes.bundles.storage_service", mock_storage), patch(
        "app.api.routes.bundles.process_bundle"
    ) as mock_celery_task:
        mock_celery_task.delay = MagicMock()
        response = await client.post(
            "/api/v1/bundles",
            files={"file": ("test-bundle.tar.gz", io.BytesIO(file_content), "application/gzip")},
            headers={"X-Tenant-ID": "test-tenant"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "test-bundle.tar.gz"
    assert data["status"] == "uploaded"
    assert data["tenant_id"] == "test-tenant"
    assert data["size_bytes"] == len(file_content)


@pytest.mark.asyncio
async def test_upload_and_retrieve_bundle(client):
    mock_storage = MagicMock()
    mock_storage.upload_bundle.return_value = "tenant-a/20240101000000-abcd1234-bundle.tar.gz"

    file_content = make_gzip_bytes(b"support bundle data")
    bundle_id = None

    with patch("app.api.routes.bundles.storage_service", mock_storage), patch(
        "app.api.routes.bundles.process_bundle"
    ) as mock_task:
        mock_task.delay = MagicMock()
        upload_resp = await client.post(
            "/api/v1/bundles",
            files={"file": ("bundle.tar.gz", io.BytesIO(file_content), "application/gzip")},
            headers={"X-Tenant-ID": "tenant-a"},
        )
        assert upload_resp.status_code == 201
        bundle_id = upload_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/bundles/{bundle_id}", headers={"X-Tenant-ID": "tenant-a"}
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == bundle_id


@pytest.mark.asyncio
async def test_tenant_isolation(client):
    """A bundle uploaded by tenant-x should not be visible to tenant-y."""
    mock_storage = MagicMock()
    mock_storage.upload_bundle.return_value = "tenant-x/bundle.tar.gz"

    file_content = make_gzip_bytes(b"tenant x data")

    with patch("app.api.routes.bundles.storage_service", mock_storage), patch(
        "app.api.routes.bundles.process_bundle"
    ) as mock_task:
        mock_task.delay = MagicMock()
        upload_resp = await client.post(
            "/api/v1/bundles",
            files={"file": ("bundle.tar.gz", io.BytesIO(file_content), "application/gzip")},
            headers={"X-Tenant-ID": "tenant-x"},
        )
        bundle_id = upload_resp.json()["id"]

    # tenant-y should get 404
    resp = await client.get(
        f"/api/v1/bundles/{bundle_id}", headers={"X-Tenant-ID": "tenant-y"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_invalid_magic_bytes(client):
    """Upload with non-archive content should return 400."""
    mock_storage = MagicMock()
    mock_storage.upload_bundle.return_value = "tenant-z/bundle.tar.gz"

    file_content = b"this is not an archive at all"

    with patch("app.api.routes.bundles.storage_service", mock_storage), patch(
        "app.api.routes.bundles.process_bundle"
    ) as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            "/api/v1/bundles",
            files={"file": ("bundle.tar.gz", io.BytesIO(file_content), "application/gzip")},
            headers={"X-Tenant-ID": "tenant-z"},
        )

    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_bundle(client):
    """DELETE /api/v1/bundles/{id} returns 204 and bundle is gone from subsequent GET."""
    mock_storage = MagicMock()
    mock_storage.upload_bundle.return_value = "tenant-del/bundle.tar.gz"
    mock_storage.delete_bundle = MagicMock()

    file_content = make_gzip_bytes(b"bundle to delete")
    bundle_id = None

    with patch("app.api.routes.bundles.storage_service", mock_storage), patch(
        "app.api.routes.bundles.process_bundle"
    ) as mock_task:
        mock_task.delay = MagicMock()
        upload_resp = await client.post(
            "/api/v1/bundles",
            files={"file": ("bundle.tar.gz", io.BytesIO(file_content), "application/gzip")},
            headers={"X-Tenant-ID": "tenant-del"},
        )
        assert upload_resp.status_code == 201
        bundle_id = upload_resp.json()["id"]

    with patch("app.api.routes.bundles.storage_service", mock_storage):
        del_resp = await client.delete(
            f"/api/v1/bundles/{bundle_id}", headers={"X-Tenant-ID": "tenant-del"}
        )
    assert del_resp.status_code == 204

    # Bundle should be gone
    get_resp = await client.get(
        f"/api/v1/bundles/{bundle_id}", headers={"X-Tenant-ID": "tenant-del"}
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_bundle_not_found(client):
    """DELETE /api/v1/bundles/{nonexistent} returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(
        f"/api/v1/bundles/{fake_id}", headers={"X-Tenant-ID": "default"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_bundle_tenant_isolation(client):
    """DELETE /api/v1/bundles/{id} with wrong tenant returns 404."""
    mock_storage = MagicMock()
    mock_storage.upload_bundle.return_value = "tenant-owner/bundle.tar.gz"

    file_content = make_gzip_bytes(b"owned bundle")

    with patch("app.api.routes.bundles.storage_service", mock_storage), patch(
        "app.api.routes.bundles.process_bundle"
    ) as mock_task:
        mock_task.delay = MagicMock()
        upload_resp = await client.post(
            "/api/v1/bundles",
            files={"file": ("bundle.tar.gz", io.BytesIO(file_content), "application/gzip")},
            headers={"X-Tenant-ID": "tenant-owner"},
        )
        assert upload_resp.status_code == 201
        bundle_id = upload_resp.json()["id"]

    # Different tenant trying to delete
    del_resp = await client.delete(
        f"/api/v1/bundles/{bundle_id}", headers={"X-Tenant-ID": "tenant-other"}
    )
    assert del_resp.status_code == 404
