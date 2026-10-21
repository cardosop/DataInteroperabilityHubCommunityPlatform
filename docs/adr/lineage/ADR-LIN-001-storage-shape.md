# ADR-LIN-001 — Lineage storage shape

**Status:** Accepted (Phase 228 Foundations)
**Date:** 2026-04-30
**Related:** REQ-LIN-001, REQ-LIN-002

## Context

Lineage relationships have been stored in the canonical `Contract.hub_contract_json.lineage` JSONB tree since Phase 26. Read-side service methods (`LineageService.get_full_lineage`, `…get_visualization`, etc.) parse the tree on every request. As the contract-corpus grows the JSON-parse-per-read cost dominates query latency, and the tree-walking code cannot exploit a relational index for "all contracts that reference X" or "all edges of type=transformation in tenant T".

Two storage shapes are viable:

1. **JSONB-only (status quo)** — keep `hub_contract_json.lineage` as the authoritative source and parse it at read time.
2. **Pure relational** — replace `hub_contract_json.lineage` with first-class FKs and ORM models, dropping the JSONB.
3. **JSONB canonical + signal-driven derived `LineageEdge`** — keep JSONB authoritative for writes; derive a read-optimised `LineageEdge` table via `post_save` signal handler. Reads use the index; writes use the JSONB.

## Decision

**Adopt option 3.** The canonical write shape stays JSONB; we add a derived `LineageEdge` relational table maintained by a `post_save` signal handler.

The `LineageEdge` table is **read-only from application code** outside the sync handler. Application writers update `hub_contract_json.lineage`; the signal computes the diff and applies edge-create / edge-close operations transactionally.

## Consequences

**Positive:**

- Read-path queries hit a B-tree index; "all edges into contract X" is `WHERE target_contract_id = X` instead of a Python tree-walk over every contract row.
- The relational shape supports SCD Type 2 (ADR-LIN-002) and time-travel queries naturally (`valid_from`, `valid_to` columns).
- Tenant-cascade is enforced by the FK (`on_delete=CASCADE`) — no application code required.
- The JSONB stays the source of truth, so existing webhook payloads, audit events, and offline analytics that read `hub_contract_json.lineage` continue to work unchanged.

**Negative:**

- Sync drift: a malformed signal handler can leave the relational table inconsistent with JSONB. Mitigated by:
  - The `backfill_lineage_edges` management command (REQ-LIN-003) which is idempotent and resumable.
  - The `lineage-edge-sync-drift` runbook (228.0.21).
  - The `lineage_edge_writes_total` metric (228.0.19) which surfaces noop/add/remove ratios.
- Double-write cost: every Contract save writes JSONB AND the derived edges. Mitigated by `transaction.on_commit()` so the request thread is not blocked by the diff.

**Neutral:**

- Storage cost: estimated ~120 bytes per edge × 3-year row count. See `docs/capacity/lineage-storage.md`.

## Alternatives Considered

- **Pure relational (option 2):** rejected because it forces a coordinated migration of every consumer of `hub_contract_json.lineage` (webhooks, offline analytics, the SDK that ships JSON envelopes verbatim, the OpenLineage adapter). The signal-driven derived table reaches read-performance parity without breaking those consumers.
- **JSONB-only (option 1):** rejected because it does not satisfy REQ-LIN-004 (time-travel) — JSONB has no version-history semantics; we would need an audit-event-replay scheme that is far slower than SCD Type 2 over an indexed table.
- **Eventual-consistency via Kafka** (queue the sync rather than emit it synchronously on commit): rejected for Phase 228 because the diff handler is fast (<5 ms for typical contracts) and `transaction.on_commit` already removes it from the request critical path. Revisit if profiling shows the sync is a hot path.
