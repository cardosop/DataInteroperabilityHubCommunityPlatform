# Runbook — Semantic Resource Tombstone (Phase 230.3)

Spec: [REQ-SEM-TOMBSTONE-001](../../openspec/changes/preprod01/specs/semantic-service-layer/spec.md#requirement-tombstone-lifecycle-and-http-410-gone-req-sem-tombstone-001)

## What is a tombstone?

A `SemanticResource` row whose `status = TOMBSTONED`.  When a tombstoned IRI is dereferenced, the platform returns **HTTP 410 Gone** with `Cache-Control: max-age=86400` — telling caches and consumers that the resource is permanently gone, not merely missing.

Tombstoning is the **single canonical mechanism** for retiring an IRI.  There is no "delete the SemanticResource row" path; the row stays so the 410 endpoint can answer for at least one cache TTL after the underlying object is gone.

## When does a resource get tombstoned?

Three signal-driven paths plus one programmatic path:

| Trigger | Reason code | Where wired |
|---|---|---|
| `Asset.status` flips to `RETIRED` | `asset_retired` | [hub/apps/assets/signals.py](../../hub/apps/assets/signals.py) |
| `Contract.delete()` (post_delete) | `contract_deleted` | [hub/apps/contracts/signals.py](../../hub/apps/contracts/signals.py) |
| `Dataset.archived_at` flips from NULL → non-NULL | `dataset_archived` | [hub/apps/datasets/signals.py](../../hub/apps/datasets/signals.py) |
| GDPR right-to-be-forgotten purge | `gdpr_purge` | (future) — calls `tombstone_resource` directly |

All four go through the canonical `tombstone_resource()` in [hub/apps/semantic/tombstone.py](../../hub/apps/semantic/tombstone.py).

## What happens at tombstone time?

Atomic block (single DB transaction):

1. `SemanticResource.status` → `TOMBSTONED`
2. `tombstoned_at` → `timezone.now()`
3. `tombstone_reason` → one of the four reason codes
4. A `SEMANTIC_TOMBSTONE` audit event is written

Outside the DB transaction (best-effort):

5. `SemanticServiceClient.delete_resource_triples(tenant_id, iri)` purges the resource's triples from the tenant's Fuseki named graph.  If Fuseki is unreachable (circuit-breaker open / network partition), the purge is logged at WARNING and the DB transition is preserved — the spec mandates the DB row is the canonical signal; the Fuseki purge is downstream best-effort.

## Operator playbook

### Symptom: customer reports "this resource exists in our app but the IRI returns 410"

1. **Confirm the DB state.**
   ```sql
   SELECT uri, status, tombstoned_at, tombstone_reason, updated_at
   FROM semantic_resources
   WHERE uri = '<the IRI>';
   ```
   If `status = 'TOMBSTONED'`, that IS the answer.

2. **Find the canonical reason.**  The `tombstone_reason` column tells you why — match it against the table above.

3. **Pull the audit row.**
   ```sql
   SELECT id, action, created_at, details_json
   FROM audit_event
   WHERE action = 'SEMANTIC_TOMBSTONE'
     AND details_json->>'iri' = '<the IRI>'
   ORDER BY created_at DESC LIMIT 1;
   ```
   `details_json.reason` mirrors `tombstone_reason`; `details_json.iri` confirms the resource.  `created_at` tells you exactly when the transition happened — usually within seconds of the underlying Asset / Contract / Dataset operation.

4. **If the customer claims the operation was a mistake** — there is no built-in resurrection.  Tombstones are terminal by design.  Recovery options:
   - Create a NEW resource (new UUID, new IRI) representing the same conceptual entity.
   - For exceptional cases, manually flip `status` back to `ACTIVE` and re-trigger Fuseki ingestion via the resource's mapping endpoint.  This is OUT OF BAND and should be done only with a paper-trail ticket.

### Symptom: 410 response missing `Cache-Control: max-age=86400`

The `_maybe_tombstone_410` helper in `views.py` and the `_maybe_tombstone_outcome` helper in `services.py` both set the header.  Verify:
- Reverse-proxy (CloudFront, nginx) isn't stripping `Cache-Control`.
- DRF middleware isn't overriding it (the project's `cache_headers` middleware honours headers the view sets).

### Symptom: tombstoned IRI still returns triples in SPARQL

The Fuseki purge is best-effort.  If the semantic-service was unreachable when the tombstone fired, the DB row is `TOMBSTONED` but the triples remain.  Recovery:

```python
from hub.apps.semantic.models import SemanticResource, SemanticResourceStatus
from hub.apps.semantic.service_client import SemanticServiceClient

client = SemanticServiceClient()
for sr in SemanticResource.objects.filter(status=SemanticResourceStatus.TOMBSTONED):
    res = client.delete_resource_triples(
        tenant_id=str(sr.tenant_id), iri=sr.uri,
    )
    print(sr.uri, res.get("status"))
```

This is idempotent: re-running on already-purged triples is a no-op.  Schedule it as a daily reconciliation cron if Fuseki outages happen often.

### Symptom: `SEMANTIC_TOMBSTONE` audit count climbing fast

Run:

```sql
SELECT date_trunc('hour', created_at) AS hour,
       details_json->>'reason' AS reason,
       COUNT(*) AS n
FROM audit_event
WHERE action = 'SEMANTIC_TOMBSTONE'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY 1, 2
ORDER BY hour DESC, n DESC;
```

A burst of `contract_deleted` could be a tenant doing a bulk contract cleanup; `asset_retired` bursts often trace to a workflow that retires a parent asset and cascades.  Cross-reference the actor on the originating audit row (the one with the Asset retire / Contract delete action) to confirm intent.

## Operational guarantees

- **Idempotent.**  Re-firing the tombstone path on an already-TOMBSTONED row is a no-op — no second audit event, no second Fuseki call.
- **Atomic on the DB side.**  The status flip + audit row are written in the same transaction (`tombstone_resource` opens its own `transaction.atomic()`); a partial failure cannot produce a tombstoned row without an audit event.
- **Best-effort on Fuseki.**  A semantic-service outage does NOT block the DB transition (defence-in-depth: dereference returns 410 from the DB row even if triples linger in Fuseki for a window).
- **Cache-friendly.**  `Cache-Control: max-age=86400` means upstream caches honour the terminal state for ~1 day per the spec.

## Forbidden recovery paths

Do NOT manually `DELETE FROM semantic_resources WHERE id = ...` to "fix" a tombstone.  The 410 endpoint relies on the row being present; deleting it returns 404 instead, which breaks cache contracts (a cache that saw 410 will keep returning 410 for max-age; a cache that saw 404 may retry indefinitely).  Tombstones are terminal — the row is load-bearing.

## Related runbooks

- [Semantic-service outage](./semantic-outage.md) (if exists)
- [Marquez outage](./marquez-outage.md)
