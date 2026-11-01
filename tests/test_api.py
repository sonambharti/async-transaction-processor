import re
from uuid import uuid4

import pytest

from app import repository

TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
INTERNAL_FIELDS = {"lease_token", "lease_expires_at", "attempts"}


async def test_health(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "current_time"}
    assert response.json()["status"] == "HEALTHY"
    assert TIMESTAMP.match(response.json()["current_time"])


async def test_webhook_is_accepted_and_starts_processing(client, payload):
    response = await client.post("/v1/webhooks/transactions", json=payload)

    assert response.status_code == 202
    assert response.json() == {"status": "ACCEPTED", "transaction_id": payload["transaction_id"]}

    query = await client.get(f"/v1/transactions/{payload['transaction_id']}")
    assert query.status_code == 200
    assert isinstance(query.json(), list) and len(query.json()) == 1
    transaction = query.json()[0]
    assert transaction["status"] == "PROCESSING"
    assert transaction["processed_at"] is None
    assert transaction["amount"] == 1500
    assert TIMESTAMP.match(transaction["created_at"])
    assert not INTERNAL_FIELDS & set(transaction)


async def test_decimal_amount_round_trips(client, payload):
    payload.update(amount=150.50, currency="usd")

    await client.post("/v1/webhooks/transactions", json=payload)

    transaction = (await client.get(f"/v1/transactions/{payload['transaction_id']}")).json()[0]
    assert transaction["amount"] == 150.50
    assert transaction["currency"] == "USD"


async def test_unknown_transaction_returns_404(client):
    response = await client.get(f"/v1/transactions/txn_{uuid4().hex}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Transaction not found"}


async def test_nul_in_path_returns_404(client):
    assert (await client.get("/v1/transactions/txn%00bad")).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"amount": 0},
        {"amount": -5},
        {"amount": "NaN"},
        {"amount": True},
        {"currency": "RUPEE"},
        {"currency": "12A"},
        {"transaction_id": ""},
        {"transaction_id": "   "},
        {"transaction_id": "x" * 256},
        {"transaction_id": "txn\x00bad"},
    ],
)
async def test_invalid_body_returns_422_and_stores_nothing(client, payload, db, change):
    payload.update(change)

    response = await client.post("/v1/webhooks/transactions", json=payload)

    assert response.status_code == 422
    assert await db.fetchval("SELECT count(*) FROM transactions") == 0


@pytest.mark.parametrize(
    "field", ["transaction_id", "source_account", "destination_account", "amount", "currency"]
)
async def test_missing_field_returns_422(client, payload, field):
    del payload[field]

    assert (await client.post("/v1/webhooks/transactions", json=payload)).status_code == 422


async def test_oversized_body_returns_413(client, payload):
    payload["padding"] = "x" * 20_000

    assert (await client.post("/v1/webhooks/transactions", json=payload)).status_code == 413


async def test_oversized_chunked_body_returns_413(client):
    async def chunks():
        for _ in range(20):
            yield b"x" * 1024

    response = await client.post("/v1/webhooks/transactions", content=chunks())

    assert response.status_code == 413


async def test_database_failure_returns_503(client, payload, monkeypatch):
    async def fail(*args):
        raise TimeoutError

    monkeypatch.setattr(repository, "insert_transaction", fail)

    response = await client.post("/v1/webhooks/transactions", json=payload)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
