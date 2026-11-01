# Project memory

This is the working record for the project. Read it first when starting a session, and update it at the end of one. It holds current state, facts that are easy to forget, and session history.

It does not repeat other documents:

| For | See |
|---|---|
| Requirements | [PRD.md](PRD.md) |
| System design | [Architecture.md](Architecture.md) |
| Why a choice was made | [Decision.md](Decision.md) |
| How to write code here | [Rules.md](Rules.md) |
| Threats and controls | [Security.md](Security.md) |
| Optional console UI | [Design.md](Design.md) |

## Current state

**Last updated:** 2026-10-31

**Phase:** Built and tested locally. Publishing and deployment remain.

| Item | State |
|---|---|
| Project documents | Done |
| Backend | Done |
| Next.js console | Done |
| Tests | Passing locally |
| README | Done, except the public URLs |
| Git repository | Not initialized |
| Cloud database | Not provisioned |
| Deployment | Not started |

**Next step:** Create the GitHub repo, provision Supabase, deploy to Render and Vercel, then run the smoke and load tests against the public URL.

## Project facts

- **Assessment:** Fullstack Engineer Assessment, backend task, from the Walnut Folks Group (Confluencr).
- **Brief:** `Full Stack Developer Assessment - Backend Task.pdf` in the project root.
- **Estimated effort:** 2–3 hours.
- **Deadline:** 24–36 hours after receiving the task. The PDF was saved on 2026-10-31 at about 16:28, but the exact start time is not recorded.
- **Submission:** public GitHub repo plus a public API URL.

## Details that are easy to get wrong

- The query endpoint returns an **array** with one object, even though the ID is unique.
- The health endpoint is at the root path, `GET /`, and returns `HEALTHY`, not `OK`.
- The status code is `202`, not `200` or `201`, including for duplicates.
- `amount` can be an integer or a decimal.
- `processed_at` must be `null` until processing finishes, not omitted.
- `LEASE_SECONDS` must stay longer than `PROCESSING_DELAY_SECONDS`.
- The delay must use `asyncio.sleep`. `time.sleep` would freeze the API.
- The worker must not hold a connection during the delay.
- Crash recovery is tested by restarting the service during a delay and waiting up to about 90 seconds.
- The app starts through a factory: `uvicorn app.main:create_app --factory`.
- Two local APIs sharing a database will claim each other's rows. Stop other instances before `pytest`.
- `httpx` reports misleadingly high latency under concurrent load. Use `scripts/load_test.mjs`.
- The load test leaves 500 rows queued, so run the smoke test first.

## Items to confirm

| Item | Blocks | Related decision |
|---|---|---|
| Render plan behavior and price | Deployment | D-010 |
| Supabase limits, connection limits, and IPv4 access | Deployment | D-011 |
| Render and Supabase regions match | Meeting the 500 ms target | D-010, D-011 |

## Deployment details

Fill these in once they exist. Never record secrets here, because this file is public.

| Item | Value |
|---|---|
| GitHub repo URL | Not created |
| Public API URL | Not deployed |
| Render region | Not chosen |
| Supabase region | Not chosen |

## Session log

Add new entries at the top. Keep each one to what changed and anything the next session needs.

### 2026-10-31: Build

- Built the FastAPI service and Next.js console. Service logic stays in Python, as the brief requires (D-015).
- A burst of 200 returned 503s with 5 connections, so the defaults became 10 connections and 400 ms (D-016).
- Tested a real PostgreSQL outage and a process kill during the delay. No transaction was lost.

### 2026-10-31: Planning

- Read the assessment brief.
- Wrote the PRD, then Architecture, Decision, Memory, Rules, and Security documents.
- Chose Supabase over Neon, because the worker polls constantly (D-011), and updated the PRD to match.
- Added Design.md for an optional developer console, to build only after the required deliverables (D-014).
- No code written yet.
