"""
Admin-only routes for user management.
All endpoints require the 'admin' role.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_auth
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── Dependency ─────────────────────────────────────────────────────────────────


async def require_admin(user: User = Depends(require_auth)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return user


# ── Schemas ────────────────────────────────────────────────────────────────────


class UserAdminRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    tenant_id: str
    is_active: bool
    created_at: str

    @classmethod
    def from_orm_user(cls, u: User) -> "UserAdminRead":
        return cls(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            tenant_id=u.tenant_id,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
        )


class UserRoleUpdate(BaseModel):
    role: str


class UserStatusUpdate(BaseModel):
    is_active: bool


class AdminStats(BaseModel):
    total_users: int
    total_bundles: int
    total_findings: int
    users_by_role: dict[str, int]


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserAdminRead])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserAdminRead]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserAdminRead.from_orm_user(u) for u in users]


@router.patch("/users/{user_id}/role", response_model=UserAdminRead)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminRead:
    if body.role not in ("analyst", "manager", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    old_role = user.role
    user.role = body.role
    await db.flush()
    await db.refresh(user)

    logger.info(
        "admin_role_changed",
        target_user=str(user_id),
        old=old_role,
        new=body.role,
        by=admin.email,
    )
    return UserAdminRead.from_orm_user(user)


@router.patch("/users/{user_id}/status", response_model=UserAdminRead)
async def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminRead:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.id == admin.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user.is_active = body.is_active
    await db.flush()
    await db.refresh(user)

    logger.info(
        "admin_status_changed",
        target_user=str(user_id),
        is_active=body.is_active,
        by=admin.email,
    )
    return UserAdminRead.from_orm_user(user)


@router.get("/stats", response_model=AdminStats)
async def get_stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminStats:
    total_users = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar_one()
    total_bundles = (
        await db.execute(select(func.count()).select_from(Bundle))
    ).scalar_one()
    total_findings = (
        await db.execute(select(func.count()).select_from(Finding))
    ).scalar_one()

    role_rows = await db.execute(select(User.role, func.count()).group_by(User.role))
    users_by_role = {row[0]: row[1] for row in role_rows.all()}

    return AdminStats(
        total_users=total_users,
        total_bundles=total_bundles,
        total_findings=total_findings,
        users_by_role=users_by_role,
    )
