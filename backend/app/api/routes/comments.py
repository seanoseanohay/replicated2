import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_tenant_id
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.comment import Comment
from app.models.finding import Finding
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["comments"])


async def _get_bundle_for_tenant(
    bundle_id: uuid.UUID, tenant_id: str, db: AsyncSession
) -> Bundle:
    result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
    return bundle


async def _get_finding_for_bundle(
    finding_id: uuid.UUID, bundle_id: uuid.UUID, db: AsyncSession
) -> Finding:
    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id, Finding.bundle_id == bundle_id
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    return finding


@router.get(
    "/{bundle_id}/findings/{finding_id}/comments",
    response_model=list[CommentRead],
)
async def list_comments(
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommentRead]:
    await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    await _get_finding_for_bundle(finding_id, bundle_id, db)

    result = await db.execute(
        select(Comment)
        .where(Comment.finding_id == finding_id)
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [CommentRead.model_validate(c) for c in comments]


@router.post(
    "/{bundle_id}/findings/{finding_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: CommentCreate,
    tenant_id: str = Depends(get_tenant_id),
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentRead:
    await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    await _get_finding_for_bundle(finding_id, bundle_id, db)

    actor = current_user.email if current_user is not None else "anonymous"
    comment = Comment(
        finding_id=finding_id,
        bundle_id=bundle_id,
        actor=actor,
        user_id=current_user.id if current_user else None,
        body=body.body,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    logger.info(
        "comment_created",
        comment_id=str(comment.id),
        finding_id=str(finding_id),
        bundle_id=str(bundle_id),
    )
    return CommentRead.model_validate(comment)


@router.delete(
    "/{bundle_id}/findings/{finding_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    comment_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    await _get_finding_for_bundle(finding_id, bundle_id, db)

    result = await db.execute(
        select(Comment).where(
            Comment.id == comment_id, Comment.finding_id == finding_id
        )
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # Authorization: own comment OR manager/admin
    is_manager = current_user is not None and current_user.role in ("manager", "admin")
    is_own = (
        current_user is not None
        and comment.user_id is not None
        and comment.user_id == current_user.id
    )

    if not (is_own or is_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this comment",
        )

    await db.delete(comment)
    await db.flush()

    logger.info(
        "comment_deleted",
        comment_id=str(comment_id),
        finding_id=str(finding_id),
        bundle_id=str(bundle_id),
    )
