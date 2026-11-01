# PRD: Transaction Webhook Service

| | |
|---|---|
| **Source** | Full Stack Developer Assessment - Backend Task (PDF) |
| **Estimated effort** | 2–3 hours |
| **Deadline** | 24–36 hours from receipt |
| **Status** | Draft for implementation |

## 1. Summary

Build a Python service that receives transaction webhooks from payment processors such as Razorpay. It acknowledges each webhook within 500 ms, then processes the transaction in the background with a simulated 30-second external call and stores the result in a cloud database.

Three properties matter most:

- **Fast:** the webhook response never waits for processing.
- **Idempotent:** repeated webhooks with the same `transaction_id` produce one processed transaction.
- **Durable:** once the service returns 202, the transaction survives a crash or restart and still gets processed.

## 2. Goals and non-goals

### Goals

- Implement the three endpoints in the brief, matching its response shapes.
- Process every accepted transaction exactly once from the API consumer's point of view.
- Recover unfinished work automatically after a crash or redeploy.
- Deploy to a public URL, with a public GitHub repo and a README.

### Non-goals

- Real payment logic, ledger updates, or calls to a real external API.
- Webhook signature verification. The brief's payload carries no signature, and a real Razorpay integration would need it. The README lists this as a production follow-up.
- Authentication, rate limiting, or analytics dashboards. The Next.js console is a test tool, not a brief deliverable (D-015).
- Multi-region deployment or horizontal autoscaling. The design tolerates multiple instances, but one is deployed.

## 3. Users

| User | Need |
|---|---|
| Payment processor (webhook sender) | A fast 2xx acknowledgment, safe retries, and a non-2xx response when delivery did not succeed |
| Assessor or tester | Predictable API behavior, a working public URL, and a clear README |

## 4. Functional requirements

### FR-1: Receive a webhook

`POST /v1/webhooks/transactions`

```json
{
  "transaction_id": "txn_abc123def456",
  "source_account": "acc_user_789",
  "destination_account": "acc_merchant_456",
  "amount": 1500,
  "currency": "INR"
}
```

| Case | Response |
|---|---|
| New, valid transaction | `202`, after the row is committed to the database |
| Duplicate `transaction_id`, in any state | `202`, with no state change |
| Malformed or invalid body | `422` |
| Database unavailable or too slow | `503`, so the sender retries |

The response body is a simple acknowledgment:

```json
{ "status": "ACCEPTED", "transaction_id": "txn_abc123def456" }
```

Validation rules:

- All five fields are required.
- `transaction_id`, `source_account`, and `destination_account` are non-empty strings of at most 255 characters.
- `amount` is a number greater than 0, and accepts decimals.
- `currency` is a 3-letter code, normalized to uppercase.

### FR-2: Process in the background

- Each transaction is processed after its webhook is received, independently of the request.
- Processing includes a 30-second delay, set by `PROCESSING_DELAY_SECONDS` (default `30`).
- On completion, the status becomes `PROCESSED` and `processed_at` is set.

### FR-3: Idempotency

- `transaction_id` is the idempotency key, enforced by a database primary key.
- Duplicates return 202 without errors, without a second processing run, and without changing any stored value.
- Concurrent duplicates are safe because the unique constraint decides the winner.
- If a duplicate has a different payload, the first write wins and a warning is logged.

### FR-4: Query a transaction

`GET /v1/transactions/{transaction_id}`

The response is a **single-element array**, as shown in the brief:

```json
[{
  "transaction_id": "txn_abc123def456",
  "source_account": "acc_user_789",
  "destination_account": "acc_merchant_456",
  "amount": 150.50,
  "currency": "USD",
  "status": "PROCESSED",
  "created_at": "2024-01-15T10:30:00Z",
  "processed_at": "2024-01-15T10:30:30Z"
}]
```

- `status` is `PROCESSING` or `PROCESSED`.
- `processed_at` is `null` while processing.
- An unknown ID returns `404` with `{ "detail": "Transaction not found" }`.

### FR-5: Health check

`GET /`

```json
{ "status": "HEALTHY", "current_time": "2024-01-15T10:30:00Z" }
```

This is a liveness check and does not query the database, so a brief database outage does not cause the host to restart a working service.

