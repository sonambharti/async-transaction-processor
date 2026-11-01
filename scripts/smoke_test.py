"""Run the brief's single-transaction, duplicate, and concurrency checks on a live service.

Usage: python scripts/smoke_test.py https://your-service.example.com

Latency is measured by scripts/load_test.mjs, because httpx adds its own delay
when it sends many requests at once.
"""

import asyncio
import sys
import time
from uuid import uuid4

import httpx

CONCURRENT_REQUESTS = 100
DUPLICATE_REQUESTS = 10
MAX_WAIT_SECONDS = 45


def new_payload() -> dict:
    return {
        "transaction_id": f"txn_{uuid4().hex}",
        "source_account": "acc_user_789",
        "destination_account": "acc_merchant_456",
        "amount": 1500,
        "currency": "INR",
    }


async def send(client: httpx.AsyncClient, payload: dict) -> tuple[int, float]:
    started = time.perf_counter()
    response = await client.post("/v1/webhooks/transactions", json=payload)
    return response.status_code, (time.perf_counter() - started) * 1000


async def fetch(client: httpx.AsyncClient, transaction_id: str) -> dict:
    response = await client.get(f"/v1/transactions/{transaction_id}")
    response.raise_for_status()
    return response.json()[0]


async def wait_for_processed(client: httpx.AsyncClient, transaction_id: str) -> dict:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        transaction = await fetch(client, transaction_id)
        if transaction["status"] == "PROCESSED":
            return transaction
        await asyncio.sleep(1)
    raise AssertionError(f"{transaction_id} was not processed in {MAX_WAIT_SECONDS}s")


async def single_transaction(client: httpx.AsyncClient) -> None:
    payload = new_payload()
    started = time.monotonic()
    status, latency = await send(client, payload)
    assert status == 202, f"expected 202, got {status}"

    initial = await fetch(client, payload["transaction_id"])
    assert initial["status"] == "PROCESSING" and initial["processed_at"] is None

    await wait_for_processed(client, payload["transaction_id"])
    elapsed = time.monotonic() - started
    assert 29 <= elapsed <= 40, f"processed after {elapsed:.1f}s"
    print(f"PASS single transaction: {latency:.0f} ms ack, processed after {elapsed:.1f}s")


async def duplicate_prevention(client: httpx.AsyncClient) -> None:
    payload = new_payload()
    results = await asyncio.gather(*(send(client, payload) for _ in range(DUPLICATE_REQUESTS)))
    assert {status for status, _ in results} == {202}, results

    first = await wait_for_processed(client, payload["transaction_id"])
    status, _ = await send(client, payload)
    assert status == 202
    assert await fetch(client, payload["transaction_id"]) == first
    print(f"PASS duplicate prevention: {DUPLICATE_REQUESTS} sent, one transaction stored")


async def concurrent_load(client: httpx.AsyncClient) -> None:
    payloads = [new_payload() for _ in range(CONCURRENT_REQUESTS)]
    results = await asyncio.gather(*(send(client, payload) for payload in payloads))

    assert {status for status, _ in results} == {202}, sorted({s for s, _ in results})
    await asyncio.gather(*(wait_for_processed(client, p["transaction_id"]) for p in payloads))
    print(f"PASS concurrent load: {CONCURRENT_REQUESTS} webhooks accepted and processed")


async def main(base_url: str) -> None:
    limits = httpx.Limits(max_connections=CONCURRENT_REQUESTS + 10)
    async with httpx.AsyncClient(base_url=base_url, timeout=10, limits=limits) as client:
        health = await client.get("/")
        assert health.json()["status"] == "HEALTHY", health.text
        print("PASS health check")
        await asyncio.gather(
            single_transaction(client), duplicate_prevention(client), concurrent_load(client)
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1].rstrip("/")))
