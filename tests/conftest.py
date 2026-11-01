import os
from collections.abc import AsyncIterator
from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.config import Settings
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55432/webhooks"
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        processing_delay_seconds=1,
        lease_seconds=3,
        poll_interval_seconds=0.1,
        db_command_timeout_seconds=2,
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        await app.state.api_pool.execute("TRUNCATE transactions")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            http.app = app
            yield http


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(TEST_DATABASE_URL)
    yield connection
    await connection.close()


@pytest.fixture
def payload() -> dict:
    return {
        "transaction_id": f"txn_{uuid4().hex}",
        "source_account": "acc_user_789",
        "destination_account": "acc_merchant_456",
        "amount": 1500,
        "currency": "INR",
    }
