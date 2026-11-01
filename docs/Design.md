# Design System: Webhook Console

## Status and scope

The brief is backend-only, and a UI is not one of its deliverables. This document specifies the developer console built in `frontend/` (see D-015 in [Decision.md](Decision.md)). The API must work and pass its tests without it.

The console is one page that lets a person demonstrate the service: send a webhook, watch it move from `PROCESSING` to `PROCESSED`, prove duplicates are ignored, and see response times.

| Constraint | Reason |
|---|---|
| Next.js app in `frontend/`, deployed separately | Requested stack; the service stays in Python |
| Rendered only in the browser | It reads `localStorage` and generates random IDs |
| No UI library | Plain CSS with the tokens below is enough for one page |
| Uses only the three existing API endpoints | The UI must not change the API |
| Calls the API directly, with CORS | A proxy would hide the true webhook latency |

## 1. Visual theme and atmosphere

A calm instrument panel: quiet neutral surfaces, monospaced data, and color reserved for meaning. The page should feel like a well-made developer tool, closer to a good API client than a marketing dashboard. The eye should go straight to the status of a transaction.

| Dial | Level | Meaning here |
|---|---|---|
| Density | 7 of 10 | Balanced to dense; the data is the content |
| Variance | 3 of 10 | Predictable, because this is a working tool |
| Motion | 3 of 10 | Motion appears only when it reports a change |

The console has **no hero section**. The tool is the first thing on the page.

Light and dark themes are both supported. The page follows the system setting, and a header control can override it.

## 2. Color palette and roles

All neutrals are from one Zinc scale. There is one accent. Status colors carry meaning only and never decorate.

### Neutrals

| Name | Light | Dark | Role |
|---|---|---|---|
| Canvas | `#FAFAFA` | `#111113` | Page background |
| Surface | `#FFFFFF` | `#18181B` | Panels and inputs |
| Sunken | `#F4F4F5` | `#212124` | Code blocks and table header |
| Hairline | `#E4E4E7` | `#2E2E33` | Borders and dividers |
| Ink | `#18181B` | `#F4F4F5` | Primary text |
| Muted Steel | `#5F5F68` | `#A1A1AA` | Labels, metadata, and secondary text |

### Accent

| Name | Light | Dark | Role |
|---|---|---|---|
| Ledger Blue | `#1D5FA8` | `#7FB2E5` | Primary button, focus ring, and links |
| On Accent | `#FFFFFF` | `#111113` | Text on the accent |

### Status

| Meaning | Light text | Light background | Dark text | Dark background | Used for |
|---|---|---|---|---|---|
| Processing | `#8A5300` | `#FDF3E1` | `#F0B861` | `#33260F` | `PROCESSING` |
| Processed | `#1B6B3A` | `#E7F5EC` | `#74CC97` | `#12301F` | `PROCESSED`, `HEALTHY` |
| Error | `#B3261E` | `#FCEBEA` | `#F2968F` | `#3A1715` | 4xx, 5xx, and connection failures |

Status is always shown with a text label as well as color.

### CSS tokens

```css
:root {
  --canvas: #FAFAFA; --surface: #FFFFFF; --sunken: #F4F4F5;
  --hairline: #E4E4E7; --ink: #18181B; --muted: #5F5F68;
  --accent: #1D5FA8; --on-accent: #FFFFFF;
  --processing: #8A5300; --processing-bg: #FDF3E1;
  --processed: #1B6B3A; --processed-bg: #E7F5EC;
  --error: #B3261E; --error-bg: #FCEBEA;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --canvas: #111113; --surface: #18181B; --sunken: #212124;
    --hairline: #2E2E33; --ink: #F4F4F5; --muted: #A1A1AA;
    --accent: #7FB2E5; --on-accent: #111113;
    --processing: #F0B861; --processing-bg: #33260F;
    --processed: #74CC97; --processed-bg: #12301F;
    --error: #F2968F; --error-bg: #3A1715;
  }
}
```

Repeat the dark values under `:root[data-theme="dark"]` so the manual control works.

## 3. Typography rules

| Role | Font | Size | Weight |
|---|---|---|---|
| Page title | Geist | 1.25rem (20px) | 600 |
| Section heading | Geist | 0.875rem (14px) | 600 |
| Body and labels | Geist | 0.875rem (14px) | 400 to 500 |
| Metadata | Geist | 0.75rem (12px) | 400 |
| Data and code | Geist Mono | 0.8125rem (13px) | 400 |
| Elapsed timer | Geist Mono | 1.125rem (18px) | 500 |

- Load both fonts with `next/font/google`, with `system-ui` and `ui-monospace` as fallbacks.
- Use Geist Mono for IDs, amounts, timestamps, latencies, and JSON.
- Use `font-variant-numeric: tabular-nums` so timers do not shift as they count.
- Build hierarchy through weight and color, not large sizes.
- Serif fonts and Inter are not used.

## 4. Spacing, shape, and depth

| Token | Value |
|---|---|
| Spacing scale | 4, 8, 12, 16, 24, 32px |
| Control and badge radius | 6px |
| Panel radius | 8px |
| Control height | 36px on desktop, 44px on touch screens |
| Page max width | 1200px |

Panels use a 1px Hairline border and no shadow. Depth comes from the Canvas, Surface, and Sunken layers.

## 5. Layout

