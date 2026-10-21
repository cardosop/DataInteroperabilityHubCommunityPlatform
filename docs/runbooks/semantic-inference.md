# Semantic OWL/RDFS Reasoning (per-tenant)

**Phase:** 230.7
**Spec:** REQ-SEM-INFERENCE-001
**Owners:** Platform / Semantic
**Status:** Per-tenant feature (default OFF). Flip via `Tenant.semantic_inference_enabled`.

## Overview

When a tenant has `semantic_inference_enabled=True`, SPARQL queries
against `/api/v1/semantic/sparql` are routed to a Fuseki dataset
configured with an OWL Mini reasoner overlay (the same TDB2 store
on disk, just wrapped in an `InfModel` at query time). The reasoner
materialises:

- `rdfs:subClassOf` transitive closure (instances of subclasses
  appear when querying for the superclass).
- `rdfs:subPropertyOf` transitive closure.
- `owl:inverseOf`.
- `rdfs:domain` / `rdfs:range`.

Direct queries (flag OFF) hit `/hub`. Inferred queries (flag ON) hit
`/hub-inferred`. **The on-disk store is unchanged** — flipping a
tenant back to OFF is instantaneous (no rebuild, no cache eviction).

## Wire path

```
Django view (sparql_query)
  └─ SPARQLQueryService.run()
       ├─ _resolve_inference_flag(tenant_id) → reads Tenant.semantic_inference_enabled
       │                                     (per-query SELECT, NOT cached — flag flips
       │                                      take effect on the very next query)
       └─ SemanticServiceClient.query_sparql(..., inference=<bool>)
            └─ POST /query  {tenant_id, query, inference}
                 └─ semantic-service main.py:tenant_sparql_query
                      ├─ selected_client = fuseki_client_inferred if request.inference
                      │                    else fuseki_client
                      ├─ span.set_attribute("fuseki.endpoint", "dataset/inferred"|"dataset")
                      └─ selected_client.query(...)
                           └─ POST {FUSEKI_URL}/{FUSEKI_DATASET|FUSEKI_INFERRED_DATASET}/query
```

## Verification (the spec scenario)

The spec mandates that a flag flip takes effect on the very next
query, observable via `fuseki.endpoint` trace span attribute (and as
a defensive fallback, the `X-Fuseki-Endpoint` response header).

```bash
# As a tenant admin:
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/tenants/$TID/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"semantic_inference_enabled": true}'

# Immediately:
curl -X POST https://api.stagingmeshant-internal.example.com/api/v1/semantic/sparql \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"}' \
  -i | grep -i x-fuseki-endpoint
# X-Fuseki-Endpoint: dataset/inferred
```

In Grafana / Tempo, filter on `service.name=semantic-service` and
group by `fuseki.endpoint` to see the per-tenant routing distribution.

## Operational scenarios

### Rolling out to a single tenant

1. Confirm the inferred dataset is registered:
   ```bash
   kubectl exec -n hub-staging fuseki-0 -- curl -s http://localhost:3030/$/datasets | jq '.[].["ds.name"]'
   # Expected: ["/hub", "/hub-inferred"]
   ```
2. Flip the tenant flag:
   ```python
   from hub.apps.tenants.models import Tenant
   Tenant.objects.filter(slug="acme").update(semantic_inference_enabled=True)
   ```
3. Have the tenant run a representative SPARQL query; verify the
   trace span / response header shows `dataset/inferred`.

### Tenant reports SPARQL latency regression after flag flip

Inference adds 2-5x latency by design. If the tenant is unhappy:

1. Check the latest `semantic-inference-benchmark` workflow run for
   the global p99/p95 trend on staging — if it's also climbing, this
   is a cross-tenant reasoner regression, not a per-tenant problem.
2. Per-tenant: fetch the slow query from logs, EXPLAIN it against
   `/hub-inferred` to see if the reasoner is over-materialising.
3. Flip the tenant flag back to False. The change takes effect
   immediately — no Fuseki restart.

### Reasoner choice change

`OWLMicroFBRuleReasoner` is the chosen default
(see `helm/files/fuseki-config.ttl`). To change:

1. Edit `helm/files/fuseki-config.ttl` — the `:model_hub_inferred`
   `ja:reasonerURL` value. Common alternatives:
   - `RDFSExptRuleReasoner` (faster, drops `owl:inverseOf`).
   - `OWLFBRuleReasoner` (full OWL, ~10x slower than micro).
2. Helm upgrade — Fuseki StatefulSet rolls; the inferred service
   binding picks up the new reasoner. **The on-disk TDB2 is NOT
   touched.** Direct queries (flag OFF) are unaffected.
