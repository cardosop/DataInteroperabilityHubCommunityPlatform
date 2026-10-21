# Runbook — GraphQL-LD Endpoint (Phase 230.13 / REQ-SEM-GQL-001 + 002)

> **Audience**: oncall + platform-security.
> **Phase**: 230.13 — `POST /api/v1/semantic/graphql`.
> **Last updated**: 2026-05-01.

This runbook covers operational tasks for the GraphQL-LD endpoint:
capability flag, DoS caps, audit reconstruction, troubleshooting
denied / timed-out / throttled queries, and the kill switch.

---

## Quick reference

| Key | Value |
| --- | ----- |
| **Endpoint** | `POST /api/v1/semantic/graphql` |
| **Auth** | `IsAuthenticated` (DRF) |
| **Capability flag** | `Tenant.semantic_graphql_ld_enabled` (default False) |
| **Depth cap** | 5 levels (`SEMANTIC_GRAPHQL_DEPTH_LIMIT`) |
| **Complexity cap** | 100 (`SEMANTIC_GRAPHQL_COMPLEXITY_LIMIT`) |
| **Timeout** | 10 s (`SEMANTIC_GRAPHQL_TIMEOUT_SECONDS`) |
| **Throttle** | 60 q/min/user (`semantic_graphql` scope) |
| **Audit code** | `SEMANTIC_GRAPHQL_QUERY` |
| **Outcomes** | `SUCCESS` / `DEPTH_EXCEEDED` / `COMPLEXITY_EXCEEDED` / `TIMEOUT` / `THROTTLED` / `SYNTAX_ERROR` / `EXECUTION_ERROR` |
| **Audit body** | NEVER stored — only SHA-256 hash of the query text |
| **Per-tenant kill** | Set `semantic_graphql_ld_enabled=False` |
| **Cluster-wide kill** | Drop the URL pattern via Helm override (`SEMANTIC_GRAPHQL_DISABLE=true` env override — see § Kill switches) |
| **Frontend playground** | `/semantic?tab=graphql` (lazy-loaded via `React.lazy`) |

---

## Symptoms → likely cause

