# Decision log

Each entry records a technical decision and why it was made, so it is not reopened without new information.

**Status values:** `Accepted` is final unless new facts appear. `Provisional` depends on something that still needs checking. `Superseded` has been replaced by a later entry.

To change a decision, add a new entry and mark the old one `Superseded`. Do not rewrite old entries.

| ID | Decision | Status |
|---|---|---|
| D-001 | Use FastAPI on Uvicorn | Accepted |
| D-002 | Use PostgreSQL | Accepted |
| D-003 | Use the database as the job queue | Accepted |
| D-004 | Run the worker in the web process | Accepted |
| D-005 | Claim work with leases and `SKIP LOCKED` | Accepted |
| D-006 | Enforce idempotency with the primary key | Accepted |
| D-007 | Keep failed jobs in `PROCESSING` and retry | Accepted |
| D-008 | Use `asyncpg` with plain SQL | Accepted |
| D-009 | Return 503 when the row cannot be saved | Accepted |
| D-010 | Host on Render's always-on plan | Provisional |
| D-011 | Use Supabase through the session pooler | Provisional |
| D-012 | Apply the schema on startup, without a migration tool | Accepted |
| D-013 | Follow the brief's response shapes exactly | Accepted |
| D-014 | Treat the developer console as optional | Superseded by D-015 |
| D-015 | Build the console in Next.js and keep the service in Python | Accepted |
| D-016 | Use 10 API connections and a 400 ms database budget | Accepted |

---

## D-001: Use FastAPI on Uvicorn

**Context:** The brief allows any Python framework. The API is small, and the worker needs to wait on many jobs at once.

**Decision:** Use FastAPI on Uvicorn.

**Alternatives:**
- Flask or Django: synchronous by default, so many concurrent waits are harder to manage, and more setup is needed.

**Consequences:** Validation and API docs come built in. All I/O must be async, because one blocking call stalls both the API and the worker.

## D-002: Use PostgreSQL

**Context:** The service needs durable storage, a uniqueness guarantee, and safe concurrent claims.

**Decision:** Use managed PostgreSQL.

**Alternatives:**
- MongoDB or DynamoDB: both can enforce unique keys, but claiming work safely needs more custom logic.
- Redis as primary storage: durability depends on its configuration.

**Consequences:** One system handles results, uniqueness, and the queue.

## D-003: Use the database as the job queue

**Context:** A transaction must not be lost after the 202 is returned.

**Decision:** Treat the `transactions` table as the queue. The webhook's single insert stores the result row and the pending work together.

**Alternatives:**
- FastAPI `BackgroundTasks` or plain `asyncio.create_task`: rejected, because a crash loses in-memory work.
- Celery with Redis, or Amazon SQS: durable and well proven, but they add infrastructure. Writing to the database and a separate queue also creates a gap where a crash can leave them out of step.

**Consequences:** Fewer moving parts and no gap between the two writes. Polling adds up to a second of delay. This suits assessment-scale traffic, not very high volume.

## D-004: Run the worker in the web process

**Context:** A separate worker means a second deployed service, and possibly a second paid instance.

**Decision:** Start the worker as an asyncio task inside the FastAPI lifespan.

**Alternatives:**
- A separate worker service: better isolation and independent scaling, but too much for this scope.

**Consequences:** Deployment stays simple, and the in-flight work is safe because state lives in the database. API and worker share one event loop, so D-001's no-blocking rule is essential. Moving the worker out later requires only a new entry point.

## D-005: Claim work with leases and `SKIP LOCKED`

**Context:** The worker must not hold a database transaction or connection through a 30-second delay, yet a crashed job must become available again.

**Decision:** A claim writes a `lease_token` and `lease_expires_at`, then commits. The final update matches on that token. Expired leases can be claimed again. `FOR UPDATE SKIP LOCKED` stops two claimers taking the same row.

**Alternatives:**
- Hold a row lock during the delay: ties up one connection per job, which free-tier connection limits cannot support.
- A plain "in progress" flag: a crash would leave rows stuck forever.

**Consequences:** Recovery needs no special code. The lease must always be longer than the delay, and `LEASE_SECONDS` defaults to 60 for this reason. Recovery can take up to a full lease.

## D-006: Enforce idempotency with the primary key

**Context:** Concurrent duplicates can arrive within milliseconds of each other.

**Decision:** Use `transaction_id` as the primary key and insert with `ON CONFLICT DO NOTHING`. Duplicates return 202. If a duplicate's payload differs, the first write wins and a warning is logged.

**Alternatives:**
- Read first, then insert: two concurrent requests can both pass the read.
- A Redis idempotency cache: adds a system without adding a stronger guarantee.

**Consequences:** The database decides every race. Processors get a success response for retries, so they stop resending.

## D-007: Keep failed jobs in `PROCESSING` and retry

**Context:** The brief defines only `PROCESSING` and `PROCESSED`, and requires that transactions are not lost.

**Decision:** On failure, log the error and let the lease expire. There is no `FAILED` status and no retry limit. `attempts` records the count.

**Alternatives:**
- Add a `FAILED` status with a dead-letter process: useful with real external calls, but it extends the brief's API contract with no failure to report.

**Consequences:** The worker stays small. The simulated job does not depend on the payload, so a job that can never succeed cannot occur. **Real payment processing would need a retry limit and a failed state.**

