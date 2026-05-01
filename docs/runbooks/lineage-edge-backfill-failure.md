# Lineage edge backfill — failure runbook

**Phase:** 228 Foundations (228.0.11, REQ-LIN-003)
**Owner:** Data Platform Eng
**Severity:** P2 by default (P1 if customer-visible lineage UI is empty)
**Last reviewed:** 2026-04-30

## When this runbook fires

The `backfill_lineage_edges` management command runs as a one-shot, off-peak job per tenant. Failure modes:

1. **The command exited non-zero.** Check stdout for the failed contract ID + error message.
2. **The command finished cleanly but verification reported `DRIFT`.** Open-edge count diverges from JSON-lineage-entry count beyond the ±0.1% tolerance.
3. **The command was killed mid-run** (SIGKILL, OOM, pod eviction). Recoverable via `--resume-key`.

## TL;DR — recovery commands

### Resume after crash

```bash
# If you ran with --resume-key=<key>, just rerun with the same key.
python manage.py backfill_lineage_edges \
    --tenant=<TENANT_UUID> \
    --resume-key=lineage-backfill-${TENANT_UUID}-$(date +%F)

# If you didn't use --resume-key originally, the safe move is to
# re-run from the start. The command is idempotent — already-correct
# rows are noop'd, drift is corrected.
python manage.py backfill_lineage_edges --tenant=<TENANT_UUID>
```

### Investigate verification drift

```bash
# Re-run with verbose output and the dry-run flag to see the per-row plan.
python manage.py backfill_lineage_edges --tenant=<TENANT_UUID> --dry-run

# Compare open-edge count to expected JSON-lineage-entry count manually:
python manage.py shell -c "
from hub.apps.contracts.models import Contract, LineageEdge
from hub.apps.contracts.lineage_sync import _desired_edge_set

t = '<TENANT_UUID>'
edges = LineageEdge.objects.filter(tenant_id=t, valid_to__isnull=True).count()
json = sum(len(_desired_edge_set(c)) for c in Contract.objects.filter(tenant_id=t))
print(f'edges_open={edges} json_entries={json} delta={abs(edges-json)}')
"
```

### Find which contracts have drift

```python
# In python manage.py shell:
from hub.apps.contracts.models import Contract, LineageEdge
from hub.apps.contracts.lineage_sync import _desired_edge_set, _current_edge_set

for c in Contract.objects.filter(tenant_id="<TENANT_UUID>"):
    desired = _desired_edge_set(c)
    current = set(_current_edge_set(c).keys())
    if desired != current:
        print(f"DRIFT contract={c.id}")
        print(f"  desired - current = {desired - current}")
        print(f"  current - desired = {current - desired}")
```

## Common failure modes + fixes

### Fix 1 — Stale `hub_contract_json.lineage` references a deleted contract

**Symptom:** the backfill creates an open edge with `source_contract_id=NULL` (FK was `SET_NULL` because the source contract is deleted) but the JSON entry references a UUID that no longer maps to any row.

**Action:** Decide whether the stale reference is in scope for the live data product:

- If the source contract was deleted intentionally, run the contract owner through the Schema editor to remove the dangling lineage entry; the next live save fixes the JSON.
- If the source contract was deleted in error, restore from the prior contract row (`Contract.all_objects.filter(id=<id>)` if soft-delete is in use).

### Fix 2 — JSON references a UUID that has never existed

**Symptom:** verification reports `json > edges` and the diff shows entries with no source contract row at all (typo / hand-edited contract).

**Action:** the JSON is malformed. Use the Schema editor to clean up the contract's `lineage` block; rerun the backfill.

### Fix 3 — Concurrent live writes during backfill

**Symptom:** verification reports a small drift (<1%) immediately after a backfill that ran during business hours.

**Action:** the live signal handler may have raced the backfill on a small number of contracts. Re-run the backfill; the second pass corrects any race-induced drift. If the drift recurs, schedule the backfill for off-peak hours.

### Fix 4 — `--resume-key` crashed but Redis lost the checkpoint

**Symptom:** Redis was restarted between the crash and the recovery; the resume-key has expired (default 24h TTL).

**Action:** restart from the beginning. The idempotency invariant means already-processed contracts are noop'd; the cost is a slower but correct rerun.

## Escalation

If verification reports drift > 1% or the same drift recurs after two reruns, escalate to `#data-platform-oncall` with:

- The tenant id.
- The verification line: `edges=<n> json=<n> delta=<percent>`.
- The list of drift-positive contract ids from the "Find which contracts have drift" snippet above.

The platform team treats >1% drift as a P1 because it indicates a defect in the diff algorithm (the signal handler + backfill share `_sync_contract_edges`, so divergence implies a logic bug, not transient state).

## Related

- [REQ-LIN-003 spec](../../openspec/changes/preprod01/specs/lineage-foundations/spec.md#requirement-idempotent-lineage-edge-backfill-req-lin-003)
- [ADR-LIN-001 storage shape](../adr/lineage/ADR-LIN-001-storage-shape.md)
- [ADR-LIN-008 async-workers](../adr/lineage/ADR-LIN-008-async-workers.md)
- Source: [`hub/apps/contracts/management/commands/backfill_lineage_edges.py`](../../hub/apps/contracts/management/commands/backfill_lineage_edges.py)
