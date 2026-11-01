import asyncio
import os
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from app import repository
from tests.conftest import TEST_DATABASE_URL
from tests.helpers import wait_for_processed


async def test_transaction_is_processed_after_delay(client, payload, settings):
    started = time.monotonic()
    await client.post("/v1/webhooks/transactions", json=payload)

    transaction = await wait_for_processed(client, payload["transaction_id"])

    assert time.monotonic() - started >= settings.processing_delay_seconds
    assert transaction["processed_at"] is not None


async def test_many_jobs_wait_concurrently(client, settings):
    ids = [f"txn_{uuid4().hex}" for _ in range(50)]
    started = time.monotonic()

    await asyncio.gather(
        *(
            client.post(
                "/v1/webhooks/transactions",
                json={
                    "transaction_id": transaction_id,
                    "source_account": "acc_a",
                    "destination_account": "acc_b",
                    "amount": 1,
                    "currency": "INR",
                },
            )
            for transaction_id in ids
        )
    )
    await asyncio.gather(*(wait_for_processed(client, i) for i in ids))

    assert time.monotonic() - started < settings.processing_delay_seconds * 5


async def test_stale_lease_cannot_complete(client, payload, db):
    await client.post("/v1/webhooks/transactions", json=payload)
    await asyncio.sleep(0.3)

    duration = await repository.complete_transaction(
        client.app.state.worker_pool, payload["transaction_id"], uuid4()
    )

    assert duration is None
    status = await db.fetchval(
        "SELECT status FROM transactions WHERE transaction_id = $1", payload["transaction_id"]
    )
    assert status == "PROCESSING"


async def test_concurrent_claims_never_share_a_row(client, db):
    await db.executemany(
        "INSERT INTO transactions (transaction_id, source_account, destination_account,"
        " amount, currency) VALUES ($1, 'a', 'b', 1, 'INR')",
        [(f"txn_{uuid4().hex}",) for _ in range(30)],
    )

    batches = await asyncio.gather(
        *(repository.claim_transactions(client.app.state.worker_pool, 10, 30) for _ in range(3))
    )
    claimed = [row["transaction_id"] for batch in batches for row in batch]

    assert len(claimed) == len(set(claimed))


async def test_crash_during_delay_recovers(payload, db):
    await db.execute("TRUNCATE transactions")
    port = "18765"
    env = {
        **os.environ,
        "DATABASE_URL": TEST_DATABASE_URL,
        "PROCESSING_DELAY_SECONDS": "2",
        "LEASE_SECONDS": "3",
        "POLL_INTERVAL_SECONDS": "0.1",
        "DB_COMMAND_TIMEOUT_SECONDS": "2",
    }
    command = [
        sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--port", port,
    ]

    async def start_service() -> subprocess.Popen:
        process = subprocess.Popen(
            command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        async with httpx.AsyncClient() as probe:
            for _ in range(100):
                try:
                    await probe.get(f"http://127.0.0.1:{port}/")
                    return process
                except httpx.TransportError:
                    await asyncio.sleep(0.1)
        process.kill()
        raise AssertionError("service did not start")

    first = await start_service()
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            assert (await http.post("/v1/webhooks/transactions", json=payload)).status_code == 202
            while not await db.fetchval(
                "SELECT attempts FROM transactions WHERE transaction_id = $1",
                payload["transaction_id"],
            ):
                await asyncio.sleep(0.05)
    finally:
        first.kill()
        first.wait()

    second = await start_service()
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            transaction = await wait_for_processed(http, payload["transaction_id"], timeout=15)
    finally:
        second.kill()
        second.wait()

    attempts = await db.fetchval(
        "SELECT attempts FROM transactions WHERE transaction_id = $1", payload["transaction_id"]
    )
    assert attempts == 2
    assert transaction["status"] == "PROCESSED"
