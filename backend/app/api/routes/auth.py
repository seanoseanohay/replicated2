import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_auth
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_ALPHANUM = string.ascii_uppercase + string.digits
_MAX_KEY_RETRIES = 10


def _random_org_key() -> str:
    """Generate an 8-character random org key."""
    return "".join(secrets.choice(_ALPHANUM) for _ in range(8))


async def _generate_unique_org_key(db: AsyncSession) -> str:
    """Generate a random org key, retrying until we find one not in the DB."""
    for _attempt in range(_MAX_KEY_RETRIES):
        candidate = _random_org_key()
        taken = await db.execute(select(User).where(User.org_key == candidate))
        if taken.scalar_one_or_none() is None:
            return candidate
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate unique org key",
    )


async def _resolve_tenant(body: RegisterRequest, db: AsyncSession) -> tuple[str, str, str | None]:
    """Return (tenant_id, role, org_key) for this registration.

    If an org_key is provided, join that admin's tenant as a user.
    Otherwise create a brand-new tenant and become its admin.
    """
    if not body.org_key:
        tenant_id = str(uuid.uuid4())
        org_key = await _generate_unique_org_key(db)
        return tenant_id, "admin", org_key

    result = await db.execute(select(User).where(User.org_key == body.org_key))
    admin_user = result.scalar_one_or_none()
    if admin_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid org key",
        )
    return admin_user.tenant_id, "user", None


def _build_token_response(user: User) -> TokenResponse:
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
    }
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        role=user.role,
        tenant_id=user.tenant_id,
        org_key=user.org_key,
    )


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled",
        )

    tenant_id, role, org_key = await _resolve_tenant(body, db)

    result = await db.execute(
        select(User).where(User.email == body.email, User.tenant_id == tenant_id)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this tenant",
        )

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=role,
        tenant_id=tenant_id,
        org_key=org_key,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Emit metrics on new user registration (best-effort, fire-and-forget)
    import asyncio
    from app.services.metrics_reporter import collect_and_send_metrics_sync

    try:
        asyncio.create_task(asyncio.to_thread(collect_and_send_metrics_sync))
    except Exception:
        pass

    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    return _build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh token pair.

    The ``sub`` claim is a string UUID; it must be coerced to ``uuid.UUID``
    before passing to ``db.get`` because the User primary key is typed as
    ``UUID(as_uuid=True)`` in SQLAlchemy.
    """
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return _build_token_response(user)


@router.get("/me", response_model=UserRead)
async def me(
    user: User = Depends(require_auth),
) -> UserRead:
    return UserRead.model_validate(user)
