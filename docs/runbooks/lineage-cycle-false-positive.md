# Lineage cycle false-positive runbook

**Phase:** 228 X (228.X.6.7)
**Owner:** Data Platform Eng
**Last reviewed:** 2026-05-01

The lineage cycle detector (REQ-LIN-007 / 228.0.5) walks the
`LineageEdge` graph and flags strongly-connected components as
cycles. Most cycles ARE bugs — they break impact analysis and
loop the visualization renderer. But three cohorts trip
false-positives that ops needs to disposition without panicking:

1. **Same-name cohort ambiguity.** Two contracts share the same
   declarative `name` across tenants → the cycle detector treats
   them as one node and finds an apparent loop.
2. **Reference-edges across tenant marketplace listings.** A
   marketplace consumer inherits an upstream pointer that points
   back to a sibling-listing in the consumer's own tenant.
   Topologically a cycle; semantically intentional.
3. **Self-edges by design.** A contract that includes itself as a
   reference (e.g. snapshot semantics) is one node + one edge to
   itself — strictly a cycle but operational by design.

## Detect

The detector emits the audit-action `LINEAGE_CYCLE_DETECTED`
(see [hub/apps/audit/models.py](../../hub/apps/audit/models.py)).
Page on:

- `LINEAGE_CYCLE_DETECTED` audit rate > 5/hour for any tenant.
- The `lineage_cycle_detected_total{cohort=...}` counter (added
  in 228.0.5) exceeds the per-cohort threshold.

## Triage

```bash
# Inspect the most recent flagged cycle.
kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
from hub.apps.audit.models import AuditEvent
import json
ev = AuditEvent.objects.filter(action='LINEAGE_CYCLE_DETECTED').order_by('-timestamp').first()
print(json.dumps({'tenant': str(ev.tenant_id), 'details': ev.details}))
"

# Cross-check the reported edges against the relational index.
kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
from hub.apps.contracts.models import LineageEdge
from django.db.models import Q
TENANT='<tenant-uuid>'
qs = LineageEdge.objects.filter(tenant_id=TENANT, valid_to__isnull=True)
for r in qs:
    print(r.source_contract_id, '→', r.target_contract_id, r.edge_type)
"
```

## Disposition

### Cohort 1 — same-name ambiguity

The detector should already key on `contract.id`, not `name`. If
a same-name false-positive appears, it's a regression. **Fix the
detector**, not the data:

1. Capture the offending audit row + the edges from triage.
2. Open a P2 issue against `lineage-cycle-detector`.
3. Suppress the alert for the affected tenant via:
   ```bash
   kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
   from hub.apps.contracts.models import Contract
   Contract.objects.filter(tenant_id='<id>', name='<dup-name>').update(
       cycle_detector_suppress=True,
   )
   "
   ```
   (Field added by Phase 228.0.5 for exactly this case.)

### Cohort 2 — marketplace cross-tenant pointer

This is intentional — the marketplace consumer wants to express
"my asset comes FROM listing X which itself originated from a
sibling listing". Mark these edges with
`edge_type='reference'` AND `transformation_ref='marketplace'`;
the detector skips edges with that combination by design (see
`is_marketplace_pointer()` in
[hub/apps/contracts/lineage_validator.py](../../hub/apps/contracts/lineage_validator.py)).

If the false-positive persists, the edge isn't tagged
`marketplace` — backfill:

```bash
kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
from hub.apps.contracts.models import LineageEdge
LineageEdge.objects.filter(
    target_contract_id='<consumer-listing-id>',
    edge_type='reference',
    transformation_ref='',
).update(transformation_ref='marketplace')
"
```

### Cohort 3 — self-reference by design

Snapshot-semantics contracts may legitimately reference
themselves. The detector skips self-edges where
`source_contract_id == target_contract_id` AND
`edge_type='reference'`. If the false-positive escapes this
filter, capture the edge and open a detector issue.

## Validate

After disposition:

```bash
# Re-run the detector for the tenant.
kubectl exec -n hub-staging deploy/api -- python manage.py \
    detect_lineage_cycles --tenant=<id>
# Expect: zero cycles for the dispositioned tenant.
```

## If stuck

If the cycle is real (not a false-positive in any of the three
cohorts above), follow [lineage-edge-sync-drift.md](./lineage-edge-sync-drift.md)
to reconcile + re-run the cycle detector.

## Related

- [Edge sync drift](./lineage-edge-sync-drift.md)
- [Backfill failure](./lineage-edge-backfill-failure.md)
