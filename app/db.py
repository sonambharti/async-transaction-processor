from pathlib import Path

import asyncpg

from app.config import Settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


async def create_api_pool(settings: Settings) -> asyncpg.Pool:
    # Connections stay open: a new TLS connection would use up the 500 ms budget.
    return await asyncpg.create_pool(
        settings.database_url,
        min_size=settings.api_pool_size,
        max_size=settings.api_pool_size,
        max_inactive_connection_lifetime=0,
    )


async def create_worker_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=settings.worker_pool_size,
        command_timeout=settings.worker_db_timeout_seconds,
    )


async def apply_schema(pool: asyncpg.Pool) -> None:
    await pool.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
