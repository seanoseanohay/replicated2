import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_token
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Returns authenticated User if JWT present and valid.
    Falls back to None (anonymous with X-Tenant-ID) for backward compat.
    """
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def require_auth(user: User | None = Depends(get_current_user)) -> User:
    """Raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


async def require_manager(user: User = Depends(require_auth)) -> User:
    """Raises 403 if not manager or admin."""
    if user.role not in ("manager", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required")
    return user


async def get_tenant_id(
    user: User | None = Depends(get_current_user),
    x_tenant_id: str = Header(default="default"),
) -> str:
    """Extract tenant_id from JWT (preferred) or X-Tenant-ID header (backward compat)."""
    if user is not None:
        return user.tenant_id
    return x_tenant_id
