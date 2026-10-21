# ADR-LIN-002 — Lineage snapshot model

**Status:** Accepted (Phase 228 Foundations)
**Date:** 2026-04-30
**Related:** REQ-LIN-001, REQ-LIN-004

## Context

Phase 228 ships time-travel queries (`as_of` parameter on every `LineageService` read method, REQ-LIN-004). The implementation needs a versioning model on the `LineageEdge` table that supports:

- "What was the lineage of contract X two days ago?" — point-in-time queries.
- "When did edge E close?" — audit / compliance queries.
- "How long did edge E exist?" — operational analytics.

Three models are viable:

1. **Audit-event replay** — store every edge mutation as an append-only event, reconstruct state by replaying events up to the `as_of` cutoff.
2. **SCD Type 1 + audit-event log** — keep the current state in `LineageEdge`, log every mutation in a separate audit table.
3. **SCD Type 2 columns on `LineageEdge`** — every edge row carries `valid_from` and `valid_to`; closed edges are retained with `valid_to` set; current edges have `valid_to IS NULL`.

## Decision

**Adopt SCD Type 2 columns on `LineageEdge`.** The model carries:

- `valid_from: DateTimeField(default=DB NOW(), db_index=True)` — when the edge became current.
- `valid_to: DateTimeField(null=True, db_index=True)` — when the edge stopped being current; `NULL` means "still current".

Time-travel queries use the standard SQL pattern:

```sql
WHERE valid_from <= :as_of
  AND (valid_to IS NULL OR valid_to > :as_of)
```

Edge updates are modelled as **close-then-insert**: the existing open row gets its `valid_to` set to `NOW()`, and a new row is inserted with `valid_from = NOW()` and `valid_to = NULL`.

## Consequences

**Positive:**

- Point-in-time queries are a single index scan per the composite index `(source_contract, valid_from, valid_to)` / `(target_contract, valid_from, valid_to)` (defined in REQ-LIN-001).
- The current state is queryable as `WHERE valid_to IS NULL` — the unique-constraint enforces "at most one open row per scope tuple" and prevents the data race where two pods race to insert duplicate open edges.
- Audit trail is implicit: closed rows are retained, and `created_at` / `created_by_run` provide the write-side metadata.
- Cascade-on-tenant-delete is unchanged — closed rows go with the tenant.

**Negative:**

- Storage grows: closed edges are retained. Mitigated by `docs/capacity/lineage-storage.md` (228.0.4) projecting 3-year row count vs RDS instance class. Long-term archival to S3 + cold storage is a follow-up if the row count exceeds budget.
- The signal handler must do the close-then-insert atomically inside the same transaction, otherwise concurrent saves can violate the unique constraint. The composite-index design + `select_for_update(skip_locked=True)` in the backfill (REQ-LIN-003) handles this; the production code path uses `transaction.on_commit` so the diff runs serially per save.

**Neutral:**

- DB-side `NOW()` is mandatory (REQ-LIN-F5-006) — application time is forbidden because clock skew between pods would produce non-monotonic `valid_from` values that break the point-in-time predicate. Pinned by `test_lineage_clock_skew.py` (228.0.23).

## Alternatives Considered

- **Audit-event replay (option 1):** rejected because point-in-time queries become an O(N events since contract creation) replay. For a 3-year-old contract with many edits this is unbounded; the SCD Type 2 model is O(1 index scan) regardless of contract age.
- **SCD Type 1 + separate audit log (option 2):** rejected because it requires JOINs to reconstruct historical state, and joining a wide audit-event table (which carries every mutation across every domain) against `LineageEdge` is slower than a self-contained SCD Type 2 query. The audit log is retained for compliance reporting (`LINEAGE_EDGE_CREATED` / `LINEAGE_EDGE_DELETED` action codes per REQ-LIN-007), but is not the time-travel substrate.
