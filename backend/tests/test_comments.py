"""Tests for Phase 11 — Comments & Discussion."""
import uuid

import pytest
import pytest_asyncio

from app.core.auth import create_access_token, hash_password
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User


def _token(user: User) -> dict:
    tok = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role, "tenant_id": user.tenant_id}
    )
    return {"Authorization": f"Bearer {tok}", "X-Tenant-ID": user.tenant_id}


TENANT = "comment-tenant"


@pytest_asyncio.fixture()
async def manager_cmt(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"mgr-cmt-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="manager",
        tenant_id=TENANT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def analyst_cmt(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"analyst-cmt-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pass"),
        role="analyst",
        tenant_id=TENANT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def bfpair(db_session):
    bundle = Bundle(
        id=uuid.uuid4(),
        filename="cmt-test.tar.gz",
        original_filename="cmt-test.tar.gz",
        size_bytes=100,
        status="ready",
        tenant_id=TENANT,
        s3_key=f"cmt/{uuid.uuid4().hex}.tar.gz",
    )
    db_session.add(bundle)
    await db_session.flush()

    finding = Finding(
        id=uuid.uuid4(),
        bundle_id=bundle.id,
        rule_id="cmt_rule",
        title="Comment Test Finding",
        severity="medium",
        summary="Summary",
        evidence_ids=[],
        status="open",
    )
    db_session.add(finding)
    await db_session.flush()
    await db_session.refresh(bundle)
    await db_session.refresh(finding)
    return bundle, finding


@pytest.mark.asyncio
async def test_list_comments_empty(client, manager_cmt, bfpair):
    bundle, finding = bfpair
    headers = _token(manager_cmt)
    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_post_comment_creates(client, analyst_cmt, bfpair):
    bundle, finding = bfpair
    headers = _token(analyst_cmt)
    resp = await client.post(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments",
        json={"body": "Hello from analyst"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "Hello from analyst"
    assert data["actor"] == analyst_cmt.email


@pytest.mark.asyncio
async def test_delete_own_comment_succeeds(client, analyst_cmt, bfpair):
    bundle, finding = bfpair
    headers = _token(analyst_cmt)

    # Create comment
    create_resp = await client.post(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments",
        json={"body": "To be deleted"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    comment_id = create_resp.json()["id"]

    # Delete own comment
    del_resp = await client.delete(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments/{comment_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_other_user_comment_as_analyst_forbidden(
    client, analyst_cmt, manager_cmt, bfpair
):
    bundle, finding = bfpair

    # Manager creates a comment
    mgr_headers = _token(manager_cmt)
    create_resp = await client.post(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments",
        json={"body": "Manager comment"},
        headers=mgr_headers,
    )
    assert create_resp.status_code == 201
    comment_id = create_resp.json()["id"]

    # Analyst tries to delete manager's comment
    analyst_headers = _token(analyst_cmt)
    del_resp = await client.delete(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments/{comment_id}",
        headers=analyst_headers,
    )
    assert del_resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_other_user_comment_as_manager_succeeds(
    client, analyst_cmt, manager_cmt, bfpair
):
    bundle, finding = bfpair

    # Analyst creates a comment
    analyst_headers = _token(analyst_cmt)
    create_resp = await client.post(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments",
        json={"body": "Analyst comment"},
        headers=analyst_headers,
    )
    assert create_resp.status_code == 201
    comment_id = create_resp.json()["id"]

    # Manager deletes analyst's comment
    mgr_headers = _token(manager_cmt)
    del_resp = await client.delete(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments/{comment_id}",
        headers=mgr_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_comments_tenant_isolation(client, manager_cmt, bfpair):
    """Comments should not be accessible from a different tenant."""
    bundle, finding = bfpair

    resp = await client.get(
        f"/api/v1/bundles/{bundle.id}/findings/{finding.id}/comments",
        headers={"X-Tenant-ID": "other-tenant"},
    )
    assert resp.status_code == 404
