# GraphQL-LD — operational runbook

**Phase**: 284.B.6
**Status**: Authoritative; reviewed quarterly + on-incident.
**On-call escalation**: `#semantic-eng` Slack → SRE primary on-call → Eng EM.
**Feature flag**: `semantic_graphql_ld_enabled` (GA, opt-in, retire-by 2027-08-01).

## Scope

Operational guide for the GraphQL-LD endpoint at `POST /api/v1/semantic/graphql`
([hub/apps/graphql_ld/views.py](../../hub/apps/graphql_ld/views.py)). Covers
complexity/depth enforcement, tenant isolation verification, timeout triage,
and audit reconstruction. The endpoint translates GraphQL queries against the
tenant's Linked-Data surface into canonical Django ORM lookups (Asset,
Contract, Dataset); no Fuseki/SPARQL dependency exists for the read path.

## Architecture

```
POST /api/v1/semantic/graphql
  → 1. IsAuthenticated (DRF)
  → 2. Capability gate: tenant.semantic_graphql_ld_enabled → 403 if False
  → 3. SemanticGraphQLThrottle (60 q/min/user) → 429 + Retry-After
  → 4. Body parse: { query: str, variables?: dict }
  → 5. Parse to graphql-core DocumentNode → 400 GRAPHQL_SYNTAX_ERROR
  → 6. Depth check: calculate_max_depth() ≤ SEMANTIC_GRAPHQL_DEPTH_LIMIT (5)
       → 400 GRAPHQL_DEPTH_EXCEEDED
  → 7. Complexity check: calculate_complexity() ≤ SEMANTIC_GRAPHQL_COMPLEXITY_LIMIT (100)
       → 400 GRAPHQL_COMPLEXITY_EXCEEDED
  → 8. Execute under ThreadPoolExecutor with 10s hard cap
       → 408 GRAPHQL_QUERY_TIMEOUT
  → 9. Audit emission: SEMANTIC_GRAPHQL_QUERY with SHA-256 query hash
       (NEVER the query body — PII risk)
```

Every outcome (SUCCESS, DEPTH_EXCEEDED, COMPLEXITY_EXCEEDED, TIMEOUT,
SYNTAX_ERROR, EXECUTION_ERROR, THROTTLED) emits exactly one audit row.

## Symptom triage matrix

| Symptom | Likely cause | Action |
|---|---|---|
| User sees 403 "not enabled for this tenant" | Flag off for tenant | Verify `semantic_graphql_ld_enabled` in tenant admin |
| User sees 400 GRAPHQL_DEPTH_EXCEEDED | Query depth > 5 | User action: flatten nested selections; use fragments |
| User sees 400 GRAPHQL_COMPLEXITY_EXCEEDED | Complexity > 100 | User action: reduce alias count; avoid 11+ list fields |
| User sees 408 GRAPHQL_QUERY_TIMEOUT | Resolver > 10s | Check DB load; check for missing index on filtered column |
| User sees 429 with Retry-After | Rate limit hit (60 q/min) | User action: back off; client should honour Retry-After |
| Query returns empty assets/datasets/contracts | Tenant has no data, or cross-tenant lookup | Check tenant owns the queried resources |
| Asset point-lookup returns null | Cross-tenant ID supplied (by design — no 404 leak) | Verify the asset belongs to the authenticated tenant |

## Tenant isolation verification

The resolver layer never trusts client-supplied tenant IDs. The view wires
`info.context.tenant_id` from the authenticated user's `request.user.tenant`.
Resolvers filter by this value exclusively.

**Verification query** (requires PLATFORM_ADMIN access):

```sql
-- Confirm every resolver WHERE clause carries tenant_id
-- View source: hub/apps/graphql_ld/resolvers.py
-- list_assets:    Asset.objects.filter(tenant_id=tenant_id)
-- get_asset:      Asset.objects.get(id=asset_id, tenant_id=tenant_id)
-- list_contracts: Contract.objects.filter(tenant_id=tenant_id)
-- list_datasets:  Dataset.objects.filter(tenant_id=tenant_id)
```

**Cross-tenant leak test**: A user on tenant-Y querying `asset(id: <X.id>)`
MUST receive `data.asset == null` — never 403 or 404. This is tested in
`hub/apps/graphql_ld/tests/test_resolvers.py::GraphQLTenantIsolationTests`.

## Complexity troubleshooting

### Understanding the complexity score

| Field type | Cost |
|---|---|
| Scalar / object field | +1 |
| List field (returns array) | +10 |
| Fragment spread | Cost of fragment body (visited once) |
| Inline fragment | Cost of inner selection set |

List fields are weighted 10× because a list resolver may return up to
`limit` rows (default 100). Eleven list-typed selections → 110 > 100 →
rejected.

### Common fixes for rejected queries

1. **Reduce alias count**: `a1: assets { id }  a2: assets { id } ...` adds
   +10 per alias. Inline the needed fields under a single `assets` selection.
2. **Use fragments**: Extract repeated sub-selections into named fragments.
   Each fragment body is scored once per operation.
3. **Narrow selections**: Only request the fields you need. Every scalar
   field adds +1.

### Configuration overrides (deployment-level)

```python
# settings.py — raise/lower limits per environment
SEMANTIC_GRAPHQL_DEPTH_LIMIT = 5       # default
SEMANTIC_GRAPHQL_COMPLEXITY_LIMIT = 100  # default
SEMANTIC_GRAPHQL_TIMEOUT_SECONDS = 10.0 # default
```

## Audit reconstruction

All queries emit `SEMANTIC_GRAPHQL_QUERY` audit rows. The query body is
NEVER persisted — only the SHA-256 hash. To reconstruct usage patterns:

```sql
SELECT timestamp, actor_user_id, tenant_id,
       details_json->>'outcome' AS outcome,
       details_json->>'query_sha256' AS query_hash,
       details_json->>'response_time_ms' AS latency_ms
FROM audit_auditevent
WHERE action = 'SEMANTIC_GRAPHQL_QUERY'
  AND tenant_id = '<tenant-uuid>'
ORDER BY timestamp DESC
LIMIT 100;
```

The `outcome` field in `details_json` is one of: `SUCCESS`, `DEPTH_EXCEEDED`,
`COMPLEXITY_EXCEEDED`, `TIMEOUT`, `SYNTAX_ERROR`, `EXECUTION_ERROR`, `THROTTLED`.

## Throttle configuration

```python
# REST_FRAMEWORK settings — overridable per environment
DEFAULT_THROTTLE_RATES = {
    "semantic_graphql": "60/minute",
}
```

The throttle is per-user (not per-IP). Tenant isolation is implicit because
each user belongs to exactly one tenant. The `throttled()` override emits a
`SEMANTIC_GRAPHQL_QUERY` audit row with `outcome=THROTTLED` before raising
the 429 — so the auditor can see denied requests.

## Related runbooks

- [RB-SEM-* — SPARQL endpoint](../runbooks/) (future)
- Feature flag lifecycle: [admin-feature-flag-flip.md](admin-feature-flag-flip.md)
- Semantic search throttle: [semantic-search.md](semantic-search.md) (future)
