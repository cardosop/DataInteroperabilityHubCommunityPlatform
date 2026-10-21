# ADR-DSF-003 — Purge idempotency + distributed locks

**Status**: Accepted (Phase 260.0)

## Decision

Destructive storage sweeps MUST wrap work in `hub.apps.core.distributed_lock` (Redis `SET` + tokenised Lua release) to avoid duplicate deletions.

## Consequences

Depends on cache Redis availability; extend TTL for long sweeps.

