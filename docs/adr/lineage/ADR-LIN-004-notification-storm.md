# ADR-LIN-004 — Lineage change-notification storm prevention

**Status:** Accepted (Phase 228 Foundations)
**Date:** 2026-04-30
**Related:** Phase 228 F3 (lineage change notifications, capability flag `lineage.change_notifications`)

## Context

Phase 228 ships lineage change-notifications: when an upstream contract changes, downstream tenants receive an email + in-app notification. Without rate limiting this produces three failure modes:

1. **Mass-replay storm.** A backfill or re-normalization run modifies thousands of edges in seconds; subscribers receive thousands of emails in seconds.
2. **Cascade chains.** A single upstream change triggers dependent edges, each of which triggers further notifications — N levels deep.
3. **Per-edit pinging.** A data engineer iterating on a contract saves 30 times in 10 minutes; each save fires a notification, the consumer marks them all as spam.

## Decision

**Three-layer storm prevention:**

### Layer 1 — Severity gate

A notification is emitted only when the lineage change crosses a **severity threshold**:

- `MAJOR` — edge added/removed where the affected target contract has ≥1 ACTIVE asset OR is published in marketplace. Notify.
- `MINOR` — edge metadata change (e.g., `transformation_ref` updated) without structural change. Suppress.
- `COSMETIC` — `created_by_run` or other audit-only column changed. Suppress.

Severity is computed in the sync handler before emitting the change-notification event; suppressed changes are still recorded in the audit log (`LINEAGE_EDGE_CREATED` / `LINEAGE_EDGE_DELETED`) but do not produce a notification.

### Layer 2 — Per-recipient debounce window

For each `(recipient_user_id, contract_id)` pair, the notification dispatcher tracks the timestamp of the last sent notification. Subsequent notifications for the same pair within a **1-hour window** are coalesced into a single "summary" notification at the end of the window listing every change observed.

Implemented as a Redis sorted-set per recipient with score = next-flush time. The dispatcher worker drains the sorted set every minute and sends the summary email.

### Layer 3 — Opt-in subscription

Recipients are opted in via explicit subscription to `lineage.change.<contract_id>` event types (existing webhook + UserNotification subscription patterns extended). No tenant is auto-subscribed; the subscription is a deliberate ops/customer-success action.

## Consequences

**Positive:**

- Mass-replay storms are converted into a single per-recipient summary email per hour, regardless of how many edges changed.
- The severity gate cuts noise from cosmetic edits without losing the audit trail.
- Opt-in subscription respects customers who want zero lineage notifications (most do not want them on by default).

**Negative:**

- 1-hour delay on the first notification of a window — a customer subscribing for "changes to my upstream" sees the change up to 60 minutes later. Acceptable per Phase 228 product brief; a follow-up phase can ship sub-hour debouncing if customer demand warrants.
- The dispatcher worker is a new failure mode. Mitigated by the existing async-worker framework (ADR-LIN-008) and the dispatcher being idempotent (a double-flush sends the same summary twice with identical event_id, which the existing webhook idempotency guard deduplicates).

**Neutral:**

- The severity classifier lives in `hub/apps/contracts/lineage_severity.py` (Phase 228 F3 implementation, not in 228.0 Foundations).

## Alternatives Considered

- **No rate limiting** — rejected because the storm scenarios above are operationally unacceptable.
- **Token bucket per recipient** — rejected because token-bucket allows bursts (e.g., 10 emails in the first minute, then nothing for the rest of the hour). The 1-hour debounce + summary is more predictable for recipients.
- **Server-Sent Events / WebSocket push only** — rejected because customers want email digests for compliance / audit purposes; a WebSocket push has no archive.
