# Tenant Custom Ontology Registration

**Phase:** 230.10
**Spec:** REQ-SEM-ONTO-001 / REQ-SEM-ONTO-002
**Owners:** Platform / Semantic
**Status:** Per-tenant feature, default OFF. Flip via
`Tenant.semantic_custom_ontology_enabled`.

## Overview

A `TENANT_ADMIN` may upload Turtle / RDF/XML / JSON-LD ontologies
that extend the SPARQL vocabulary available to their tenant.
Activated ontologies are loaded into the Fuseki named graph
`urn:tenant:{tenant_id}:ontology:{name}` and dropped on
deactivation. The hub `Tenant.semantic_custom_ontology_enabled`
flag gates the entire surface — when False, the API endpoints
return 403 regardless of role (REQ-SEM-ONTO-002).

## Wire path

```
Django view (TenantOntologyViewSet.create)
  ├─ resolve tenant from request
  ├─ check Tenant.semantic_custom_ontology_enabled (403 if off)
  ├─ check IsTenantAdmin (403 if not TENANT_ADMIN)
  ├─ OntologyValidator().validate(...)         ← sync (< 50 ms)
  │     ├─ size cap (≤ 10 MB raw)
  │     ├─ rdflib parse
  │     ├─ triple-count cap (≤ 100k)
  │     ├─ reserved-namespace check
  │     └─ per-tenant namespace uniqueness
  ├─ TenantOntology.objects.create(...)
  ├─ create_audit_event(action="SEMANTIC_ONTOLOGY_UPLOAD")
  └─ enqueue ONTOLOGY_VALIDATE job (async re-validation)

Activation (PATCH is_active=True):
  ├─ require TenantOntology.validation_status == VALID
  ├─ SemanticServiceClient.load_ontology(graph_uri, rdf, format)
  │     └─ POST /ontology/load on FastAPI semantic-service
  │           └─ FusekiClient.delete_graph + store_graph
  ├─ TenantOntology.is_active = True; activated_at = now()
  └─ create_audit_event(action="SEMANTIC_ONTOLOGY_ACTIVATE")

Deactivation (PATCH is_active=False):
  ├─ SemanticServiceClient.drop_ontology(graph_uri)
  │     └─ DELETE /ontology/load on FastAPI semantic-service
  ├─ TenantOntology.is_active = False
  └─ create_audit_event(action="SEMANTIC_ONTOLOGY_DEACTIVATE")
```

## Operational scenarios

### Enabling the feature for a tenant

```python
from hub.apps.tenants.models import Tenant
Tenant.objects.filter(slug="acme").update(semantic_custom_ontology_enabled=True)
```

The next request from any TENANT_ADMIN of that tenant will see the
"Custom Ontologies" tab on `/semantic`. No restart, no cache
eviction.

### TENANT_ADMIN uploads an ontology via CLI

```
meshant semantic custom-ontology upload \
  --name acme \
  --namespace https://acme.example/ontology/ \
  --format turtle \
  --file ./acme-ontology.ttl
```

Validation runs synchronously; on rejection the CLI surfaces the
error code (`ONTOLOGY_TOO_LARGE` / `ONTOLOGY_RESERVED_NAMESPACE` /
`ONTOLOGY_PARSE_ERROR` / `ONTOLOGY_NAMESPACE_DUPLICATE`).

After upload, activate:

```
meshant semantic custom-ontology activate <ontology_id>
```

### Reasoning interaction (Phase 230.7 + 230.10)

When a tenant has BOTH `semantic_inference_enabled=True` AND at
least one active custom ontology, the inference reasoner sees the
ontology's triples through the same `:dataset_hub_inferred` Fuseki
service binding (the inferred service binds to the entire on-disk
TDB2 store, which includes every named graph including
`urn:tenant:{id}:ontology:{name}`). No additional configuration
needed — the reasoner picks them up at the next query.

To verify the inferred-overlay sees a custom ontology:

```sparql
PREFIX acme: <https://acme.example/ontology/>
SELECT ?s WHERE { GRAPH <urn:tenant:{TID}:ontology:acme> { ?s a owl:Class } }
```

The query MUST run with the tenant's `semantic_inference_enabled=True`
flag on; the results include both directly-asserted and reasoner-
materialised classes.

### Ontology stuck in PENDING status

Async re-validation runs as `JobType.ONTOLOGY_VALIDATE`. If a row
stays PENDING for more than ~1 minute, the worker queue is likely
backed up. Triage:

