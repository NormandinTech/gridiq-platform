"""
GridIQ — Alembic Environment
Connects Alembic database migrations to our SQLAlchemy models.
Supports both sync (for migration runs) and async (for the app) engines.
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add project root to path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))))

from backend.core.config import settings
from backend.models.db_models import Base

# Alembic Config object
config = context.config

# Override sqlalchemy.url with our app's database URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The MetaData object from our models — Alembic uses this to detect changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL without a DB connection.
    Useful for reviewing migrations before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Include schema in autogenerate
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against a live async database connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
