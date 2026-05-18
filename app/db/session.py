import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Neon requires SSL; asyncpg needs an ssl context, not URL params
_connect_args: dict = {}
if "neon.tech" in settings.DATABASE_URL or "sslmode=require" in settings.DATABASE_URL:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args["ssl"] = ssl_ctx

# Strip query params that asyncpg doesn't understand
_db_url = settings.DATABASE_URL.split("?")[0]

engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
