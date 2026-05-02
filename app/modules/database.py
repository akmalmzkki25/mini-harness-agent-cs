from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.setting import setting
from app.models.base import Base
import app.models.conversation  # noqa: F401
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _build_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


engine = create_async_engine(_build_async_database_url(setting.DATABASE_URL), pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    logger.debug("Opening database session")
    async with AsyncSessionLocal() as session:
        yield session
    logger.debug("Database session closed")


async def create_database_schema() -> None:
    logger.info("Creating database schema if needed")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text(
                "ALTER TABLE conversation_messages "
                "ADD COLUMN IF NOT EXISTS files JSONB DEFAULT '[]'::jsonb"
            )
        )
    logger.info("Database schema sync completed")
