# Security

This document covers the service's threats, its controls, and the risks accepted for an assessment project. The service handles simulated data, so some gaps are deliberate. Those gaps must be closed before any real payment data is used.

## 1. Scope

**Assets to protect:**
- The database and its credentials
- The accuracy of stored transactions
- Service availability

**Trust boundaries:**
- The public internet to the API. All input is untrusted.
- The service to the database, over an encrypted connection.

## 2. Security posture

The brief defines an unauthenticated API, and its webhook payload carries no signature. A test client must be able to call every endpoint without credentials, so authentication is out of scope ([PRD section 2](PRD.md)).

**Consequence:** the public endpoint is open to anyone with the URL. Use only test data with it.

## 3. Threats and controls

| Threat | Risk here | Control | State |
|---|---|---|---|
| SQL injection | High if unhandled | Bound parameters only | Required |
| Secret leak through the public repo | High | `.env` ignored, `.env.example` has placeholders, repo scanned before publishing | Required |
| Database traffic intercepted | Medium | TLS required on the connection | Required |
| Malformed or oversized input | Medium | Pydantic validation and field and body size limits | Required |
| Internal details leaked in errors | Medium | Generic error responses; details go to logs only | Required |
| Log injection | Low | Structured logs, which escape field values | Required |
| Other websites calling the API from a browser | Low | CORS allows only the origins in `CORS_ORIGINS`; the API is public anyway | Required |
| Script injection through stored values in the console | Medium | React escapes rendered values; the console does not render raw HTML | Required |
| Vulnerable dependencies | Medium | Pinned versions, `pip-audit` before submitting | Required |
| Forged webhooks | High in production | None; see section 4 | Accepted |
| Transaction ID squatting | High in production | None; see section 4 | Accepted |
| Reading any transaction by ID | Medium | Non-sequential IDs only; see section 4 | Accepted |
| Request flooding | Medium | Host-level protection only; see section 4 | Accepted |

## 4. Accepted risks

Each of these is acceptable only because the data is simulated.

| Risk | Impact | Fix for production |
|---|---|---|
| **No webhook signature check.** Anyone can submit a transaction. | Forged records | Verify the processor's HMAC signature, as in section 5 |
| **First write wins on `transaction_id`.** A forged webhook could claim a real ID, and the real one would then be treated as a duplicate. | Wrong stored data | Signature verification removes this attack |
| **Query endpoint has no authentication.** It exposes account IDs and amounts. | Data disclosure | Require authentication, or remove the endpoint, since the brief says it is for testing |
| **No rate limiting.** A flood can fill the table and use up connections. | Lost availability, storage costs | Rate limit at the edge |
| **Public API docs.** FastAPI serves `/docs` and `/openapi.json` by default. | Minor; the API is already public | Disable them in production |

## 5. Webhook signature verification

This is the first control to add if the service ever handles real webhooks. Razorpay signs each webhook with HMAC-SHA256 of the raw request body, using a shared webhook secret, and sends the result in the `X-Razorpay-Signature` header. Confirm the details in Razorpay's current docs when implementing.

```python
expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, signature_header):
    raise HTTPException(status_code=401)
```

- Sign the **raw bytes**. Parsing and re-serializing the JSON changes them.
- Use `hmac.compare_digest`, which is safe against timing attacks.
- Check the signature before validation or any database write.

## 6. Required controls

### Secrets

- [ ] `DATABASE_URL` is set only in `.env` locally and in the host's environment when deployed.
- [ ] `.gitignore` includes `.env` before the first commit.
- [ ] `.env.example` contains placeholders only.
- [ ] The connection string is never logged, including in startup messages and exceptions.
- [ ] The git history has been scanned, for example with `gitleaks`, before the repo goes public.

If a secret is committed, rotate it right away. Deleting it in a later commit does not remove it from history.

### Database

- [ ] The connection requires TLS.
- [ ] The service uses a dedicated role with only the access it needs, rather than the admin role, where the provider allows it.
- [ ] Supabase's auto-generated Data API cannot reach the `transactions` table. `schema.sql` enables row level security with no policies; confirm it in the dashboard after deploying.
- [ ] All queries use bound parameters.

The Data API item is easy to miss. Tables in Supabase's public schema can be exposed through its REST API, and the API's public key is not a secret. Confirm the current behavior in the Supabase dashboard.

### Input

- [ ] Requests with an unknown field or wrong type are handled by the Pydantic models.
- [ ] String fields have a maximum length of 255.
- [ ] `amount` must be greater than 0, and `NaN` and `Infinity` are rejected.
- [ ] Request bodies over 16 KB are rejected. The expected payload is well under this size.

### Errors and logs

- [ ] Unexpected errors return a generic JSON message with no stack trace.
- [ ] Debug mode is off when deployed.
- [ ] Logs contain IDs and events, but no credentials or request headers.

### Dependencies

- [ ] Versions are pinned in `requirements.txt`.
- [ ] `pip-audit` has been run, and any serious findings are resolved.

## 7. Data handling

- Stored fields are account IDs, amounts, and currency. No card numbers, names, or contact details are collected.
- Transport encryption is handled by the host (HTTPS) and the database connection (TLS).
- Encryption at rest is handled by the database provider.
- Data has no retention policy, because this is an assessment. Delete the database after the review.

## 8. Before using real payment data

Treat each of these as a blocker:

1. Add signature verification.
2. Authenticate or remove the query endpoint.
3. Add rate limiting.
4. Disable public API docs.
5. Define data retention and access policies.
6. Add a retry limit and failed state (D-007).
7. Review the applicable compliance obligations, such as PCI DSS and local data protection law.