```text
┌───────────────────────────────────────────────────────────────────┐
│ Webhook Console                   ● HEALTHY  12:30:45 UTC  [Theme]│
├──────────────────────────┬────────────────────────────────────────┤
│ SEND WEBHOOK             │ TRANSACTIONS                           │
│ transaction_id   [Regen] │ ID            Amount   Status   Elapsed│
│ [txn_8f3k2m9q        ]   │ txn_8f3k...   1500 INR PROCESSING  18s │
│ source_account           │ ████████████░░░░░░░░░                  │
│ [acc_user_789        ]   │ txn_p2x7...   150.50   PROCESSED   30s │
│ destination_account      │                                        │
│ [acc_merchant_456    ]   ├────────────────────────────────────────┤
│ amount       currency    │ DETAILS: txn_8f3k2m9q                  │
│ [1500   ]    [INR]       │ { raw JSON from the query endpoint }   │
│                          │                                        │
│ [Send webhook]           │                                        │
│ [Send duplicates: 10]    │                                        │
├──────────────────────────┴────────────────────────────────────────┤
│ REQUEST LOG                                                       │
│ 12:30:44  POST /v1/webhooks/transactions   202   84 ms            │
└───────────────────────────────────────────────────────────────────┘
```

- Use CSS Grid, with a 5 to 7 split between the form and the tracker.
- Below 768px, everything collapses to one column in this order: health, form, transactions, details, log.
- The page must never scroll horizontally. Long IDs truncate in the middle on screen, and show in full in the details panel.
- Use `min-height: 100dvh`, not `100vh`.

## 6. Components

**Primary button.** Ledger Blue fill with On Accent text. Hover darkens it slightly, and active moves it down 1px. Used once, for "Send webhook".

**Secondary button.** Transparent with a Hairline border. Used for "Send duplicates" and "Regenerate".

**Inputs.** Label above, error text below, and no floating labels. The focus ring is 2px Ledger Blue. ID, account, and amount fields use Geist Mono. Validation messages from a `422` appear under the matching field.

**Status badge.** Text in capitals, using the status text and background pair. A `PROCESSING` badge has a small pulsing dot, which is the page's only continuous animation.

**Progress line.** A 2px line under a `PROCESSING` row, filling across 30 seconds from the time the browser sent the webhook. It is not a progress measurement, so at 30 seconds it stops at full and waits for the actual status. It disappears at `PROCESSED`.

**Elapsed timer.** Counts up from the send time while processing, so a wrong device clock does not skew it. It then shows the final duration from `created_at` and `processed_at`.

**Resend.** A secondary button in the details panel that sends the same transaction again, to show a duplicate changes nothing.

**Health indicator.** A dot, `HEALTHY`, and `current_time`. If the check fails it shows `UNREACHABLE` in Error color.

**Request log.** Time, method, path, status, and latency, newest first, keeping the last 50 entries. Latency of 500 ms or more shows in Error color.

**Duplicate result.** After "Send duplicates", a summary line appears under the form: `10 sent, 10 accepted, 1 transaction, slowest 142 ms`. These figures must come from the real responses.

## 7. Behavior

| Item | Rule |
|---|---|
| Health | Call `GET /` every 10 seconds |
| Transaction status | Call the query endpoint every 2 seconds per `PROCESSING` row; stop at `PROCESSED` |
| Transaction list | The API has no list endpoint, so the page tracks IDs it sent and stores them in `localStorage` |
| Latency | Measured with `performance.now()` around each `fetch` |
| Duplicates | Sent with the same payload using `Promise.all` |
| Default ID | Generated on page load and after each send, for example `txn_8f3k2m9q` |

`localStorage` calls must be wrapped in `try/catch`, and the page must work without it.

## 8. Interface states

| State | Treatment |
|---|---|
| Empty list | "No transactions yet. Send a webhook to start tracking one." |
| Loading | A skeleton row in the same layout; no circular spinners |
| Sending | Button disabled, label changes to "Sending" |
| `202` | New row at the top of the list |
| `422` | Field-level errors; no row added |
| `503` | Banner: "The service could not save this transaction. Nothing was stored, so it is safe to send again." |
| Network failure | Banner: "Could not reach the service." Polling continues and clears it on recovery |
| Tracked ID returns `404` | Row marked "Not found", for example after the database was reset |

## 9. Motion

- Use CSS only, with no animation library.
- Durations are 120–200 ms with `ease-out`. The progress line is the exception and runs linearly, because it represents elapsed time.
- New rows fade in and move up 4px, and a status change cross-fades the badge.
- Animate only `transform` and `opacity`.
- Under `prefers-reduced-motion: reduce`, remove the pulse and transitions. The timer and status still update.

## 10. Accessibility

- All text meets WCAG AA contrast, at least 4.5:1, against its own background.
- The whole page works by keyboard, with a visible focus ring on each control.
- Every input has a real `<label>`.
- Status changes are announced through an `aria-live="polite"` region.
- Touch targets are at least 44px below 768px.

## 11. Security

- Render all response data with `textContent`, never `innerHTML`, so stored values cannot run as script.
- The console holds no secrets and adds no special access, because the API is already public (see [Security.md](Security.md)).
- Show a short note in the footer: "Use test data only."

## 12. Anti-patterns

Never do these:

- Emojis, gradient text, neon glows, or colored shadows
- Purple or neon blue, or a second accent color
- Pure black (`#000000`)
- Three equal cards in a row, or decorative statistic tiles
- Invented figures. Every number must come from a real response
- Circular spinners or custom cursors
- Status shown by color alone
- Marketing copy such as "seamless" or "next-gen"
- Placeholder names such as "John Doe" or "Acme"
