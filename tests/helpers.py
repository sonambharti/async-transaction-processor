import asyncio
import time

import httpx


async def wait_for_processed(
    client: httpx.AsyncClient, transaction_id: str, timeout: float = 10
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = await client.get(f"/v1/transactions/{transaction_id}")
        if response.status_code == 200 and response.json()[0]["status"] == "PROCESSED":
            return response.json()[0]
        await asyncio.sleep(0.1)
    raise AssertionError(f"{transaction_id} was not processed within {timeout}s")
