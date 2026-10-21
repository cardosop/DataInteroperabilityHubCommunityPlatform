# ADR-API-VER-001: API Versioning Strategy (v2 Plan)

**Status:** Accepted
**Date:** 2026-05-13
**Phase:** 277.B.024

## Context

The Meshant API currently serves under a single `/api/v1/` prefix. Several
endpoints have been deprecated (legacy search, asset middleware) but no
formal v2 strategy exists. Phase 273.1.8 added RFC 8594 Sunset/Link headers
to the legacy search endpoint as a precedent.

## Decision

**In-place additive changes** for non-breaking changes. **Parallel routes**
(`/api/v2/...`) for breaking changes, with `/api/v1/` preserved for a
6-month deprecation window.

## Sunset Header Policy

Every deprecated endpoint MUST emit:
- `Deprecation: true`
- `Sunset: <RFC 7231 date>` (90-day window from deprecation date)
- `Link: </api/v2/...>; rel="successor-version"` (if successor exists)

## Currently Deprecated Endpoints

| Endpoint | Successor | Sunset Date |
|----------|-----------|-------------|
| `/api/v1/search/search/` | `/api/search/` | 2026-08-10 |
| `/api/v1/assets/deprecated-endpoint` | TBD | Pending |

## v2 Candidate Endpoints

The following endpoints are candidates for v2 breaking changes:
1. Records API — cursor-based pagination → StandardCursorPagination alignment
2. Compliance runs — response shape standardized to `format_error()`
3. Governance approval — ABAC verdict rendering in error responses

## Minimum Deprecation Window

90 days from deprecation announcement to endpoint removal per RFC 8594.
6-month window for high-volume endpoints (search, marketplace).
