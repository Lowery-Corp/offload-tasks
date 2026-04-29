import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv("DATABASE_URL")

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """
    Initialize one async SQLAlchemy engine and session factory
    per Celery worker process.
    """
    global _engine, _sessionmaker

    if _engine is not None and _sessionmaker is not None:
        return

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    _engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
    )

    _sessionmaker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_db()

    if _sessionmaker is None:
        raise RuntimeError("Database sessionmaker was not initialized")

    return _sessionmaker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Use this inside Celery tasks.

    Opens one session for the task, commits on success,
    rolls back on error, and always closes the session.
    """
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_db() -> None:
    """
    Close the DB engine when the Celery worker process shuts down.
    """
    global _engine, _sessionmaker

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    _sessionmaker = None
