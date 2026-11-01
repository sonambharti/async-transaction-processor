# Project rules

These rules apply to anyone working on this project, human or AI. If a rule needs to change, record the reason in [Decision.md](Decision.md) first.

## 1. Core guarantees

Never break these. Each one protects a requirement in the brief.

1. **Return 202 only after the row is committed.** No in-memory buffering of accepted transactions.
2. **Do no processing inside the request.** The webhook only validates and inserts.
3. **Use the database as the source of truth.** No in-memory job lists or duplicate caches.
4. **Let the database enforce idempotency.** Never check for a duplicate with a read before the insert.
5. **Never move a row out of `PROCESSED`.**
6. **Check the lease token in every final update.**

## 2. Async rules

- Do not make blocking calls in async code. This means no `time.sleep`, `requests`, or synchronous database drivers.
- Use `asyncio.sleep` for the delay.
- Do not hold a database connection across the delay. Acquire one, run the query, and release it.
- Keep a reference to every background task so it is not garbage collected, and log its exceptions.
- The worker loop must catch and log errors from each iteration, then continue. Only cancellation can stop it.
- Never swallow `asyncio.CancelledError`, or shutdown will hang.

## 3. Database rules

- All SQL lives in `app/repository.py`.
- Always use bound parameters (`$1`, `$2`). Never build SQL with f-strings or string concatenation.
- Bound every query and every pool acquire with a timeout.
- Use database time (`now()`) for all stored timestamps and lease checks, so there is one clock.
- Store money as `NUMERIC`. Parse it as `Decimal`, and do not do arithmetic on it as a float.
- Keep `schema.sql` idempotent.

## 4. API rules

- Keep paths, field names, and status values exactly as the brief specifies.
- Keep the query endpoint's one-element array.
- Do not return internal columns: `lease_token`, `lease_expires_at`, or `attempts`.
- Format all timestamps as ISO 8601 UTC with a `Z` suffix, in seconds precision as in the brief.
- Return `null` for an unset `processed_at`. Do not leave the field out.
- Keep the status codes to those in PRD section 4.
- `GET /` must not query the database.

## 5. Code style

- Target Python 3.14, with type hints on all functions.
- Use Pydantic models at the API boundary.
- Read configuration only through `app/config.py`, not through `os.environ` elsewhere.
- Add no hardcoded delays, URLs, or limits. Add a setting instead.
- Keep functions small, and comment only on why something non-obvious is done.
- Do not add a dependency, service, or abstraction without a need the PRD can point to.
- Log through the structured events in Architecture section 10. Do not use `print`.

## 6. Testing rules

- Test against a real PostgreSQL instance. Do not mock the database, because the guarantees depend on its behavior.
- Set a short `PROCESSING_DELAY_SECONDS` in automated tests, with a lease longer than that delay.
- Give each test its own unique `transaction_id`, or reset the table between tests.
- Wait for results by polling with a timeout, not with fixed sleeps.
- Stop any other running API before `pytest`, because its worker would claim test rows.
- Measure latency with `scripts/load_test.mjs`. `httpx` adds its own delay under concurrent load.
- Every behavior change needs a test. Every core guarantee in section 1 needs one.
- Before submitting, run the full test plan in PRD section 9 against the public URL, using the real 30-second delay.

## 7. Scope rules

- Build what the PRD asks for. The estimated effort is 2–3 hours.
- Do not add authentication, dashboards, new statuses, or message brokers. If one seems necessary, raise it first.
- Note worthwhile improvements in the README's production follow-ups, not in the code.

## 8. Git rules

- Never commit `.env` or any secret.
- Keep commits small and focused, with messages in the imperative mood.
- Do not commit broken code to the main branch.
- Check the repo for secrets before making it public.

## 9. Documentation rules

- Update [Memory.md](Memory.md) at the end of each working session.
- Add a [Decision.md](Decision.md) entry for any change to the stack, data model, or guarantees.
- If the code and a document disagree, fix one of them in the same change.
- Keep the README's run and test instructions correct at every commit that affects them.

## 10. Before submitting

- [ ] All tests pass locally.
- [ ] The test plan passes against the public URL.
- [ ] The first request after an idle period responds within 500 ms.
- [ ] A fresh clone runs by following the README alone.
- [ ] The README covers run instructions, test instructions, and technical choices.
- [ ] The README contains the public API URL.
- [ ] The repo is public and contains no secrets.
- [ ] The controls in Security section 6 are done.
