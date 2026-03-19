import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import create_access_token, hash_password
from app.core.database import Base, get_db
from app.main import app
from app.models.user import User

# Use an in-memory SQLite for unit tests so no Postgres is needed locally
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture()
async def db_session(engine):
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture()
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def manager_user(db_session):
    """A manager-role user for tests that require elevated permissions."""
    user = User(
        id=uuid.uuid4(),
        email=f"manager-{uuid.uuid4().hex[:8]}@test.example.com",
        hashed_password=hash_password("managerpass1"),
        role="manager",
        tenant_id="default",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def make_manager_headers(user: User, tenant_id: str = "default") -> dict:
    """Build Authorization + X-Tenant-ID headers for a manager user."""
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role, "tenant_id": user.tenant_id}
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}
