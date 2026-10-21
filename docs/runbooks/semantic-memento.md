# Semantic Memento (Accept-Datetime) Versioned Retrieval

**Phase:** 230.4
**Spec:** REQ-SEM-MEMENTO-001
**Owners:** Platform / Semantic
**Status:** Behind feature flag (`SEMANTIC_MEMENTO_ENABLED` + `Tenant.semantic_memento_enabled`)

## Overview

The Memento (RFC 7089) feature lets clients dereference a semantic
resource as it existed at a past point in time. Three surfaces:

1. `GET /api/v1/semantic/resource/{type}/{id}/` with the
   `Accept-Datetime` header → `302` redirect to the nearest-past
   versioned URI, with `Memento-Datetime` response header.
2. `GET /api/v1/semantic/resource/{type}/{id}/version/{iso8601}` →
   the captured RDF body for that snapshot.
3. `GET /api/v1/semantic/resource/{type}/{id}/timemap` →
   `application/link-format` listing every snapshot.

Snapshots live in Postgres only (`semantic_resource_versions`
table), NOT in Fuseki — so the SPARQL query path is unaffected by
the version count.

## Feature flags

| Flag | Default | Effect |
|------|---------|--------|
| `SEMANTIC_MEMENTO_ENABLED` (env / settings) | `False` | Global kill-switch. When False the dereference endpoint ignores `Accept-Datetime` regardless of per-tenant flags. |
| `Tenant.semantic_memento_enabled` | `False` | Per-tenant opt-in. Both flags must be True for snapshots to be created OR served. |
| `SEMANTIC_MEMENTO_MAX_PER_RESOURCE` | `100` | Per-resource cap. Beyond this the snapshot job prunes oldest. |
| `SEMANTIC_MEMENTO_MAX_PER_TENANT` | `1_000_000` | Per-tenant cap. Above 80% an alert fires; at 100% new snapshot jobs refuse. |
| `SEMANTIC_MEMENTO_DEBOUNCE_SECONDS` | `60` | Redis SETNX TTL for the post-save debounce. |

## How snapshots are produced

1. Asset / Contract / Dataset post_save signal fires.
2. `transaction.on_commit(_maybe_schedule_snapshot)` runs after the
   source-side commit.
3. The handler checks the global + tenant flag; checks
   `cache.add(lock_key, ttl=60)` — first writer wins, others skip.
4. A `Job` row with `type=SEMANTIC_SNAPSHOT` is inserted and
   dispatched to django-rq's `default` queue.
5. The job re-fetches the live RDF, sorts the N-Triples lines,
   SHA-256s the result, INSERTs a `SemanticResourceVersion`. The
   `(resource, content_hash)` UniqueConstraint dedupes identical
   content (turning unchanged resaves into a no-op).
6. The job prunes any rows above
   `SEMANTIC_MEMENTO_MAX_PER_RESOURCE` for the same resource.

## Operational scenarios

### Rolling out to a single tenant

1. Confirm the global setting is on:
   `kubectl exec deploy/hub -- python -c 'from django.conf import settings; print(settings.SEMANTIC_MEMENTO_ENABLED)'`.
2. Flip the per-tenant flag:
   ```python
   from hub.apps.tenants.models import Tenant
   Tenant.objects.filter(slug="acme").update(semantic_memento_enabled=True)
   ```
3. Trigger an Asset save in the target tenant; verify a Job row
   appears with `type='SEMANTIC_SNAPSHOT'` and a
   `SemanticResourceVersion` row follows shortly.

### Tenant approaching the 1M cap

Alert: `semantic_memento_tenant_cap_alert` (logger warning at 80%).

Triage:

1. Query the version count:
   ```sql
   SELECT tenant_id, count(*) FROM semantic_resource_versions GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
   ```
2. If a single resource dominates, suspect runaway updates. Check
   `audit_events` for that resource's update cadence — debounce
   should hold updates to ≤ 1/min/resource.
3. If it's a healthy spread, raise `SEMANTIC_MEMENTO_MAX_PER_TENANT`
   for the tenant via env override; engage product on whether the
   tenant should move to a higher pricing tier.

Refused snapshots (`status="refused", reason="tenant_cap_exceeded"`
in `Job.result_json`) are NOT retried — they're a load-shed signal
not a transient failure.

