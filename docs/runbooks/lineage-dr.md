# Lineage — Disaster Recovery runbook

**Phase:** 228 Foundations (228.0.22)
**Owner:** Data Platform Eng + SRE
**Severity:** P0 (full DR scenario only)
**Last reviewed:** 2026-04-30

## Scope

Recovery of the **lineage feature surface** after a catastrophic event. The lineage feature has two persistence surfaces:

1. **`Contract.hub_contract_json.lineage`** — the canonical write source. Lives in the same RDS Postgres instance as every other Meshant tenant data; recovery is governed by the existing `docs/runbooks/destroy-staging.md` + RDS PITR procedure.
2. **`LineageEdge`** — the derived signal-driven index. Idempotent and reproducible from the JSONB source via the backfill command; **does NOT need its own DR backup**.

This runbook covers the lineage-specific steps that ride on top of the platform DR procedure.

## DR scenarios

### Scenario A — RDS instance lost, restored from PITR

**Action:** the RDS PITR restore brings back BOTH `hub_contract_json` AND `LineageEdge` to the same point in time. No lineage-specific steps required. Verify post-restore:

```bash
python /app/hub/manage.py backfill_lineage_edges --dry-run
```

The verification line should report `verification=ok` if the PITR snapshot was internally consistent (which RDS guarantees by snapshotting the Postgres WAL position).

### Scenario B — `LineageEdge` table corrupted, `hub_contract_json` intact

**Action:** rebuild `LineageEdge` from the JSONB source. The relational table is a derived index — it can be reconstructed without data loss.

```bash
# 1. Truncate the table (corrupted rows are unrecoverable; the JSONB
#    has the canonical state).
python /app/hub/manage.py shell -c "
from hub.apps.contracts.models import LineageEdge
LineageEdge.objects.all().delete()
"

# 2. Rebuild via the idempotent backfill.
python /app/hub/manage.py backfill_lineage_edges \
    --resume-key=dr-rebuild-$(date +%F)

# 3. Verify.
python /app/hub/manage.py backfill_lineage_edges --dry-run
```

**Estimated rebuild time:** ~10 minutes per 10,000 contracts on the prod RDS instance class.

### Scenario C — `hub_contract_json` corrupted, `LineageEdge` intact

**Action:** the relational `LineageEdge` table is the **only remaining source of truth**. Use it to reconstruct the JSONB lineage subtree.

```python
# In python /app/hub/manage.py shell:
from hub.apps.contracts.models import Contract, LineageEdge

for c in Contract.objects.iterator(chunk_size=500):
    edges = LineageEdge.objects.filter(target_contract=c, valid_to__isnull=True)
    contracts = [
        {
            "source_contract": str(e.source_contract_id) if e.source_contract_id else None,
            "target_contract": str(c.id),
            "edge_type": e.edge_type,
            "transformation_ref": e.transformation_ref,
            "job_ref": e.job_ref,
        }
        for e in edges
    ]
    if contracts:
        payload = c.hub_contract_json or {}
        payload.setdefault("lineage", {})["contracts"] = contracts
        c.hub_contract_json = payload
        c.save(update_fields=["hub_contract_json"])
```

**Caveat:** this restores the **lineage subtree** only — the rest of `hub_contract_json` (models, schema, info) cannot be reconstructed from `LineageEdge`. For full `hub_contract_json` recovery, restore from RDS PITR.

### Scenario D — Both surfaces lost (full data loss)

**Action:** restore from RDS PITR per `docs/runbooks/destroy-staging.md` § "Recovery from snapshot". Then run scenario B's verification step.

## Pre-DR drills

A quarterly DR drill SHALL exercise scenario B in staging:

1. Snapshot the staging `LineageEdge` row count before the drill.
2. Truncate the table.
3. Run the backfill.
4. Verify the post-drill row count matches the pre-drill count within ±0.1% (the `--dry-run` verification line).

The drill confirms the backfill remains idempotent + the storage projection stays accurate. Failed drills route to `#data-platform-oncall` as a P1.

## Related

- [Backfill failure runbook](lineage-edge-backfill-failure.md)
- [Sync drift runbook](lineage-edge-sync-drift.md)
- [ADR-LIN-001](../adr/lineage/ADR-LIN-001-storage-shape.md) — derived-table doctrine (the foundation of this DR plan)
- [Capacity plan](../capacity/lineage-storage.md) — row count projections used to estimate rebuild time
- Platform DR baseline: `docs/runbooks/destroy-staging.md` (RDS PITR procedure)
