# Architecture: Transaction Webhook Service

This document describes how the system is built. Requirements live in [PRD.md](PRD.md), and the reasons behind each choice live in [Decision.md](Decision.md). SQL for the schema and worker queries is in PRD section 6.

## 1. System overview

The service is one Python process connected to one managed PostgreSQL database. The process runs the HTTP API and a background worker. The database stores results and also acts as the job queue. An optional Next.js console in `frontend/` is a static client of the public API (D-015), and the service does not depend on it.

```text
                     ┌──────────────── Web process (Render) ───────────────┐
                     │                                                     │
Payment processor ──▶│  FastAPI routes ──▶ API pool ───────────┐           │
Tester / client   ◀──│                                         │           │
                     │  Worker loop ─────▶ Worker pool ────────┤           │
                     │    └─ job tasks (asyncio.sleep)         │           │
                     └─────────────────────────────────────────┼───────────┘
                                                               ▼
                                                 ┌───────────────────────┐
                                                 │ PostgreSQL (Supabase) │
                                                 │ transactions table    │
                                                 └───────────────────────┘
```

## 2. Components

| Component | Responsibility | Must not |
|---|---|---|
| API routes | Validate input, commit the row, return a response | Wait for processing |
| Worker loop | Poll for available rows and start job tasks | Stop on an error |
| Job task | Wait out the delay and write the final result | Hold a database connection during the delay |
| Repository | Hold all SQL in one place | Contain business decisions |
| PostgreSQL | Enforce uniqueness and store durable state | Be bypassed by in-memory state |

## 3. Project layout

```text
.
├── app/
│   ├── main.py          # App creation, lifespan, error handlers
│   ├── api.py           # The three routes
│   ├── config.py        # Environment settings
│   ├── db.py            # Connection pools
│   ├── log.py           # Structured logging
│   ├── models.py        # Pydantic request and response models
│   ├── repository.py    # All SQL queries
│   └── worker.py        # Polling loop and job tasks
├── frontend/            # Next.js console
├── scripts/             # Live smoke and load tests
├── tests/
├── docs/
├── schema.sql           # Idempotent schema, applied on startup
├── Dockerfile
├── render.yaml
├── requirements.txt
└── README.md
```

## 4. Transaction lifecycle

The public API has two statuses. Internally, a `PROCESSING` row is either available or leased.

```text
webhook accepted
      │
      ▼
┌───────────────────────┐   worker claims   ┌────────────────────┐
│ PROCESSING, available │ ────────────────▶ │ PROCESSING, leased │
└───────────────────────┘                   └────────────────────┘
      ▲                                        │             │
      │          lease expires                 │             │ final update
      └────────────────────────────────────────┘             │ matches token
                                                             ▼
                                                     ┌───────────────┐
                                                     │  PROCESSED    │
                                                     └───────────────┘
```

`PROCESSED` is terminal. Nothing moves a row out of it.

## 5. Request flows

### New webhook

1. Pydantic validates the body. Invalid input returns `422` and touches nothing.
2. The route runs `INSERT ... ON CONFLICT DO NOTHING`.
3. After the commit, the route returns `202`.

### Duplicate webhook

The insert affects zero rows. The same statement also returns the stored row, so the route logs a warning if the payload differs, with no second round trip. It returns `202` either way and changes nothing.

### Background processing

1. The worker polls each second and claims up to its number of free concurrency slots.
2. Each claimed row gets a new `lease_token` and starts a job task.
3. The task sleeps for `PROCESSING_DELAY_SECONDS` with no connection held.
4. The task runs the final update, which matches only if the row still has its token.
5. Zero rows updated means the lease moved to a newer claim, so the task exits quietly.

### Crash recovery

No startup recovery step exists. After a restart, the normal claim query finds rows whose lease has expired, so recovery and regular processing use the same code path.

## 6. Timing

### Webhook budget (500 ms)

| Step | Target |
|---|---|
| Host routing and validation | Under 50 ms |
| Acquire a connection and run the insert | Up to 400 ms, then `503` |
| Network return and margin | The remainder |

`DB_COMMAND_TIMEOUT_SECONDS` bounds the connection wait and the query together, so a full pool cannot wait past the budget. API connections stay open, because opening a new TLS connection would use up the budget.

### Processing time

| Scenario | Time from `created_at` to `processed_at` |
|---|---|
| Normal | 30–32 seconds: up to 1 second of polling, the delay, and the write |
| One crash during the delay | Up to about 90 seconds: the 60-second lease expires, then a full rerun of the delay |
| Backlog above concurrency | Longer, until a slot is free |

## 7. Concurrency and capacity

- `asyncio.sleep` lets one process hold hundreds of waiting jobs at little cost, so the delay does not slow the API.
- At 200 slots and 30 seconds per job, throughput is about 400 transactions per minute.
- `FOR UPDATE SKIP LOCKED` keeps claims safe if a second instance is ever added. Only one is deployed.

| Connection pool | Size | Reason |
|---|---|---|
| API | 10 | Each webhook holds a connection for one short query (D-016) |
| Worker | 3 | Short claim and completion queries only |

Together, the pools must stay under the database plan's connection limit. Keeping them separate means a worker burst cannot delay a webhook.

## 8. Application startup and shutdown

**Startup, in the FastAPI lifespan:**

1. Load and validate settings.
2. Create both connection pools.
3. Apply `schema.sql`.
4. Start the worker loop.

**Shutdown:**

1. Stop claiming new rows.
2. Cancel in-flight job tasks.
3. Close the pools.

Cancelled rows recover when their lease expires, so shutdown does not need to wait 30 seconds for jobs to finish.

## 9. Deployment

| Item | Value |
|---|---|
| Host | Render web service on an always-on plan, one instance, built from the `Dockerfile` |
| Start command | `uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT` |
| Console | Vercel, with `NEXT_PUBLIC_API_URL` set to the API URL |
| Uvicorn workers | One |
| Health check path | `/` |
| Database | Supabase Postgres, in the same region as the service |
| Connection | Supabase session-mode pooler, with TLS required |
| Secrets | `DATABASE_URL` in the host's environment only |

Multiple Uvicorn workers would still be safe because of `SKIP LOCKED`, but they would multiply the connection pools and add no benefit here.

## 10. Observability

Logs are structured and written to stdout, where the host collects them.

| Event | Level | Key fields |
|---|---|---|
| `transaction.received` | INFO | `transaction_id` |
| `transaction.duplicate` | INFO, or WARNING if the payload differs | `transaction_id` |
| `transaction.claimed` | INFO | `transaction_id`, `attempts` |
| `transaction.processed` | INFO | `transaction_id`, `duration_seconds` |
| `transaction.lease_lost` | WARNING | `transaction_id` |
| `worker.error` | ERROR | Exception details |

## 11. Limits of this design

- Polling adds up to one second of delay and keeps a steady, light load on the database.
- Crash recovery takes up to the full lease period.
- Sustained traffic well above 400 transactions per minute would need a dedicated worker service and a real broker.
- A deadline for a real external call would need a more careful lease, because the simulated delay is always fixed.
