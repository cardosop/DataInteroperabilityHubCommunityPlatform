# ADR-API-GQL-001: GraphQL Implementation Consolidation

**Status:** Accepted
**Date:** 2026-05-13
**Phase:** 277.B.102

## Context

Three partial GraphQL implementations coexist in the codebase:

| Implementation | Library | Lines | Endpoint | Status |
|---|---|---|---|---|
| `hub/apps/graphql/` | Strawberry | 1,400 | `/graphql/` | Mounted in `hub/urls.py`; has tests |
| `hub/apps/graphql_graphene/` | Graphene-Django | 2,861 | `/graphql-graphene/` (conditional) | Import-guarded; largest codebase but no tests |
| `hub/apps/graphql_ld/` | Custom JSON-LD resolver | 805 | None | Not wired into URL conf; resolver-only |

All three are incomplete — none meets production-readiness criteria (no schema
introspection gating, no depth/complexity limits, no query cost analysis, no
auth integration beyond basic DRF token, no persisted queries).  Maintaining
three partial implementations creates a maintenance burden and confuses API
consumers (which endpoint should they use?).

## Decision

**Strawberry** (`hub/apps/graphql/`) is selected as the canonical GraphQL
implementation for GA.

Rationale:
- It is the only implementation currently mounted in the primary URL conf
  (`hub/urls.py:44`).
- It has a test suite (`hub/apps/graphql/tests/`).
- Strawberry is the modern Python GraphQL library (type-safe, code-first,
  schema-first, built-in support for Django, FastAPI, and async).
- The Django community is converging on Strawberry as the successor to
  Graphene-Django (Graphene is in maintenance-only mode since 2023).

**Graphene-Django** (`hub/apps/graphql_graphene/`) and **GraphQL-LD**
(`hub/apps/graphql_ld/`) are deprecated effective immediately.

## Consequences

### Deprecation timeline

| Milestone | Date | Action |
|---|---|---|
| Deprecation announced | 2026-05-13 | This ADR accepted |
| Graphene endpoint gated | 2026-06-01 | `/graphql-graphene/` returns 410 Gone with `Link: </graphql/>; rel="alternate"` unless `ENABLE_GRAPHQL_GRAPHENE=true` |
| Graphene removed | 2026-08-01 | `hub/apps/graphql_graphene/` directory deleted; conditional import removed from `hub/urls.py` |
| GraphQL-LD removed | 2026-06-01 | `hub/apps/graphql_ld/` directory deleted (never wired, no migration needed) |
| Strawberry GA milestone | 2026-09-01 | Schema introspection gated to staging only; depth/complexity limits enforced; query cost analysis added; persisted queries supported |

### Migration path for existing consumers

1. **Graphene-Django consumers**: The `/graphql/` (Strawberry) endpoint
   serves the same GraphQL protocol. No wire-format change is needed; clients
   only need to update their endpoint URL. Schema parity will be maintained
   during the deprecation window — any type or field present in Graphene but
   missing in Strawberry must be ported before the 2026-08-01 deletion.

2. **GraphQL-LD consumers**: The JSON-LD resolvers in `graphql_ld/resolvers.py`
   have no HTTP endpoint. If JSON-LD remains a product requirement, the
   resolver logic should be ported into the Strawberry schema as
   `@strawberry.type` definitions rather than maintaining a separate app.

### What Strawberry GA requires (post-GA gap list)

These items are out of scope for this ADR and will be implemented in follow-up
phases before the GA milestone:

1. **Schema introspection gating** — introspection enabled on staging only;
   production returns 403 with `code=SCHEMA_INTROSPECTION_DISABLED`.
2. **Query depth and complexity limits** — `max_depth` default 10;
   `max_complexity` calculated per-query; configurable per tenant.
3. **Query cost analysis** — estimate resolver call cost before execution;
   reject queries exceeding tenant's GraphQL budget.
4. **Persisted queries** — allow clients to register query hashes;
   only registered queries execute in production (safer and cachable).
5. **Auth hardening** — tenant-scoping via `tenant_context()` on every
   resolver; ABAC integration for field-level access control.
6. **Caching** — `@strawberry.cached` on expensive resolvers; CDN-cacheable
   GET-based queries via automatic persisted queries (APQ).
7. **Rate limiting** — `GraphQLUserThrottle` with per-tenant quota;
   query cost factors into rate-limit consumption.

## Related

- Strawberry docs: https://strawberry.rocks/docs
- Graphene-Django deprecation: https://github.com/graphql-python/graphene-django
- Phase 277.A.18: API surface health — GraphQL consolidation gap
- `hub/urls.py`: GraphQL URL mounting
- `hub/apps/graphql/schema.py`: Strawberry schema definition
