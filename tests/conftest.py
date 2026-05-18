import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.session import _connect_args, _db_url, get_db
from app.main import app

# Use NullPool so each test gets a fresh connection (no stale-pool issues with asyncpg)
_test_engine = create_async_engine(_db_url, echo=False, connect_args=_connect_args, poolclass=NullPool)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db():
    """Yield a DB session that rolls back all changes after each test."""
    session = AsyncSession(_test_engine, expire_on_commit=False)

    # Override commit so service-layer commits just flush (stay in the same txn)
    async def _noop_commit():
        await session.flush()

    session.commit = _noop_commit

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
async def client(db):
    """Async HTTP client with DB session overridden to use test transaction."""

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def register_payload():
    """Fresh registration payload with unique email."""
    unique = uuid.uuid4().hex[:8]
    return {
        "email": f"test-{unique}@example.com",
        "password": "securepass123",
        "full_name": "Test User",
        "org_name": f"Test Org {unique}",
    }