## 5. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Webhook latency | Under 500 ms, including while many transactions are processing |
| NFR-2 | Durability | No transaction that received a 202 is lost |
| NFR-3 | Processing time | About 30 seconds from receipt with no failures; 30–32 seconds is the expected range |
| NFR-4 | Availability | The deployed service does not sleep when idle, so the first request also meets NFR-1 |
| NFR-5 | Timestamps | ISO 8601 in UTC with a `Z` suffix |
| NFR-6 | Observability | Structured logs for receipt, duplicates, claims, completions, and failures |

## 6. Technical design

### Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | FastAPI on Uvicorn, Python 3.14 | Async I/O, built-in validation, and generated API docs |
| Console | Next.js, in `frontend/` | Optional test UI; all service logic stays in Python (D-015) |
| Database | Managed PostgreSQL (Supabase) | Provides the unique constraint and `FOR UPDATE SKIP LOCKED` |
| Database driver | `asyncpg` with plain SQL | The core queries are Postgres-specific, so an ORM adds little |
| Hosting | Render web service on an always-on instance | Simple Git-based deploys; the host must not sleep (see Risks) |
| Tests | `pytest`, `httpx` | Standard async API testing |

### Architecture: the database is the queue

There is no separate broker. The `transactions` table holds both the result and the pending work, so the 202 and the job are stored in one atomic write. With an in-memory task or a separate queue, a crash between the two steps could lose a transaction.

```text
Processor ──POST──▶ API ──INSERT ... ON CONFLICT DO NOTHING──▶ Postgres
              ◀─202─┘                                             ▲
                                                                  │
                    Worker loop (same process) ──claim, wait 30s, │
                                                 mark PROCESSED───┘
```

The worker is an asyncio task started by the FastAPI lifespan. Running it in the web process keeps deployment to one service. Waiting on `asyncio.sleep` does not block request handling, and durability comes from the database, not the process.

### Data model

```sql
CREATE TABLE transactions (
    transaction_id      TEXT PRIMARY KEY,
    source_account      TEXT NOT NULL,
    destination_account TEXT NOT NULL,
    amount              NUMERIC NOT NULL CHECK (amount > 0),
    currency            CHAR(3) NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PROCESSING'
                        CHECK (status IN ('PROCESSING', 'PROCESSED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at        TIMESTAMPTZ,
    lease_token         UUID,
    lease_expires_at    TIMESTAMPTZ,
    attempts            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_transactions_pending
    ON transactions (lease_expires_at)
    WHERE status = 'PROCESSING';
```

`lease_token`, `lease_expires_at`, and `attempts` are internal and never returned by the API. `amount` is stored as `NUMERIC` to avoid floating-point errors.

### Webhook write

```sql
INSERT INTO transactions
    (transaction_id, source_account, destination_account, amount, currency)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (transaction_id) DO NOTHING;
```

### Worker loop

1. Every second, claim available rows, up to the free concurrency slots:

   ```sql
   WITH claimable AS (
       SELECT transaction_id FROM transactions
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
   RETURNING t.transaction_id, t.lease_token, t.attempts;
   ```

   The CTE stops the planner from re-running the `LIMIT` once per candidate row.

2. Run each claimed job as its own task, and wait out the delay **without holding a database connection**.
3. Finish with a write that checks the lease:

   ```sql
   UPDATE transactions
   SET status = 'PROCESSED', processed_at = now(),
       lease_token = NULL, lease_expires_at = NULL
   WHERE transaction_id = $1
     AND status = 'PROCESSING'
     AND lease_token = $2;
   ```

### Failure handling

| Failure | Behavior |
|---|---|
| Process crashes or redeploys during the delay | The lease expires and the row is claimed again on the next poll |
| Job raises an exception | The error is logged and the row is retried when its lease expires |
| Worker stalls past its lease | Another claim gets a new token, so the stale worker's final update matches no rows |
| Database down during a webhook | Returns `503` and the sender retries; a 202 is never returned without a commit |
| Database down during polling | The loop logs the error, waits, and keeps running |
| SIGTERM on shutdown | Stop claiming new work; in-flight rows recover through lease expiry |

Failed jobs retry indefinitely and keep the `PROCESSING` status. The brief defines no failed state, and the simulated work does not depend on the payload, so every failure here is transient. `attempts` records retries in the logs and database.

