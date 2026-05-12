# ADR-0005: API Versioning for Warehouse Connectivity (Phase 275.A.22)

**Status:** Accepted
**Date:** 2026-05-12

## Context

Phase 275.D introduces two new API surfaces:
- `GET /api/v1/datasets/{id}/rows/` — Records API (JSON + Arrow)
- `GET /api/v1/datasets/{id}/share/` — Delta Sharing endpoint

Both live under the existing `/api/v1/` prefix served by the DatasetViewSet.
We need a versioning policy that allows these endpoints to evolve without
breaking existing clients.

## Decision

**URL-versioning** — endpoints are mounted under `/api/v1/` as `@action`
methods on the existing `DatasetViewSet`. If a breaking change is needed
in the future:

1. The current endpoint continues to serve under `/api/v1/datasets/{id}/rows/`
2. A new version is mounted under `/api/v2/datasets/{id}/rows/`
3. The old version carries `Deprecation: true` + `Sunset:` header (RFC 8594)
   for a 6-month deprecation window
4. After 6 months, the old version returns 410 Gone

This mirrors the Phase 240.3.B.3 `deprecated-dual-mount` precedent
(`/api/v1/search/search/` → `/api/search/`).

## Consequences

- No URL path changes for existing clients during the 6-month window
- New `Accept: application/vnd.apache.arrow.stream` content type is
  additive (non-breaking) — clients that don't send it get JSON
- Delta Sharing protocol version is negotiated via the response body
  `protocol.version` field, not the URL
- Breaking changes to the response shape must go through a formal
  deprecation cycle per this ADR