1. Check `Job.objects.filter(type='ONTOLOGY_VALIDATE', status='PENDING').count()`.
2. If non-zero, check `django-rq` worker pod count (`kubectl get pods -l app=worker`).
3. Manually re-run validation:
   ```python
   from hub.apps.semantic.tasks import run_ontology_validation_job
   run_ontology_validation_job(ontology_id="<uuid>")
   ```

### Validation passes but activation fails (LOAD_FAILED)

The Fuseki `POST /ontology/load` call is best-effort wrapped in a
circuit breaker. A LOAD_FAILED status means the validator passed
but Fuseki was unreachable or returned a non-OK response.

1. Check the FastAPI semantic-service logs for `ontology_load_*`
   warnings.
2. Verify Fuseki is up: `kubectl exec fuseki-0 -- curl http://localhost:3030/$/ping`.
3. Re-attempt activation: `PATCH /api/v1/semantic/ontologies/{id}/` with `is_active=True`.

### Tenant exceeds practical ontology budget

There is no hard per-tenant cap on the NUMBER of ontologies — the
spec's caps are per-ontology (10 MB raw, 100k triples). A tenant
with hundreds of active ontologies multiplies the SPARQL query
surface and reasoner cost; if you see latency regressions:

1. Query active ontology count:
   ```sql
   SELECT tenant_id, count(*) FROM semantic_tenant_ontologies WHERE is_active = true GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
   ```
2. Coordinate with the tenant on consolidation (one large ontology
   often beats many small ones for reasoner performance).

## Known limitations

- **No per-tenant ontology cap.** A motivated tenant could create
  thousands of small ontologies. Consider adding a soft cap (e.g.
  100 active ontologies / tenant) if abuse becomes operationally
  visible.
- **`owl:imports` not followed.** The validator parses the
  uploaded body verbatim; cross-document `owl:imports` declarations
  are NOT resolved. Tenants needing imports must inline the
  imported triples or upload each ontology separately.
- **Reasoner cost grows with active-ontology count.** The Phase
  230.7 inference-on/off latency benchmark gate (p99 < 2s) catches
  reasoner regressions globally; a single tenant with too many
  active ontologies could blow past the gate without anyone
  noticing the cause until the workflow fails.

## On-call escalations

| Symptom | Likely cause | First action |
|---------|--------------|--------------|
| Tenant reports 403 on `/api/v1/semantic/ontologies/` despite TENANT_ADMIN role | `semantic_custom_ontology_enabled=False` | Flip flag via Tenant.objects.update |
| Upload returns ONTOLOGY_TOO_LARGE | Body > 10 MB | Tenant must split or compact the ontology |
| Upload returns ONTOLOGY_RESERVED_NAMESPACE | Tenant declared `https://meshant.com/ontology/` | Reject — reserved namespace; pick a different IRI |
| Activation 503 + LOAD_FAILED | Fuseki unreachable | Check semantic-service + Fuseki pod health |
| Inference query missing custom-ontology classes | Either flag off OR inferred dataset cache stale | Check `semantic_inference_enabled` flag; run query through `/sparql` and inspect `X-Fuseki-Endpoint` header |

## Reference

- Spec: `openspec/changes/preprod01/specs/semantic-custom-ontology/spec.md` § REQ-SEM-ONTO-001 / REQ-SEM-ONTO-002
- Tasks: `openspec/changes/preprod01/tasks.md` § 230.10
- Tenant flag: `hub/apps/tenants/models.py::Tenant.semantic_custom_ontology_enabled`
- Migrations: `hub/apps/tenants/migrations/0027_*.py` + `hub/apps/semantic/migrations/0007_tenant_ontology.py`
- Model: `hub/apps/semantic/models.py::TenantOntology`
- Validator: `hub/apps/semantic/ontology_validator.py::OntologyValidator`
- ViewSet: `hub/apps/semantic/views_ontology.py::TenantOntologyViewSet`
- Job: `hub/apps/semantic/tasks.py::run_ontology_validation_job`
- Service-side endpoints: `services/semantic-service/main.py::load_ontology / drop_ontology`
- Frontend: `frontend/src/features/semantic/components/OntologyManager.tsx`
- CLI: `cli/datahub_cli/commands/semantic.py::custom_ontology` group
- E2E: `frontend/e2e/journeys/ai-ml-semantic/custom-ontology.spec.ts`
