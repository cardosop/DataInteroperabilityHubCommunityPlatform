# API Versioning Policy

**Owner**: Platform Engineering  
**Last reviewed**: 2026-05-13  
**Next review**: 2026-08-11  

## Scope

This policy governs how the Meshant Data Interoperability Hub API evolves over time. It applies to all REST endpoints under `/api/v1/`, the GraphQL-LD endpoint at `/graphql/`, and the OpenAPI schema published at `/api/v1/openapi.yaml`.

## Current Version

| Property | Value |
|---|---|
| Current API version | `v1.0.0` |
| Supported versions | `v1.0.0` |
| Base path | `/api/v1/` |
| OpenAPI spec | `/api/v1/openapi.yaml` |
| Version discovery | `GET /api/v1/` (see [277.B.110](#related-tasks)) |

The `APIVersionManager` class at `hub/apps/api/versioning.py` is the canonical source of truth for `CURRENT_VERSION`, `SUPPORTED_VERSIONS`, and the `DEPRECATED_ENDPOINTS` registry.

## Versioning Rules

### 1. Additive-only for `/api/v1/`

New fields, optional query parameters, and new endpoints may be added to `/api/v1/` without a version bump. Clients that ignore unknown fields are forward-compatible.

**Permitted on v1 without version bump:**
- Adding a new endpoint (e.g., `GET /api/v1/new-resource/`)
- Adding an optional field to a response body
- Adding an optional query parameter
- Adding a new enum value (clients must treat unknown values as passthrough)

**Requires a new major version:**
- Removing or renaming an existing field
- Changing a field's type (e.g., string → integer)
- Changing a required field to optional, or vice versa
- Removing an endpoint
- Changing authentication requirements on an existing endpoint

### 2. Deprecation Window: 90 days

When an endpoint or field must be removed, it goes through a 90-day deprecation window:

| Milestone | Day | Action |
|---|---|---|
| Deprecation announced | T+0 | `Deprecation: true` header added. Deprecated endpoint registered in `APIVersionManager.DEPRECATED_ENDPOINTS`. Warning header emitted per RFC 7234. |
| Sunset header added | T+0 | `Sunset: <RFC 7231 date>` header set to T+90. |
| v2 replacement available | T+0–T+30 | `Link: <replacement>; rel="successor-version"` header pointing to v2 equivalent. |
| Client migration window | T+0–T+90 | Deprecated endpoint remains functional. SDKs emit warnings. `GET /api/v1/` lists the endpoint under `deprecated_endpoints`. |
| Hard removal | T+90 | Endpoint returns 410 Gone with `Link` pointing to replacement. Rows archived in database. |

**High-volume endpoints** (≥100 req/min averaged over 7 days) get a 180-day window.

### 3. RFC 8594 Headers

Every deprecated endpoint returns these response headers:

```
Deprecation: true
Sunset: Sat, 15 Nov 2026 00:00:00 GMT
Link: </api/v2/search/>; rel="successor-version"
```

The `APIVersionMiddleware` (Django middleware at `hub/apps/api/versioning.py:266`) adds these headers automatically for any endpoint registered in `APIVersionManager.DEPRECATED_ENDPOINTS`.

Additionally, all `/api/` responses carry:
```
X-API-Version: v1.0.0
X-API-Supported-Versions: v1.0.0
```

### 4. Parallel `/api/v2/` for Breaking Changes

When breaking changes are unavoidable, a new major version is deployed in parallel:

```
/api/v1/  — stable, maintained during v2 migration
/api/v2/  — new major version with breaking changes
```

Both versions run simultaneously during the deprecation window. The v1 path is removed only after the deprecation window expires.

### 5. GraphQL-LD as v2 Path

The GraphQL-LD endpoint at `/graphql/` is the designated v2 surface for semantic and federated queries. It follows the same additive-only policy and uses schema deprecation (`@deprecated` directives) rather than endpoint removal.

### 6. SDKs Follow Semver

| SDK | Package | Version Strategy |
|---|---|---|
| Python | `datahub-interoperability` | Semver: MAJOR.MINOR.PATCH. Major bumps when API v2 ships or client-breaking changes occur. |
| JavaScript | `@datahub/interoperability-sdk` | Same. Published to npm with corresponding version tags. |
| TypeScript | `sdk/typescript/` | OpenAPI-generated. Regenerated on every API change. Version matches OpenAPI spec version. |
| CLI | `datahub-cli` | Follows Python SDK major version. Deprecated command flags emit warnings for 2 minor releases before removal. |

### 7. Breaking Change Detection

CI enforces this policy through automated gates:

| Gate | Job | Mechanism |
|---|---|---|
| Endpoint removal detection | `contract-test-openapi` | Compares live schema against committed baseline; fails on removed paths |
| Type change detection | `contract-test-openapi` | Validates response schemas; fails on renamed/missing required fields |
| OpenAPI drift | `generate-openapi-yaml --check` | SHA-256 comparison of committed vs generated YAML |
| Completeness | `lint-openapi-completeness` | Every Django URL must have an OpenAPI path entry |
| CLI/SDK parity | `lint-cli-sdk-openapi-parity` | Every OpenAPI path must have CLI + SDK coverage |

## Programmatic Discovery

Clients can discover version information at runtime:

```bash
curl https://api.stagingmeshant-internal.example.com/api/v1/ | jq .
```

Returns:
```json
{
  "current_version": "v1.0.0",
  "supported_versions": ["v1.0.0"],
  "deprecated_endpoints": [
    {
      "path": "/api/v1/search/",
      "method": "GET",
      "deprecated_since": "2026-03-19",
      "sunset_date": "2026-04-18",
      "replacement": "/api/search/",
      "migration_guide": "Phase 54: migrate to UnifiedSearchView at /api/search/"
    }
  ],
  "links": {
    "openapi_schema": "/api/v1/openapi.yaml",
    "openapi_json": "/api/v1/openapi.json",
    "changelog": "https://meshant-internal.example.com/changelog",
    "versioning_policy": "https://meshant-internal.example.com/api/versioning"
  }
}
```

Rate limited to 30 requests/minute per IP.

## Decisions

See `docs/adr/API-VER-001.md` for the architectural decision record behind this policy.

## Related Tasks

- 277.B.082 — API v2 plan + Sunset/Link header coverage
- 277.B.110 — Version discovery endpoint `GET /api/v1/`
- 277.B.083 — CLI/SDK OpenAPI parity checker
- 277.B.062 — OpenAPI YAML generation + drift detection

## Maintenance

This document is reviewed quarterly alongside API changes. When a new endpoint is deprecated, update the examples in this document and the `DEPRECATED_ENDPOINTS` registry in `hub/apps/api/versioning.py`.