3. Run `semantic-inference-benchmark.yml` ad-hoc via
   `workflow_dispatch` and confirm the gates still pass before
   considering the change settled.

### Fuseki upgrade

When upgrading Fuseki, both `:service_hub` and
`:service_hub_inferred` rebuild from the same `:dataset_hub` —
there's no separate "inferred TDB2" to migrate. Ordinary Fuseki
upgrade procedure applies.

### Disabling inference globally (incident)

For a global kill-switch (e.g. reasoner CVE):

1. Set `semanticService.env.FUSEKI_INFERRED_DATASET=hub` in
   `helm/values.yaml` (route inferred-mode requests at the plain
   dataset). Helm upgrade.
2. Inferred queries now return direct triples — semantically
   incorrect for tenants who depend on inferences, but available
   while the reasoner is being patched.
3. Restore by reverting the env var.

Per-tenant flip remains the preferred path; this is a break-glass
last resort.

## Latency budget (REQ-SEM-INFERENCE-001 / 230.7.6)

| Metric | Budget | Where enforced |
|--------|--------|----------------|
| p99 latency (inferred) | < 2000 ms | `.github/workflows/semantic-inference-benchmark.yml` |
| p95 ratio (on/off) | < 5x | same |
| Early-warning p99 | 1500 ms (warn only) | same |

Workflow runs nightly at 04:30 UTC; failures pop a separate alert
from `perf-nightly`.

## Known limitations

- The reasoner runs **at query time** on Fuseki — heavy ontologies +
  large tenants may hit the reasoner's per-query timeout before the
  Hub's. If you see Fuseki 503s with `Reasoner timeout`, it's the
  reasoner, not the network. Fuseki has its own timeout config; the
  semantic-service `timeout` parameter only governs the HTTP layer.
- `owl:sameAs` is NOT materialised by `OWLMicroFBRuleReasoner`. If a
  tenant relies on owl:sameAs (cross-IRI identity), they need a
  reasoner change (`OWLFBRuleReasoner` covers it). File an issue
  rather than adding it inline — full OWL is ~10x slower.
- Result-cache partitioning: inferred and direct query results are
  cached under separate keys (different FusekiClient instances ⇒
  different connection pools / Redis namespaces). Cache eviction on
  one side does NOT propagate.
- The hub-side flag check is **per query**, intentionally NOT cached.
  A tenant flipping the flag in a tight loop pays one indexed PK
  lookup per SPARQL request.

## Pager / on-call escalations

| Symptom | Likely cause | First action |
|---------|--------------|--------------|
| `semantic-inference-benchmark` workflow fails on p99 budget | Reasoner regression OR staging tenant graph grew | Check graph size; re-run workflow ad-hoc; consider RDFSExptRuleReasoner |
| `semantic-inference-benchmark` fails on ratio budget | New ontology pattern triggers reasoner blow-up | Inspect new triples in `urn:system:ontology`; revert if bad pattern |
| Tenant reports SPARQL returns extra (unexpected) results | Tenant flag flipped to True without their knowledge | Check audit log for the PATCH; flip back if unintentional |
| `Reasoner timeout` 503s under load | Reasoner can't keep up with current graph | Tactical: tenant flag → False; strategic: reasoner change |
| `Could not flip inference flag` in benchmark output | Admin API endpoint missing or perm change | Check tenant PATCH endpoint exists + smoke-admin has perms |

## Reference

- Spec: `openspec/changes/preprod01/specs/semantic-service-layer/spec.md` § REQ-SEM-INFERENCE-001
- Tasks: `openspec/changes/preprod01/tasks.md` § 230.7
- Tenant model field: `hub/apps/tenants/models.py::Tenant.semantic_inference_enabled`
- Migration: `hub/apps/tenants/migrations/0026_tenant_semantic_inference_enabled.py`
- Service routing: `hub/apps/semantic/services.py::SPARQLQueryService._resolve_inference_flag`
- Wire forwarding: `hub/apps/semantic/service_client.py::SemanticServiceClient.query_sparql(... inference=...)`
- Service-side dispatch: `services/semantic-service/main.py::tenant_sparql_query`
- Fuseki overlay: `helm/files/fuseki-config.ttl::service_hub_inferred`
- Helm env: `helm/values.yaml` — `semanticService.env.FUSEKI_INFERRED_DATASET`
- Benchmark: `scripts/semantic_inference_benchmark.py` + `.github/workflows/semantic-inference-benchmark.yml`