A recovered transaction reruns the 30-second delay, so its `processed_at` can be later than usual. Across a crash, processing is at-least-once and the stored result is exactly-once. A real external call would need to pass `transaction_id` as its own idempotency key.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | Required | Postgres connection string |
| `PROCESSING_DELAY_SECONDS` | `30` | Simulated external call; lowered in tests |
| `LEASE_SECONDS` | `60` | Must be longer than the processing delay |
| `POLL_INTERVAL_SECONDS` | `1` | Worker polling frequency |
| `WORKER_CONCURRENCY` | `200` | Maximum jobs in flight |
| `DB_COMMAND_TIMEOUT_SECONDS` | `0.4` | Limits the webhook's database wait, so it can return 503 inside the 500 ms budget |
| `API_POOL_SIZE` | `10` | Webhook and query connections |
| `WORKER_POOL_SIZE` | `3` | Worker connections |
| `CORS_ORIGINS` | Empty | Comma-separated browser origins, such as the console's URL |

The API and the worker use separate connection pools, so worker queries cannot starve webhook requests.

## 7. Interpretation of the brief

The brief is ambiguous in these places. Each decision below is the one to implement, and the README should mention them.

| Issue in the brief | Decision |
|---|---|
| The query response is an array, though the ID is unique | Return a one-element array, matching the brief exactly |
| `amount` is `1500` in one example and `150.50` in another | Accept integers and decimals; return a JSON number |
| The health response sample has a trailing comma, which is invalid JSON | Return valid JSON with the same two fields |
| No behavior is given for an unknown transaction ID | Return `404` |
| "Must return 202" does not cover invalid input | Return `422` for invalid bodies |
| "Must respond within 500ms" and "doesn't lose transactions" conflict during a database outage | Prefer no data loss: return `503` quickly, not a false 202 |
| Only `PROCESSING` and `PROCESSED` are listed | Keep these two public statuses; retries stay in `PROCESSING` |

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The host sleeps when idle, as Render's free tier does | Cold starts break the 500 ms target, and polling stops | Use an always-on plan, and confirm the plan's current behavior before deploying |
| The database suspends when idle, as some free tiers do | The first query is slow | Use Supabase, and the worker's one-second polling keeps it active; confirm this against free-tier limits |
| App and database are in different regions | Each insert costs more of the 500 ms budget | Deploy both in the same region, and measure from the public URL |
| A connection pooler in transaction mode | `asyncpg` prepared statements can fail | Use Supabase's session-mode pooler, or set `statement_cache_size=0` |
| A burst exceeds `WORKER_CONCURRENCY` | Later jobs take longer than 30 seconds, but none are lost | The default of 200 allows about 400 transactions per minute |

## 9. Test plan

These map directly to the brief's success criteria.

| # | Criterion | Test | Pass condition |
|---|---|---|---|
| 1 | Single transaction | Send one webhook, then query it immediately and again after 32 seconds | `PROCESSING` with null `processed_at`, then `PROCESSED` about 30 seconds after `created_at` |
| 2 | Duplicate prevention | Send the same webhook 10 times, sequentially and concurrently, including after it has processed | Every call returns 202, one row exists, `attempts` is 1, and `processed_at` does not change |
| 3 | Performance | Send 100 concurrent webhooks with distinct IDs against the deployed URL, while earlier jobs are in flight | All return 202, each under 500 ms; all reach `PROCESSED` |
| 4 | Reliability | Kill the process during a delay, then restart it | The transaction reaches `PROCESSED`, with `attempts` of 2 |
| 5 | Validation | Send missing fields, a zero or negative amount, and a bad currency | `422`, with no row created |
| 6 | Query and health | Query an unknown ID, then call `GET /` | `404`, then `200` with `HEALTHY` and a current UTC time |

Automated tests run against a real Postgres instance with a short `PROCESSING_DELAY_SECONDS`. Tests 1–3 are repeated manually against the deployed service with the real 30-second delay.

## 10. Deliverables

- [ ] Public GitHub repository containing the working Python application
- [ ] README with instructions to run and test the service
- [ ] README with a brief explanation of technical choices, including section 7
- [ ] Public API endpoint deployed on the cloud, with its URL in the README

## 11. Implementation plan

| Step | Work | Estimate |
|---|---|---|
| 1 | Project setup, configuration, schema, and database pools | 25 min |
| 2 | Three endpoints with validation and error handling | 30 min |
| 3 | Worker loop, leases, and shutdown | 40 min |
| 4 | Automated tests, including duplicates and crash recovery | 35 min |
| 5 | Provision the database, deploy, and run the test plan on the live URL | 30 min |
| 6 | README and final check of the deliverables | 20 min |

## 12. Definition of done

- All six tests in section 9 pass, and tests 1–3 also pass against the public URL.
- A fresh clone can be run locally by following the README alone.
- The repository contains no secrets, and `DATABASE_URL` is set only in the host's environment.
