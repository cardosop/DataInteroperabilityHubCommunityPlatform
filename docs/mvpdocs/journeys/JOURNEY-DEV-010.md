# JOURNEY-DEV-010: Query via GraphQL-LD Endpoint

**Persona:** [External Developer](../personas/external-developer/)
**Use Cases:** UC-SEM-GQL-001
**Phase:** 284 (GA Promotion — 284.B)
**Status:** Implemented
**E2E:** `graphql-ld.spec.ts`
**Routes:** `/semantic?tab=graphql` (playground), `POST /api/v1/semantic/graphql` (API)

## Overview

An External Developer queries the tenant's Linked-Data surface through a GraphQL endpoint. The endpoint translates GraphQL queries against the tenant's named graph into canonical Django ORM lookups for Asset, Contract, and Dataset types. The developer uses the in-browser playground to explore the schema, compose queries with syntax highlighting, and execute queries with variables — all subject to depth ≤5, complexity ≤100, and a 10-second hard timeout.

## Journey Steps

1. **Open GraphQL playground** — Navigate to `/semantic?tab=graphql`. The `GraphQLLDPlayground` component lazy-loads with: query input textarea (pre-filled with a default query), variables input textarea, Run button, and response panel.
2. **Execute a simple query** — The default query `{ assets { id name } }` is pre-filled. Clicks "Run" → `POST /api/v1/semantic/graphql` with `{ query: "{ assets { id name } }" }`. Response renders in the `CodeBlock` component as formatted JSON.
3. **Use variables** — Enters a parameterized query: `query Q($id: ID!) { asset(id: $id) { id name } }` and sets variables to `{"id": "<asset-uuid>"}`. The variables JSON is validated client-side before submission.
4. **Handle error states** — The playground surfaces backend errors via `<ErrorDisplay>`:
   - Syntax error → "Invalid GraphQL syntax" with parse error location
   - Depth exceeded → "Query depth N exceeds limit 5"
   - Complexity exceeded → "Query complexity N exceeds limit 100"
   - Timeout → "GraphQL query exceeded 10.0s timeout"
   - Flag off → "GraphQL-LD endpoint not enabled for this tenant"
   - Rate limited → Retry-After header honoured
5. **Dark mode usage** — Toggles dark mode; the playground re-renders with Phase 282 CSS custom properties. Query input, response panel, and Run button remain visible and usable.

## Error Handling

- **Invalid variables JSON** — Client-side validation catches parse errors before submission; shows inline error.
- **Empty query** — Backend returns 400 "query is required."
- **Cross-tenant isolation** — `asset(id: <cross-tenant-uuid>)` returns `data.asset: null` (never 403/404 — no information leakage).
- **Network failure** — `<ErrorDisplay>` with retry; query text preserved in the input.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `SEMANTIC_GRAPHQL_QUERY` | Every query attempt (all outcomes) | 30 days |
| `SEMANTIC_GRAPHQL_QUERY` (outcome=THROTTLED) | Rate limit hit | 30 days |

Query body is NEVER logged — only the SHA-256 hash in `details_json.query_sha256`.

## Success Criteria

- Developer can execute a valid GraphQL query and see results in under 3 seconds.
- All 7 error outcomes (syntax/depth/complexity/timeout/flag-off/throttle/execution) produce user-facing error messages.
- Dark mode renders all playground elements with correct contrast.
- Rate limit (60 q/min/user) enforced; 429 includes Retry-After header.
- Every query emits a `SEMANTIC_GRAPHQL_QUERY` audit row.

## Related

- E2E: `frontend/e2e/journeys/ai-ml-semantic/graphql-ld.spec.ts` (284.B.4)
- Runbook: [RB-SEM-001-graphql-ld.md](../../runbooks/RB-SEM-001-graphql-ld.md)
- Components: `GraphQLLDPlayground`
- CLI: `datahub semantic graphql query --query "..." [--file] [--variables] [--format]`
- SDK: `client.semantic.execute_graphql_ld(query, variables)`
- Backend: `hub/apps/graphql_ld/views.py::SemanticGraphQLView` (525L)
- Feature flag: `semantic_graphql_ld_enabled` (GA, opt-in, default_new=False)
- Phase: 230.13, 284.B (DRAFT→GA promotion)
