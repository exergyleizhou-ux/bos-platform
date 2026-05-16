"""
BOS Pipeline v9.0 test configuration and fixtures.

Shared pytest fixtures for database, client, auth, and sample payloads.
"""

from pathlib import Path
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_async_session
from app.main import app
from app.models import Tenant, User
from app.routers.auth import create_access_token, pwd_context

TEST_DATABASE_FILE = Path(f"test-{uuid.uuid4().hex}.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///./{TEST_DATABASE_FILE.name}"
collect_ignore_glob = ["*.backup.py"]

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


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create and drop all database tables for the test session."""
    if TEST_DATABASE_FILE.exists():
        TEST_DATABASE_FILE.unlink()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if TEST_DATABASE_FILE.exists():
        TEST_DATABASE_FILE.unlink()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async database session per test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def override_db(db_session: AsyncSession):
    """Override the app database dependency with the test session."""

    async def _override():
        yield db_session

    app.dependency_overrides[get_async_session] = _override
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an ASGI test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a tenant for the current test."""
    tenant = Tenant(name="Test Tenant", slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a regular operator user for the current test."""
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


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create or reuse an admin user for the current test."""
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
    """Create or reuse an operator user for the current test."""
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
    """Create or reuse a scientist user for the current test."""
    return await _get_or_create_user(
        db_session,
        username="test_scientist",
        email="test_scientist@bos.io",
        full_name="Test Scientist",
        password="TestScientist123!",
        role="scientist",
        tenant_id=test_tenant.id,
    )


@pytest_asyncio.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization headers for the default test user."""
    return {"Authorization": f"Bearer {_make_token(test_user)}"}


@pytest_asyncio.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    """Authorization headers for the admin test user."""
    return {"Authorization": f"Bearer {_make_token(admin_user)}"}


@pytest_asyncio.fixture
def operator_headers(operator_user: User) -> dict[str, str]:
    """Authorization headers for the operator test user."""
    return {"Authorization": f"Bearer {_make_token(operator_user)}"}


@pytest_asyncio.fixture
def scientist_headers(scientist_user: User) -> dict[str, str]:
    """Authorization headers for the scientist test user."""
    return {"Authorization": f"Bearer {_make_token(scientist_user)}"}


@pytest_asyncio.fixture
def test_admin(admin_user: User) -> User:
    """Legacy fixture alias."""
    return admin_user


@pytest.fixture
def sample_batch_payload() -> dict:
    """Sample batch payload used by integration tests."""
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


@pytest.fixture
def sample_ser_payload() -> dict:
    """Sample SER payload used by tests."""
    return {
        "dm_in": 10.0,
        "dm_out": 8.5,
        "n_in": 0.5,
        "n_larvae": 0.3,
        "n_frass": 0.15,
    }