### Disabling for a tenant in incident

Flip the per-tenant flag back to False:
```python
Tenant.objects.filter(slug="acme").update(semantic_memento_enabled=False)
```

This stops new snapshots immediately; existing snapshots stay
queryable until cleanup runs. Dereference endpoints stop honouring
`Accept-Datetime` for that tenant on the next request.

### GDPR right-to-be-forgotten

The canonical `tombstone_resource(reason=REASON_GDPR_PURGE)` path
(in `hub.apps.semantic.tombstone`) deletes ALL
`SemanticResourceVersion` rows for the affected resource inside
the same transaction as the tombstone. Verification:

```sql
SELECT count(*) FROM semantic_resource_versions
WHERE resource_id IN (SELECT id FROM semantic_resources WHERE tenant_id = '<uuid>');
-- Should return 0 after the purge job completes.
```

### Capacity test

Run on staging Postgres before raising the per-tenant cap:

```
python scripts/semantic_memento_capacity_test.py --count 100000
```

Expected:
* Bulk insert > 5k rows/s on staging RDS.
* Nearest-past lookup p95 < 50ms, p99 < 100ms.

## Known limitations

* **No pre-deploy snapshot backfill** (Phase 230.AUDIT.4 — DECIDED skip).
  Memento returns the nearest-past `SemanticResourceVersion` row.
  Resources updated AFTER the Phase 230.4 deploy date have
  snapshots; resources that haven't been updated since deploy
  have no snapshots and dereference with `Accept-Datetime` returns
  404. **Pre-deploy state is not represented in the version history.**
  The skip-backfill decision is intentional: snapshots are useless
  for time-travel until enough wall-clock time passes for the
  history to span the queried date — backfilling a single
  "deploy-time" snapshot per resource produces a degenerate history
  that misleads operators into thinking time-travel works further
  back than it does. Resources mature into the Memento surface
  organically as they receive updates post-deploy.
* Blank-node IDs are NOT canonicalised. Two graphs that differ only
  in blank-node naming will hash differently, producing a redundant
  snapshot. Acceptable for v1; URDNA2015 canonicalisation is a
  follow-up.
* `serialization_format` is fixed to `n-triples` for hashing. Other
  formats are reserialised on read (rdflib round-trip), which is
  potentially lossy for `@context` directives in JSON-LD.
* The `(resource_id, snapshot_at DESC)` index is built with
  `CREATE INDEX CONCURRENTLY` (migration 0006, `atomic=False`).
  If the migration fails mid-build, drop the partial index manually
  before re-applying:
  ```
  DROP INDEX IF EXISTS semv_resource_snapat_idx;
  ```

## Pager / on-call escalations

| Symptom | Likely cause | First action |
|---------|--------------|--------------|
| `semantic_memento_tenant_cap_alert` (warning) | Approaching 80% of per-tenant cap | Query top resources by version count; check debounce holding |
| `semantic_memento_tenant_cap_exceeded` (error) | At 100% of cap; new snapshots refused | Decide raise-cap vs tighten debounce; flip tenant flag off if needed |
| `semantic_snapshot_enqueue_dispatch_failed` | django-rq queue outage | Check Redis broker; replay failed jobs from `Job` table |
| `semantic_memento_lock_failed event=fail_open` | Redis cache outage | Cache layer down; jobs may double-enqueue. Content_hash dedupe still protects DB |
| `tombstone_version_purge_failed` | DB error during GDPR-purge ripple | Manually `DELETE FROM semantic_resource_versions WHERE resource_id = '<uuid>'` and re-run audit verification |

## Reference

* Spec: `openspec/changes/preprod01/specs/semantic-service-layer/spec.md` § REQ-SEM-MEMENTO-001
* Tasks: `openspec/changes/preprod01/tasks.md` § 230.4
* Memento RFC: <https://datatracker.ietf.org/doc/html/rfc7089>
* Models: `hub/apps/semantic/models.py` (`SemanticResourceVersion`)
* Job: `hub/apps/semantic/tasks.py` (`run_semantic_snapshot_job`)
* Views: `hub/apps/semantic/views.py` (`dereference_versioned_resource`, `semantic_timemap`, `_maybe_memento_302`)
