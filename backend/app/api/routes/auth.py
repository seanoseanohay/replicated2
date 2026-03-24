import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
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
    )


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: RegisterRequest,
    x_tenant_id: str = Header(default="default"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled",
        )

    # Check email not already taken in this tenant
    result = await db.execute(
        select(User).where(User.email == body.email, User.tenant_id == x_tenant_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this tenant",
        )

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role="analyst",
        tenant_id=x_tenant_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    x_tenant_id: str = Header(default="default"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(
        select(User).where(User.email == body.email, User.tenant_id == x_tenant_id)
    )
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
