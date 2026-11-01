from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.models import WebhookIn

INSERT_TRANSACTION = """
WITH inserted AS (
    INSERT INTO transactions
        (transaction_id, source_account, destination_account, amount, currency)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (transaction_id) DO NOTHING
    RETURNING 1
)
SELECT
    EXISTS (SELECT 1 FROM inserted) AS is_new,
    existing.source_account,
    existing.destination_account,
    existing.amount,
    existing.currency
FROM (SELECT 1) AS anchor
LEFT JOIN transactions AS existing ON existing.transaction_id = $1
"""

SELECT_TRANSACTION = """
SELECT transaction_id, source_account, destination_account, amount, currency,
       status, created_at, processed_at
FROM transactions
WHERE transaction_id = $1
"""

# The CTE stops the planner from re-running the LIMIT once per candidate row.
CLAIM_TRANSACTIONS = """
WITH claimable AS (
    SELECT transaction_id
    FROM transactions
    WHERE status = 'PROCESSING'
      AND (lease_expires_at IS NULL OR lease_expires_at < now())
    ORDER BY created_at
    LIMIT $1
    FOR UPDATE SKIP LOCKED
)
UPDATE transactions AS t
SET lease_token = gen_random_uuid(),
    lease_expires_at = now() + make_interval(secs => $2),
    attempts = t.attempts + 1
FROM claimable
WHERE t.transaction_id = claimable.transaction_id
RETURNING t.transaction_id, t.lease_token, t.attempts
"""

COMPLETE_TRANSACTION = """
UPDATE transactions
SET status = 'PROCESSED', processed_at = now(),
    lease_token = NULL, lease_expires_at = NULL
WHERE transaction_id = $1
  AND status = 'PROCESSING'
  AND lease_token = $2
RETURNING EXTRACT(EPOCH FROM processed_at - created_at)::float8 AS duration_seconds
"""


@dataclass(frozen=True)
class InsertResult:
    is_new: bool
    payload_differs: bool


async def insert_transaction(pool: asyncpg.Pool, webhook: WebhookIn) -> InsertResult:
    row = await pool.fetchrow(
        INSERT_TRANSACTION,
        webhook.transaction_id,
        webhook.source_account,
        webhook.destination_account,
        webhook.amount,
        webhook.currency,
    )
    if row["is_new"]:
        return InsertResult(is_new=True, payload_differs=False)

    # A concurrent insert may not be visible to this statement's snapshot.
    payload_differs = row["amount"] is not None and (
        row["source_account"] != webhook.source_account
        or row["destination_account"] != webhook.destination_account
        or row["amount"] != webhook.amount
        or row["currency"] != webhook.currency
    )
    return InsertResult(is_new=False, payload_differs=payload_differs)


async def get_transaction(pool: asyncpg.Pool, transaction_id: str) -> asyncpg.Record | None:
    return await pool.fetchrow(SELECT_TRANSACTION, transaction_id)


async def claim_transactions(
    pool: asyncpg.Pool, limit: int, lease_seconds: float
) -> list[asyncpg.Record]:
    return await pool.fetch(CLAIM_TRANSACTIONS, limit, lease_seconds)


async def complete_transaction(
    pool: asyncpg.Pool, transaction_id: str, lease_token: UUID
) -> float | None:
    """Return the duration, or None if this worker no longer holds the lease."""
    return await pool.fetchval(COMPLETE_TRANSACTION, transaction_id, lease_token)
