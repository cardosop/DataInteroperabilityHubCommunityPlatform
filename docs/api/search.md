# Search API

Canonical endpoint: `GET /api/search/?q=<term>&types=assets,contracts`

## Rate Limits (Phase 273.2)

| Endpoint | Limit | Header |
|----------|-------|--------|
| `/api/search/` | 60 req/min/tenant | `Retry-After` |
| `/api/v1/search/suggestions/` | 120 req/min/tenant | `Retry-After` |
| `/api/v1/semantic/sparql/` | 10 req/min/tenant | `Retry-After` |
| `/api/v1/semantic/dereference/` | 300 req/min/tenant | `Retry-After` |
| `/api/v1/semantic/rdf-ingest/` | 30 req/min/tenant | `Retry-After` |

Rate limits are per-tenant (cache key includes tenant_id). Tenant A's
exhaustion does not affect tenant B. On 429, the response includes a
`Retry-After` header with the number of seconds to wait.

## Error Envelope (Phase 273.5)

All error responses use the canonical envelope:

```json
{
  "error": {
    "code": "QUERY_REQUIRED",
    "message": "The 'q' query parameter is required.",
    "http_status": 400,
    "request_id": "uuid",
    "timestamp": "2026-05-12T00:00:00+00:00"
  }
}
```

## Audit Events (Phase 273.3)

| Event | Trigger |
|-------|---------|
| `SEARCH_PERFORMED` | Every successful search execution |
| `SEARCH_RATE_LIMIT_EXCEEDED` | 429 rate-limit hit on search |
| `SPARQL_EXECUTED` | Every SPARQL query execution (query_hash only) |
| `SPARQL_RATE_LIMIT_EXCEEDED` | 429 rate-limit hit on SPARQL |
| `RDF_INGESTED` | Successful RDF ingest |

Audit events are best-effort — audit-DB outage never blocks search response.

## Deprecation

`/api/v1/search/search/` is **deprecated** (Phase 54.1, sunset 2026-08-10).
All clients MUST migrate to `GET /api/search/`. The deprecated ViewSet
returns `Deprecation: true`, `Sunset: Mon, 10 Aug 2026 00:00:00 GMT`,
and `Link: </api/search/>; rel="successor-version"` headers.