| Symptom | Likely cause | Section |
| ------- | ------------ | ------- |
| User reports "GraphQL endpoint not enabled for this tenant" 403 | `Tenant.semantic_graphql_ld_enabled` is False | [§ Capability flag](#capability-flag) |
| 400 with `code=GRAPHQL_DEPTH_EXCEEDED` | Query nesting > 5 levels | [§ Caps](#caps) |
| 400 with `code=GRAPHQL_COMPLEXITY_EXCEEDED` | Computed complexity > 100 | [§ Caps](#caps) |
| 408 with `code=GRAPHQL_QUERY_TIMEOUT` | Resolver took > 10 s | [§ Caps](#caps) |
| 429 with `Retry-After` header | User exceeded 60 q/min | [§ Caps](#caps) |
| Client gets `null` on `asset(id: <X>)` despite the asset existing | Cross-tenant lookup — by design (REQ-SEM-GQL-001 isolation) | [§ Cross-tenant nulls](#cross-tenant-nulls) |
| Auditor asks "what queries did user U run yesterday?" | Replay `SEMANTIC_GRAPHQL_QUERY` rows | [§ Audit reconstruction](#audit-reconstruction) |

---

## Capability flag

The endpoint is gated by `Tenant.semantic_graphql_ld_enabled`. When False:

```json
HTTP/1.1 403 Forbidden
{ "detail": "GraphQL-LD endpoint not enabled for this tenant" }
```

Enable for a tenant via shell:

```python
from hub.apps.tenants.models import Tenant
t = Tenant.objects.get(slug="<tenant_slug>")
t.semantic_graphql_ld_enabled = True
t.save(update_fields=["semantic_graphql_ld_enabled"])
```

Or via the platform-admin UI once the feature-flag panel ships
(Phase 235.1 will surface the flag with a confirmation dialog +
audit emission).

---

## Caps

The four caps are layered in order (depth → complexity → timeout →
throttle), failing fast on the cheapest check first.

### Depth (`GRAPHQL_DEPTH_EXCEEDED`)

Pre-execution AST walk in `hub/apps/graphql_ld/views.py::calculate_max_depth`. Counts
field-selection nesting; inline + named fragments contribute their
inner depth (cyclic spreads are caught by graphql-core's validator).

```json
HTTP/1.1 400 Bad Request
{
  "code": "GRAPHQL_DEPTH_EXCEEDED",
  "max_depth": 6,
  "limit": 5,
  "detail": "Query depth 6 exceeds limit 5"
}
```

Tune via `SEMANTIC_GRAPHQL_DEPTH_LIMIT` env var (default 5).

### Complexity (`GRAPHQL_COMPLEXITY_EXCEEDED`)

Pre-execution AST walk in `hub/apps/graphql_ld/views.py::calculate_complexity`.
Scoring:

- Each scalar field → +1.
- Each list field   → +10 (a list resolver may return up to its
  per-list limit, so it's an order of magnitude heavier than a scalar).
- Each named fragment spread → cost of the fragment's selection
  (visited at most once to avoid infinite loops).

```json
HTTP/1.1 400 Bad Request
{
  "code": "GRAPHQL_COMPLEXITY_EXCEEDED",
  "complexity": 200,
  "limit": 100,
  "detail": "Query complexity 200 exceeds limit 100"
}
```

Tune via `SEMANTIC_GRAPHQL_COMPLEXITY_LIMIT`.

### Timeout (`GRAPHQL_QUERY_TIMEOUT`)

Execution under a `concurrent.futures.ThreadPoolExecutor` with a
hard 10 s timeout. The future is cancelled on timeout (in-flight
DB work continues server-side until the connection's statement
timeout fires).

```json
HTTP/1.1 408 Request Timeout
{
  "code": "GRAPHQL_QUERY_TIMEOUT",
  "timeout_seconds": 10.0,
  "detail": "GraphQL query exceeded 10.0s timeout"
}
```

Tune via `SEMANTIC_GRAPHQL_TIMEOUT_SECONDS` (float, in seconds).

### Throttle (HTTP 429 with `Retry-After`)

DRF's `UserRateThrottle` scoped to `semantic_graphql`. Default rate
is `60/minute` (set in `settings.REST_FRAMEWORK`
`DEFAULT_THROTTLE_RATES`). Throttled requests still emit a
`SEMANTIC_GRAPHQL_QUERY` audit row with `outcome=THROTTLED` so the
auditor sees the deny path.

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 47
{ "code": "GRAPHQL_RATE_LIMITED", "detail": "Request was throttled." }
```

Tune via `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES.semantic_graphql`.

---

## Cross-tenant nulls

Per REQ-SEM-GQL-001 scenario "Tenant isolation in resolver layer", a
user of tenant Y querying `asset(id: <X.id>)` for an asset owned by
tenant X gets:

```json
{ "data": { "asset": null } }
```

The endpoint MUST NOT return 404 / 403 — that would leak the
existence of cross-tenant resources. The resolvers in
`hub/apps/graphql_ld/resolvers.py` derive the active tenant id from
`info.context.tenant_id` (set by the view from
`request.user.tenant_id`); a client-supplied `tenant_id` argument
is NEVER accepted.

---

## Audit reconstruction

To answer "what queries did user U run in the last hour?":

```sql
SELECT timestamp, details_json
FROM audit_events
WHERE action = 'SEMANTIC_GRAPHQL_QUERY'
  AND actor_user_id = '<user_id>'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
```

`details_json` carries the SHA-256 hash of the query text — the
literal body is NOT stored (GraphQL inputs may carry user-supplied
PII per the spec). To reconstruct the query, pair the hash with
the calling client's debug logs, or have the user re-run the
query from the playground.

`outcome` (in `details_json`) lets you filter to denied paths:

```sql
SELECT details_json->>'outcome' AS outcome, COUNT(*) AS n
FROM audit_events
WHERE action = 'SEMANTIC_GRAPHQL_QUERY'
  AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY outcome
ORDER BY n DESC;
```

Expected outcome values: `SUCCESS`, `DEPTH_EXCEEDED`,
`COMPLEXITY_EXCEEDED`, `TIMEOUT`, `THROTTLED`, `SYNTAX_ERROR`,
`EXECUTION_ERROR`.

---

## Kill switches

### Per-tenant kill

```python
from hub.apps.tenants.models import Tenant
Tenant.objects.filter(slug="<slug>").update(
    semantic_graphql_ld_enabled=False,
)
```

Effective on the next request — the capability gate reads the flag
on every call (no cache).

### Cluster-wide kill

The endpoint is mounted from `hub/apps/semantic/urls.py`. To
disable cluster-wide, comment out the route + redeploy:

```python
# path("graphql", SemanticGraphQLView.as_view(), name="semantic-graphql-ld"),
```

After redeploy the URL returns 404. Any in-flight requests at
deploy-time are bounded by the 10 s timeout.

> **Follow-on** — wire a `SEMANTIC_GRAPHQL_HARD_DISABLE` Django
> setting that short-circuits the view to return 503 without
> needing a redeploy. Currently the per-tenant flag flip is the
> closest fast-acting kill.

---

## Schema

The schema lives at `hub/apps/graphql_ld/schema.py` and is built
**once at import time** (REQ-SEM-GQL-001 mandates "cached, not
regenerated per request"). To regenerate after an ontology
change, redeploy. Today the schema is hand-shaped from the
canonical `Asset` / `Contract` / `Dataset` models; a future
enhancement may auto-derive the types from the Meshant ontology
Turtle file.

Available types:

- `Asset { id, name }` (`assets` list, `asset(id)` point lookup).
- `Contract { id, version, originalSpecType }` (`contracts` list).
- `Dataset { id, format }` (`datasets` list).

---

## Related docs

- Spec: `openspec/changes/preprod01/specs/semantic-graphql-ld/spec.md`.
- View / caps: [hub/apps/graphql_ld/views.py](../../hub/apps/graphql_ld/views.py).
- Resolvers: [hub/apps/graphql_ld/resolvers.py](../../hub/apps/graphql_ld/resolvers.py).
- Schema: [hub/apps/graphql_ld/schema.py](../../hub/apps/graphql_ld/schema.py).
- Tests: [hub/apps/graphql_ld/tests/test_resolvers.py](../../hub/apps/graphql_ld/tests/test_resolvers.py).
- Frontend playground: [frontend/src/features/semantic/components/GraphQLLDPlayground.tsx](../../frontend/src/features/semantic/components/GraphQLLDPlayground.tsx).
- Bundle-size CI gate: [.github/workflows/bundle-size-check.yml](../../.github/workflows/bundle-size-check.yml).
