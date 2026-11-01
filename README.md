# Transaction Webhook Service

A Python service that receives transaction webhooks, acknowledges them within 500 ms, and processes them reliably in the background. A Next.js console lets you send webhooks and watch them being processed.

| | URL |
|---|---|
| **Public API** | _Add after deploying_ |
| **Console** | _Add after deploying_ |

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/webhooks/transactions` | Accept a webhook. Returns `202`, including for duplicates |
| `GET` | `/v1/transactions/{transaction_id}` | Return the transaction as a one-element array, or `404` |
| `GET` | `/` | Health check |

```bash
curl -X POST "$API_URL/v1/webhooks/transactions" \
  -H "Content-Type: application/json" \
  -d '{"transaction_id":"txn_abc123def456","source_account":"acc_user_789","destination_account":"acc_merchant_456","amount":1500,"currency":"INR"}'

curl "$API_URL/v1/transactions/txn_abc123def456"
```

The status is `PROCESSING` straight away and `PROCESSED` about 30 seconds later.

Other responses: `422` for an invalid body, `413` for a body over 16 KB, and `503` if the transaction could not be saved. A `503` means nothing was stored, so the sender should retry.

## Run locally

You need Python 3.14, Node 24, and Docker.

```bash
# 1. Start PostgreSQL
docker run -d --name webhook-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=webhooks \
  -p 55432:5432 postgres:17-alpine

# 2. Start the API on http://localhost:8000
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
echo "CORS_ORIGINS=http://localhost:3000" >> .env
uvicorn app.main:create_app --factory --port 8000

# 3. Start the console on http://localhost:3000, in a second terminal
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

The schema is applied automatically when the API starts.

## Test

**Automated tests** run against a real PostgreSQL database with a short delay. Stop any local API first, because its worker would claim the test rows.

```bash
pytest
```

**Live checks** work against any URL, using the real 30-second delay:

```bash
python scripts/smoke_test.py http://localhost:8000    # single, duplicate, concurrent
node scripts/load_test.mjs http://localhost:8000      # latency under bursts
```

Run the smoke test first. The load test queues 500 transactions, and they delay any later checks until they finish.

## Technical choices

- **FastAPI with `asyncpg`.** The work is almost all waiting, so async fits. A 30-second wait uses almost no resources, and plain SQL keeps the key queries visible.
- **PostgreSQL as both store and queue.** The webhook's single insert saves the transaction and its pending work together. There is no moment where one exists without the other, and no broker to run. A 202 is only returned after the commit.
- **Idempotency through the primary key.** `INSERT ... ON CONFLICT DO NOTHING` lets the database decide every race, so concurrent duplicates are safe. If a duplicate's payload differs, the first write wins and a warning is logged.
- **Leases for reliability.** The worker runs inside the web process and claims rows with `FOR UPDATE SKIP LOCKED` and a 60-second lease. It holds no connection during the delay. If the process dies, the lease expires and the row is picked up again. The final write checks a lease token, so a stale worker cannot complete a row twice.
- **503 over a false 202.** If the database is down, the 500 ms target and "never lose a transaction" conflict. The service fails fast with `503`, so the sender retries.
- **Next.js for the console only.** The brief requires a Python application, so all service logic is in FastAPI. The console is a static client of the public API.

### How the brief was interpreted

- The query endpoint returns a one-element array, as in the brief's sample.
- `amount` accepts integers and decimals.
- The health sample's trailing comma is invalid JSON, so the response is valid JSON with the same fields.
- An unknown ID returns `404`, and an invalid body returns `422`.
- Failed jobs stay `PROCESSING` and retry, because the brief defines only two statuses.

### Tested behavior

| Scenario | Result |
|---|---|
| Bursts of 100 and 200 concurrent webhooks, local Docker | All `202`; slowest 299 ms |
| 10 concurrent duplicates | One transaction |
| Process killed during the delay | Reprocessed after the lease expired |
| PostgreSQL stopped during the delay | `503` within about 420 ms; health stayed up; the transaction completed after recovery |

These latencies are local. A deployed service adds network time, so run `load_test.mjs` against the public URL to measure it.

## Limits and production follow-ups

The API is public and unauthenticated, as the brief defines, so use only test data.

- Verify webhook signatures. This also stops forged webhooks claiming a real `transaction_id`.
- Add authentication and rate limiting.
- Add a retry limit and failed state once real external calls exist.
- Move the worker to its own service for sustained traffic above about 400 transactions per minute.

See [docs/](docs/) for the PRD, architecture, decisions, and security notes.
