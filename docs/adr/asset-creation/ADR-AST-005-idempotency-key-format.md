# ADR-AST-005 — `Idempotency-Key` header format `<tenant_uuid>:<sha256(body)>` with 24h TTL

**Status**: Accepted
**Date**: 2026-05-03
**Phase**: 250.1.D
**Decision in design.md**: D250.8
**Owners**: Asset-Creation Eng, API Eng, SDK Eng

## Context

Phase 250.1.A introduces async asset creation: `POST /api/v1/assets/data-first/` returns a `WorkflowRun.id` immediately and the actual Asset materialises later. Async APIs need idempotency: retrying a network failure must not create duplicate workflows. Today's `POST /assets/data-first/` has NO idempotency control — a retry creates a duplicate.

## Decision

`POST /api/v1/assets/data-first/` requires an `Idempotency-Key` header. The Hub validates the key format and persists `(key, response)` for 24 hours in Redis under `idempotency:assets:<key> → <response_json>`.

### Format

`<tenant_uuid>:<sha256(canonical_body_bytes)>`

- **`<tenant_uuid>`** — the requesting tenant's UUID. Prevents cross-tenant key collision.
- **`<sha256(canonical_body_bytes)>`** — hex digest of the canonicalised request body (sorted JSON keys; UTF-8 encoded; no trailing whitespace).

Total length: 36 (UUID) + 1 (colon) + 64 (hex) = 101 chars; comfortably under the 256-char header value limit.

### Lookup semantics

Three cases at request time:

1. **Key absent from cache** — process the request normally; on success, cache `(key → response_envelope)` for 24h.
2. **Key present, body-hash matches** — return the cached response envelope verbatim. HTTP status, headers, body all replayed. Set `Idempotent-Replay: true` response header.
3. **Key present, body-hash mismatch** (same key, different body) — HTTP 409 `Conflict` with `{"code": "IDEMPOTENCY_KEY_BODY_MISMATCH", "message": "Idempotency-Key reused with different body"}`. This is the "tenant reused a key by accident" guard.

### TTL

24 hours covers reasonable retry windows (network blip → exponential-backoff retry over minutes to hours; CI-driven retries over a build cycle).

### What about `WorkflowRun.id` reuse?

Distinct concern: same `Idempotency-Key` returns the same `WorkflowRun.id`. Subsequent operations on the run (poll, cancel) work as normal.

## Consequences

### Positive

- Network-retry safety.
- Reuse-with-different-body errors caught (defensive against client-bug).
- Tenant-prefix prevents cross-tenant collision.

### Negative

- Redis storage growth: 1 KB × N requests × 24h. At 100 RPS → ~8 GB/day. Mitigated by Redis TTL eviction.
- Clients MUST generate the key correctly. Mitigation: SDK ships a helper `client.idempotency_key_for(tenant_id, body)`.

### Documentation

[docs/api/idempotency.md](../../api/idempotency.md) is the canonical client-facing reference — includes:
- Format definition
- Lookup-semantics matrix
- TTL behaviour
- SDK helper signature
- Status-code reference

## Alternatives considered

1. **Random UUID idempotency key** — works but doesn't catch body-mismatch; rejected (defensive value of body-hash matters).
2. **No idempotency at all** — rejected; async API + retry is universal pattern; not having idempotency creates bugs.
3. **TTL longer than 24h** — rejected; storage cost grows linearly; 24h is industry-standard (Stripe, Square).

## Verification

- Unit: `test_idempotency_key_replay_returns_cached_response`.
- Unit: `test_idempotency_key_body_mismatch_returns_409`.
- Unit: `test_idempotency_key_ttl_expires_after_24h`.
- Unit: `test_idempotency_key_format_validation_rejects_malformed`.
- Integration: SDK helper produces the canonical key; round-trip works.
- Integration: cross-tenant key collision impossible (tenant A's key collides with tenant B's key only if `sha256(body)` collides AND tenant_uuids match — vanishingly unlikely).