## D-008: Use `asyncpg` with plain SQL

**Context:** The core queries rely on `ON CONFLICT` and `SKIP LOCKED`.

**Decision:** Use `asyncpg` directly, with all SQL in `repository.py`.

**Alternatives:**
- SQLAlchemy: supports these features, but adds setup and hides the queries that matter most.

**Consequences:** Queries are easy to review. Parameter binding is required everywhere (see [Rules.md](Rules.md)).

## D-009: Return 503 when the row cannot be saved

**Context:** The brief asks for 202 within 500 ms and asks that no transaction is lost. If the database is down, both cannot be satisfied.

**Decision:** Prefer durability. A short timeout fails the request with `503`, so the sender retries.

**Alternatives:**
- Buffer in memory and return 202: the service would promise something a crash can break.

**Consequences:** A 202 always means the row is committed. This relies on the sender retrying non-2xx responses, which is standard webhook behavior.

## D-010: Host on Render's always-on plan

**Context:** The service must run continuously, because the worker needs to poll and the first request must meet the 500 ms target.

**Decision:** Deploy one Render web service on a plan that does not sleep. Render's free tier is ruled out because it spins down when idle.

**Alternatives:**
- Google Cloud Run: scale-to-zero and CPU throttling would need configuring away.
- Fly.io or Railway: also suitable, so either is a valid fallback.

**Consequences:** This is likely a paid plan. **Check before deploying:** current plan behavior and price. These facts come from general knowledge, not current vendor docs.

## D-011: Use Supabase through the session pooler

**Context:** The worker polls every second, around the clock. Neon's free tier bills compute by active time, and constant polling could use up its allowance. Supabase's free tier runs a compute instance continuously and pauses only after long inactivity.

**Decision:** Use Supabase Postgres, in the same region as Render (Singapore), connected through the session-mode pooler on port 5432. Supabase's docs confirm this mode supports prepared statements and IPv4 on every plan, while the direct connection needs IPv6 or a paid add-on.

**Alternatives:**
- Neon: a good database, but a weaker fit for constant polling.
- Transaction-mode pooling: requires disabling `asyncpg`'s statement cache.

**Consequences:** In session mode, the dashboard's Pool Size caps connections, and the service uses up to 13. **Check before deploying:** the project's Pool Size and inactivity rules. The code depends only on PostgreSQL, so changing provider means changing `DATABASE_URL`.

## D-012: Apply the schema on startup, without a migration tool

**Context:** The project has one table, and setup should be a single step.

**Decision:** Keep an idempotent `schema.sql` (using `IF NOT EXISTS`) and run it in the lifespan.

**Alternatives:**
- Alembic: the right tool when a schema changes over time, but unnecessary for one table.

**Consequences:** A fresh clone runs without extra steps. Later schema changes would need a migration tool.

## D-013: Follow the brief's response shapes exactly

**Context:** The solution may be tested by automated scripts, and the brief has a few oddities (see PRD section 7).

**Decision:** Keep the brief's shapes, including the one-element array from the query endpoint. The only exception is the health sample's trailing comma, because that is invalid JSON.

**Alternatives:**
- Return a plain object from the query endpoint: cleaner API design, but it could fail a test written against the brief.

**Consequences:** The API is slightly unusual, and the README explains why.

## D-014: Treat the developer console as optional

**Context:** The brief is backend-only and the PRD lists a frontend as a non-goal, but a UI design was requested for the project, which is a fullstack role assessment.

**Decision:** Specify a one-page console in [Design.md](Design.md). Build it only after the PRD deliverables are complete. It is one static file at `GET /console`, and uses only the existing endpoints.

**Alternatives:**
- A React or Next.js frontend: a second deployment and a build step, for no gain on one page.
- Serving it at `GET /`: rejected, because that path must return the JSON health check.

**Consequences:** The PRD's scope and API do not change, and a skipped console costs nothing. It stays outside the 2–3 hour estimate.

## D-015: Build the console in Next.js and keep the service in Python

**Context:** Next.js was requested for the assignment. The brief requires a "working Python application", and a 30-second background job suits serverless Next.js hosting poorly.

**Decision:** The API, worker, and storage stay in FastAPI, unchanged. The console is a Next.js app in `frontend/`, built as a static page and deployed separately. It calls the public API directly, with CORS allowing its origin. This replaces D-014's single static file served by FastAPI.

**Alternatives:**
- Rewrite the whole service in Next.js: rejected, because it would fail the brief's Python requirement.
- Proxy API calls through Next.js: adds a hop, so the console could not show true webhook latency.

**Consequences:** The project has two deployments. The console stays optional, and the API meets the brief without it. Browser latency figures can be slower than the server's, because browsers limit connections per host.

## D-016: Use 10 API connections and a 400 ms database budget

**Context:** With 5 connections and a 300 ms budget, a burst of 200 webhooks returned some 503s, because requests waited too long for a connection.

**Decision:** Default to 10 API connections and a 400 ms budget. Both are configurable.

**Alternatives:**
- Disable `synchronous_commit` for faster inserts: rejected, because a 202 must mean the row is durable.

**Consequences:** Local bursts of 200 return all 202s, the slowest at 299 ms. Together with the worker pool, the service can use 13 connections, which must fit the database plan. A remote database adds a network round trip to each insert, so measure on the deployed service.
