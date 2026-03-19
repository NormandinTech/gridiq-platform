"""
GridIQ — Database Service
Async SQLAlchemy session management + TimescaleDB hypertable setup.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings
from backend.models.db_models import Base

logger = logging.getLogger(__name__)

# ── Engine + session factory ──────────────────────────────────────────────────

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,          # detect dead connections
    pool_recycle=3600,            # recycle connections every hour
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Table creation + TimescaleDB setup ────────────────────────────────────────

async def init_db() -> None:
    """
    Create all tables and configure TimescaleDB hypertables.
    Call once on application startup (before first request).
    """
    async with engine.begin() as conn:
        logger.info("[DB] Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("[DB] Tables created")

        # Convert telemetry_readings to TimescaleDB hypertable for
        # automatic time-partitioning and compression.
        # This is idempotent — safe to call multiple times.
        try:
            await conn.execute(
                """
                SELECT create_hypertable(
                    'telemetry_readings', 'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 day'
                );
                """
            )
            await conn.execute(
                """
                SELECT create_hypertable(
                    'grid_snapshots', 'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 hour'
                );
                """
            )
            # Add compression policy: compress chunks older than 7 days
            await conn.execute(
                """
                ALTER TABLE telemetry_readings
                SET (
                    timescaledb.compress,
                    timescaledb.compress_orderby = 'timestamp DESC',
                    timescaledb.compress_segmentby = 'asset_id'
                );
                """
            )
            await conn.execute(
                """
                SELECT add_compression_policy(
                    'telemetry_readings',
                    INTERVAL '7 days',
                    if_not_exists => TRUE
                );
                """
            )
            logger.info("[DB] TimescaleDB hypertables configured")
        except Exception as exc:
            # Non-fatal: TimescaleDB extension may not be installed
            logger.warning(f"[DB] TimescaleDB setup skipped (standard PostgreSQL mode): {exc}")


async def close_db() -> None:
    """Dispose the connection pool on application shutdown."""
    await engine.dispose()
    logger.info("[DB] Connection pool closed")
