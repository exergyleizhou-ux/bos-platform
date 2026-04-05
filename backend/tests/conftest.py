"""
BOS Pipeline v9.0 �� Test Configuration & Fixtures

Shared pytest fixtures for database, client, auth, and factory helpers.
"""

import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.config import get_settings
from app.db import Base, get_async_session
from app.models import Tenant, User
from app.routers.auth import create_access_token, pwd_context

settings = get_settings()


def _make_token(user: User) -> str:
    return create_access_token(user.id, user.role, user.tenant_id)


async def _get_or_create_user(
    db_session: AsyncSession,
    *,
    username: str,
    email: str,
    full_name: str,
    password: str,
    role: str,
    tenant_id: int,
) -> User:
    """Create or update a deterministic test user by username."""
    existing = (await db_session.execute(select(User).where(User.username == username))).scalars().first()
    if existing:
        existing.email = email
        existing.full_name = full_name
        existing.hashed_password = pwd_context.hash(password)
        existing.role = role
        existing.is_active = True
        existing.tenant_id = tenant_id
        await db_session.commit()
        await db_session.refresh(existing)
        return existing

    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=pwd_context.hash(password),
        role=role,
        is_active=True,
        tenant_id=tenant_id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

# ���� Test database URL (SQLite async) ����
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ���� Event loop ����
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ���� Create / drop tables ����
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ���� Session override ����
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ���� Override dependency ����
@pytest_asyncio.fixture(autouse=True)
async def override_db(db_session: AsyncSession):
    async def _override():
        yield db_session

    app.dependency_overrides[get_async_session] = _override
    yield
    app.dependency_overrides.clear()


# ���� HTTP Client ����
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


# ���� Test User ����
@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(name="Test Tenant", slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"testuser_{suffix}",
        email=f"test_{suffix}@bos.io",
        full_name="Test User",
        hashed_password=pwd_context.hash("testpass123"),
        role="operator",
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ���� Admin User ����
@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    return await _get_or_create_user(
        db_session,
        username="test_admin",
        email="test_admin@bos.io",
        full_name="Test Admin",
        password="TestAdmin123!",
        role="admin",
        tenant_id=test_tenant.id,
    )


@pytest_asyncio.fixture
async def operator_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    return await _get_or_create_user(
        db_session,
        username="test_operator",
        email="test_operator@bos.io",
        full_name="Test Operator",
        password="TestOperator123!",
        role="operator",
        tenant_id=test_tenant.id,
    )


@pytest_asyncio.fixture
async def scientist_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    return await _get_or_create_user(
        db_session,
        username="test_scientist",
        email="test_scientist@bos.io",
        full_name="Test Scientist",
        password="TestScientist123!",
        role="scientist",
        tenant_id=test_tenant.id,
    )


# ���� Auth Headers ����
@pytest_asyncio.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id, test_user.role, test_user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(admin_user.id, admin_user.role, admin_user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def operator_headers(operator_user: User) -> dict[str, str]:
    token = create_access_token(operator_user.id, operator_user.role, operator_user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def scientist_headers(scientist_user: User) -> dict[str, str]:
    token = create_access_token(scientist_user.id, scientist_user.role, scientist_user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def test_admin(admin_user: User) -> User:
    """Legacy fixture alias."""
    return admin_user


# ���� Sample Batch Data ����
@pytest.fixture
def sample_batch_payload() -> dict:
    return {
        "batch_id": "BSF-TEST-001",
        "species": "BSF",
        "dm_in": 10.0,
        "dm_out": 8.5,
        "n_in": 0.5,
        "n_larvae": 0.3,
        "n_frass": 0.15,
        "temperature": 28.0,
        "moisture": 65.0,
        "operator": "pytest",
        "notes": "Integration test batch",
    }


# ���� Sample SER Payload ����
@pytest.fixture
def sample_ser_payload() -> dict:
    return {
        "dm_in": 10.0,
        "dm_out": 8.5,
        "n_in": 0.5,
        "n_larvae": 0.3,
        "n_frass": 0.15,
    }
