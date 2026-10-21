# Lineage edge sync drift — runbook

**Phase:** 228 Foundations (228.0.21)
**Owner:** Data Platform Eng
**Severity:** P1 (drift > 1%) / P2 (≤ 1%)
**Last reviewed:** 2026-04-30

## When this runbook fires

The `LineageEdge` table is a derived index of `Contract.hub_contract_json.lineage`. Drift means the relational table no longer matches the JSONB source of truth. Detection comes from:

1. **The `backfill_lineage_edges` post-run verification** ([runbook](lineage-edge-backfill-failure.md)) reporting `DRIFT (json=N edges=M delta=X%)`.
2. **A Grafana alert** on `abs(lineage_edge_open_count - lineage_json_entry_count) / lineage_json_entry_count > 0.01`.
3. **A customer report** that the lineage UI is missing edges they expect to see (or showing edges they have removed).

## TL;DR — recovery

1. Identify drift-positive contracts:

   ```python
   # python /app/hub/manage.py shell
   from hub.apps.contracts.models import Contract
   from hub.apps.contracts.lineage_sync import (
       _desired_edge_set, _current_edge_set,
   )

   drifted = []
   for c in Contract.objects.iterator(chunk_size=500):
       if _desired_edge_set(c) != set(_current_edge_set(c).keys()):
           drifted.append(c.id)
   print(f"drift_count={len(drifted)}")
   ```

2. Re-run the backfill in **dry-run** to preview corrective actions:

   ```bash
   python /app/hub/manage.py backfill_lineage_edges --dry-run
   ```

3. Apply the correction (idempotent, safe under load):

   ```bash
   python /app/hub/manage.py backfill_lineage_edges \
       --resume-key=drift-correction-$(date +%F)
   ```

4. Re-verify:

   ```bash
   python /app/hub/manage.py backfill_lineage_edges --dry-run
   ```

   The verification line should report `verification=ok`.

## Common drift causes

### Cause 1 — Signal handler raised silently mid-batch

**Symptom:** drift correlates with a recent contract-save burst (e.g., a bulk import).

**Investigation:** check structured logs for `lineage_sync_handler_failed`. The handler is required to fail loudly (REQ-LIN-002), so this should never reach production silently — but if logging is misconfigured the failure can be invisible.

**Fix:** the backfill above corrects state. The handler defect is a separate engineering ticket — the runbook is concerned with restoring consistency, not finding the root cause.

### Cause 2 — Direct DB write to `LineageEdge` outside the sync handler

**Symptom:** drift is asymmetric — relational edges exist that the JSONB does not describe.

**Investigation:** `git log -p hub/apps/` for any new code that does `LineageEdge.objects.create()` outside `lineage_sync.py` or `backfill_lineage_edges.py`. Direct writes are a violation of ADR-LIN-001 — only the sync handler and the backfill command may write the table.

**Fix:** revert the offending direct-write code. The backfill command will close the orphan edges on the next pass (the diff sees them as `current - desired` → close).

### Cause 3 — Stale edges on a deleted contract

**Symptom:** drift counts include rows where `source_contract_id IS NULL` (the FK was `SET_NULL` because the source contract was hard-deleted).

**Investigation:** the JSONB on the target side may still reference the deleted contract's UUID.

**Fix:** the customer must edit the lineage in the Schema editor to drop the dangling reference. Until that happens, the runbook accepts the drift as a known data-quality issue (not a bug).

### Cause 4 — Concurrent live save during backfill

**Symptom:** small drift (<1%) immediately after a backfill that ran during business hours.

**Investigation:** the live signal handler likely raced the backfill on a small number of contracts.

**Fix:** re-run the backfill. The second pass corrects any race-induced drift. Schedule future backfills for off-peak hours.

## Escalation thresholds

| Drift % | Severity | Action |
|---|---|---|
| ≤ 1% | P2 | Investigate within 1 business day; correct via backfill. |
| 1% – 5% | P1 | Page `#data-platform-oncall`; correct within 4 hours. |
| > 5% | P0 | Investigate immediately; the diff algorithm itself may be defective. Hold customer-visible lineage UI behind a feature flag until corrected. |

## Related

- [REQ-LIN-002 spec](../../openspec/changes/preprod01/specs/lineage-foundations/spec.md#requirement-signal-driven-lineage-sync-req-lin-002)
- [Backfill failure runbook](lineage-edge-backfill-failure.md)
- [DR runbook](lineage-dr.md)
- [ADR-LIN-001](../adr/lineage/ADR-LIN-001-storage-shape.md) — signal-driven derived table
