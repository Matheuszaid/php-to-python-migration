from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import QueuePool
from app.config import get_settings
from app.models import Base


class DatabaseManager:
    """Modern database manager with async support and connection pooling."""

    def __init__(self):
        self.settings = get_settings()
        self.engine = create_async_engine(
            self.settings.database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=self.settings.debug,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """Drop all database tables (for testing)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with db_manager.async_session() as session:
        try:
            yield session
        finally:
            await session.close()