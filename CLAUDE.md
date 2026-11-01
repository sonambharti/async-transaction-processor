# Project context

Transaction webhook service for the Walnut Folks Group (Confluencr) backend assessment. The brief is `Full Stack Developer Assessment - Backend Task.pdf`.

Read [docs/Memory.md](docs/Memory.md) first for current state and easy-to-miss details. Reasons for choices are in [docs/Decision.md](docs/Decision.md) (D-001 to D-017), and coding rules are in [docs/Rules.md](docs/Rules.md).

This file is public once pushed. Never put passwords, keys, connection strings, or the Supabase project ref here.

## Status (2026-11-01)

- **Done:** FastAPI service, Next.js console, tests, docs, and Supabase connected from local.
- **Last verified:** 32/32 pytest against local Postgres. Smoke test passed against Supabase from local.
- **Remaining, in order:**
  1. Clean `.env.example`: it has a second, incomplete `DATABASE_URL` and an unused `DB_Password`.
  2. Run `git init`, then create the public GitHub repo. Nothing is committed yet.
  3. Deploy the API to Render, the console to Vercel, then set `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL`.
  4. Run the smoke test, then the load test, against the public URL.
  5. Add the public URLs to `README.md`.
- **Not proven:** the 500 ms target on real infrastructure, including a burst of 200 from Frankfurt.
- **To check in Supabase:** Pool Size must be at least 13, and when inactive projects pause.

## Commands

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:create_app --factory --port 8000
.venv\Scripts\python scripts\smoke_test.py http://127.0.0.1:8000
```

`pytest` needs a local Postgres at `postgresql://postgres:postgres@127.0.0.1:55432/webhooks`, or `TEST_DATABASE_URL`. Its fixture truncates `transactions`, so never point it at Supabase. Stop any other API first.

The console runs from `frontend/` with `npm run dev`.

## Setup facts that are easy to lose

- **Regions:** Supabase is in Ireland (`eu-west-1`) and Render is set to Frankfurt (D-017). The Singapore mentioned in D-011 is out of date.
- **Database connection:** use the session pooler on port 5432, with username `postgres.<project-ref>`, an encoded password, and `?sslmode=require`. The direct host has no IPv4 address, which caused `getaddrinfo failed`.
- **`.env`:** it is gitignored and excluded from the Docker image. Its `DB_COMMAND_TIMEOUT_SECONDS=8` is local only, because of the trip to Ireland. Leave it unset on Render so the 0.4 default applies.
- **Shared database:** don't run a local API alongside the deployed one. Their workers would share rows and connections.

## Behavior that can look like a bug

- The console's transaction list comes from browser `localStorage`, because the API has no list endpoint. Rows deleted in Supabase stay visible until the site data is cleared.
- The console generates a new `transaction_id` after each accepted send, so re-clicking Send is not a duplicate. Demonstrate idempotency with **Send duplicates**, which should report one transaction.
- Duplicates return `202` by design. The proof is one row in the database and `transaction.duplicate` in the API log.
- A processing time of 30 to 32 seconds is expected. The brief requires a simulated 30-second delay, and worker polling and database trips add the rest.

## Working agreements

- Commit or push only when the user asks.
- Keep service logic in Python, as the brief requires (D-015).
- To change a decision, add a new entry to `docs/Decision.md` rather than rewriting an old one.
- Update `docs/Memory.md` at the end of each session.
