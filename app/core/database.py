"""
Database configuration and session management.
Production-ready singleton pattern for async PostgreSQL operations.
"""

import asyncio
import re
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import Pool

from app.core.logging import logger


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class DatabaseManager:
    """
    Singleton database manager for async PostgreSQL operations.
    Handles connection pooling, sessions, and lifecycle management.
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance.engine: Optional[AsyncEngine] = None
            cls._instance.async_session_factory: Optional[async_sessionmaker] = None
            cls._instance._database_url: Optional[str] = None
            cls._instance._debug: bool = False
        return cls._instance

    async def initialize(
        self,
        database_url: str,
        debug: bool = False,
        pool_size: int = 30,
        max_overflow: int = 50,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo: bool = False,
        echo_pool: bool = False,
    ) -> None:
        """Initialize database engine and session factory."""
        if self._initialized:
            logger.warning("DatabaseManager already initialized")
            return

        if DatabaseManager._lock:
            raise RuntimeError("DatabaseManager initialization already in progress")

        DatabaseManager._lock = True

        try:
            logger.info("=" * 80)
            logger.info("Initializing Database Engine")
            logger.info("=" * 80)

            if debug:
                echo = True
                echo_pool = True

            self._database_url = database_url
            self._debug = debug

            # Create async engine with connection pooling
            self.engine = create_async_engine(
                database_url,
                pool_size=50,
                max_overflow=100,
                pool_timeout=60,
                pool_recycle=1800,
                pool_pre_ping=True,
                echo=False,
                echo_pool=False,
                connect_args={
                    "statement_cache_size": 0,
                    "max_cacheable_statement_size": 1024 * 10,
                    "command_timeout": 30,
                },
            )

            # Setup pool event listeners
            self._setup_pool_listeners()

            # Create session factory
            self.async_session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            self._initialized = True

            logger.info("Database engine initialized successfully")
            logger.info(
                f"Pool: size={pool_size}, max_overflow={max_overflow}, total={pool_size + max_overflow}"
            )
            logger.info(
                f"Settings: timeout={pool_timeout}s, recycle={pool_recycle}s, pre_ping={pool_pre_ping}"
            )
            logger.info("=" * 80)

        except Exception as e:
            logger.error("=" * 80)
            logger.error("FATAL: Database initialization failed")
            logger.error("=" * 80)
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            raise
        finally:
            DatabaseManager._lock = False

    def _setup_pool_listeners(self) -> None:
        """Setup connection pool event listeners for monitoring."""

        @event.listens_for(Pool, "connect")
        def receive_connect(dbapi_conn, connection_record):
            if self._debug:
                logger.debug(f"New connection: {id(dbapi_conn)}")

        @event.listens_for(Pool, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            if self._debug:
                logger.debug(f"Connection checked out: {id(dbapi_conn)}")

        @event.listens_for(Pool, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            if self._debug:
                logger.debug(f"Connection returned: {id(dbapi_conn)}")

    async def create_tables(self) -> None:
        """Create all database tables. Use Alembic migrations in production."""
        if not self._initialized or self.engine is None:
            raise RuntimeError("DatabaseManager not initialized")

        try:
            logger.info("Creating database tables...")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all, checkfirst=True)
            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error("=" * 80)
            logger.error("ERROR: Failed to create tables")
            logger.error("=" * 80)
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            raise

    async def drop_tables(self) -> None:
        """Drop all database tables. WARNING: Deletes all data!"""
        if not self._initialized or self.engine is None:
            raise RuntimeError("DatabaseManager not initialized")

        try:
            logger.warning("Dropping all database tables...")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.warning("All database tables dropped")

        except Exception as e:
            logger.error("=" * 80)
            logger.error("ERROR: Failed to drop tables")
            logger.error("=" * 80)
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            raise

    async def close(self) -> None:
        """Close all database connections. Call at application shutdown."""
        if self.engine is None:
            logger.warning("Database engine already closed")
            return

        try:
            logger.info("Closing database connections...")
            await self.engine.dispose()
            self.engine = None
            self.async_session_factory = None
            self._initialized = False
            logger.info("Database connections closed successfully")

        except Exception as e:
            logger.error("=" * 80)
            logger.error("ERROR: Failed to close database")
            logger.error("=" * 80)
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            raise

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session with automatic cleanup.

        Usage:
            async with db_manager.session() as session:
                user = await user_crud.create(session, data)
                await session.commit()  # Manual commit required
        """
        if not self._initialized or self.async_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized")

        session: AsyncSession = self.async_session_factory()
        try:
            if self._debug:
                logger.debug(f"Session created: {id(session)}")

            yield session

        except Exception as e:
            await session.rollback()
            logger.error("=" * 80)
            logger.error("ERROR: Database operation failed, rolled back")
            logger.error("=" * 80)
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            raise

        finally:
            await session.close()
            if self._debug:
                logger.debug(f"Session closed: {id(session)}")

    async def warmup_connections(self, min_connections: int = 10) -> None:
        """Warm up connection pool by creating initial connections."""
        if not self._initialized or self.async_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized")

        try:
            logger.info(f"Warming up {min_connections} database connections...")

            # Create connections in parallel using asyncio.gather
            connections = []
            for i in range(min_connections):
                session = self.async_session_factory()
                connections.append(session)

            # Test each connection
            tasks = []
            for session in connections:
                task = session.execute(text("SELECT 1"))
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Close sessions properly
            for session in connections:
                await session.close()

            logger.info(
                f"Successfully warmed up {min_connections} database connections"
            )

        except Exception as e:
            logger.error(f"Failed to warm up connections: {str(e)}")
            raise

    async def health_check(self) -> bool:
        """Check database connectivity."""
        if not self._initialized or self.async_session_factory is None:
            logger.warning("Health check failed: not initialized")
            return False

        try:
            async with self.async_session_factory() as session:
                await session.execute(text("SELECT 1"))
                if self._debug:
                    logger.debug("Health check passed")
                return True

        except Exception as e:
            logger.error("=" * 80)
            logger.error("Health check FAILED")
            logger.error("=" * 80)
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.exception("Traceback:")
            logger.error("=" * 80)
            return False

    async def get_pool_status(self) -> dict:
        """Get current connection pool status for monitoring."""
        if not self._initialized or self.engine is None:
            raise RuntimeError("DatabaseManager not initialized")

        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.checkedin() + pool.checkedout(),
        }

    @property
    def is_initialized(self) -> bool:
        """Check if database manager is ready."""
        return self._initialized

    @property
    def database_url(self) -> Optional[str]:
        """Get database URL with masked password."""
        if not self._database_url:
            return None
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", self._database_url)

    def __repr__(self) -> str:
        status = "initialized" if self._initialized else "not initialized"
        return f"<DatabaseManager({status})>"


# Global singleton instance
db_manager = DatabaseManager()
