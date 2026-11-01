import asyncio

from tests.helpers import wait_for_processed


async def row_for(db, transaction_id):
    return await db.fetchrow(
        "SELECT amount, attempts, processed_at FROM transactions WHERE transaction_id = $1",
        transaction_id,
    )


async def test_sequential_duplicates_process_once(client, payload, db):
    for _ in range(5):
        response = await client.post("/v1/webhooks/transactions", json=payload)
        assert response.status_code == 202

    await wait_for_processed(client, payload["transaction_id"])

    assert await db.fetchval("SELECT count(*) FROM transactions") == 1
    assert (await row_for(db, payload["transaction_id"]))["attempts"] == 1


async def test_concurrent_duplicates_process_once(client, payload, db):
    responses = await asyncio.gather(
        *(client.post("/v1/webhooks/transactions", json=payload) for _ in range(20))
    )

    assert {response.status_code for response in responses} == {202}
    await wait_for_processed(client, payload["transaction_id"])
    assert await db.fetchval("SELECT count(*) FROM transactions") == 1
    assert (await row_for(db, payload["transaction_id"]))["attempts"] == 1


async def test_duplicate_after_processing_changes_nothing(client, payload, db):
    await client.post("/v1/webhooks/transactions", json=payload)
    await wait_for_processed(client, payload["transaction_id"])
    before = await row_for(db, payload["transaction_id"])

    response = await client.post("/v1/webhooks/transactions", json=payload)
    await asyncio.sleep(1.5)

    assert response.status_code == 202
    assert await row_for(db, payload["transaction_id"]) == before


async def test_duplicate_with_different_payload_keeps_first_write(client, payload, db):
    await client.post("/v1/webhooks/transactions", json=payload)

    response = await client.post(
        "/v1/webhooks/transactions", json={**payload, "amount": 9999}
    )

    assert response.status_code == 202
    assert (await row_for(db, payload["transaction_id"]))["amount"] == 1500
