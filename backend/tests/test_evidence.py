"""Tests for GET /api/v1/bundles/{bundle_id}/evidence endpoint."""
import uuid

import pytest

from app.models.bundle import Bundle
from app.models.evidence import Evidence


@pytest.mark.asyncio
async def test_list_evidence_bundle_not_found(client):
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v1/bundles/{fake_id}/evidence",
        headers={"X-Tenant-ID": "default"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_evidence_empty(client, db_session):
    """Bundle with no evidence returns 200 with empty list."""
    bundle = Bundle(
        filename="test.tar.gz",
        original_filename="test.tar.gz",
        size_bytes=100,
        status="ready",
        tenant_id="ev-tenant",
        s3_key="ev-tenant/test.tar.gz",
    )
    db_session.add(bundle)
    await db_session.flush()
    await db_session.refresh(bundle)
    bundle_id = str(bundle.id)

    response = await client.get(
        f"/api/v1/bundles/{bundle_id}/evidence",
        headers={"X-Tenant-ID": "ev-tenant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_evidence_returns_records(client, db_session):
    """Bundle with seeded evidence records is returned with correct shape."""
    bundle = Bundle(
        filename="bundle.tar.gz",
        original_filename="bundle.tar.gz",
        size_bytes=200,
        status="ready",
        tenant_id="ev-tenant-2",
        s3_key="ev-tenant-2/bundle.tar.gz",
    )
    db_session.add(bundle)
    await db_session.flush()
    await db_session.refresh(bundle)
    bundle_id = bundle.id

    ev1 = Evidence(
        bundle_id=bundle_id,
        kind="Pod",
        namespace="default",
        name="my-pod",
        source_path="cluster-resources/pods.json",
        raw_data={"status": {"phase": "Running"}},
    )
    ev2 = Evidence(
        bundle_id=bundle_id,
        kind="Log",
        namespace="default",
        name="app",
        source_path="pod-logs/default/my-pod/app.log",
        raw_data={"lines": ["hello"], "total_lines": 1, "path": "pod-logs/default/my-pod/app.log"},
    )
    db_session.add(ev1)
    db_session.add(ev2)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/bundles/{str(bundle_id)}/evidence",
        headers={"X-Tenant-ID": "ev-tenant-2"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Check shape of first item
    item = next(i for i in data["items"] if i["kind"] == "Pod")
    assert item["name"] == "my-pod"
    assert item["namespace"] == "default"
    assert item["bundle_id"] == str(bundle_id)
    assert "raw_data" in item
    assert "id" in item
    assert "created_at" in item


@pytest.mark.asyncio
async def test_list_evidence_kind_filter(client, db_session):
    """The ?kind= query param filters evidence by kind."""
    bundle = Bundle(
        filename="filter.tar.gz",
        original_filename="filter.tar.gz",
        size_bytes=300,
        status="ready",
        tenant_id="ev-tenant-3",
        s3_key="ev-tenant-3/filter.tar.gz",
    )
    db_session.add(bundle)
    await db_session.flush()
    await db_session.refresh(bundle)
    bundle_id = bundle.id

    for i in range(3):
        db_session.add(Evidence(
            bundle_id=bundle_id,
            kind="Pod",
            namespace="default",
            name=f"pod-{i}",
            source_path="cluster-resources/pods.json",
            raw_data={},
        ))
    for i in range(2):
        db_session.add(Evidence(
            bundle_id=bundle_id,
            kind="Node",
            namespace=None,
            name=f"node-{i}",
            source_path="cluster-info/nodes.json",
            raw_data={},
        ))
    await db_session.flush()

    # Filter by Pod
    response = await client.get(
        f"/api/v1/bundles/{str(bundle_id)}/evidence?kind=Pod",
        headers={"X-Tenant-ID": "ev-tenant-3"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert all(i["kind"] == "Pod" for i in data["items"])

    # Filter by Node
    response = await client.get(
        f"/api/v1/bundles/{str(bundle_id)}/evidence?kind=Node",
        headers={"X-Tenant-ID": "ev-tenant-3"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(i["kind"] == "Node" for i in data["items"])


@pytest.mark.asyncio
async def test_list_evidence_tenant_isolation(client, db_session):
    """Evidence for a bundle owned by tenant-A is not visible to tenant-B."""
    bundle = Bundle(
        filename="isolated.tar.gz",
        original_filename="isolated.tar.gz",
        size_bytes=50,
        status="ready",
        tenant_id="tenant-isolated",
        s3_key="tenant-isolated/isolated.tar.gz",
    )
    db_session.add(bundle)
    await db_session.flush()
    await db_session.refresh(bundle)
    bundle_id = str(bundle.id)

    response = await client.get(
        f"/api/v1/bundles/{bundle_id}/evidence",
        headers={"X-Tenant-ID": "other-tenant"},
    )
    assert response.status_code == 404
