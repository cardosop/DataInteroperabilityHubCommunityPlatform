# JOURNEY-DC-003: Browse Resource Version History

**Persona:** [Data Consumer](../personas/data-consumer/)
**Use Cases:** UC-VER-001
**Phase:** 284 (GA Promotion)
**Status:** Implemented
**E2E:** Semantic E2E (version history paths)
**Routes:** `/datasets/{id}`, `/contracts/{id}` (version tab/history panel)

## Overview

A Data Consumer browses the version history of a dataset or contract to understand how the resource has evolved over time. They can view individual version snapshots, compare two versions to see schema and data changes, and identify when breaking changes were introduced.

## Journey Steps

1. **Navigate to resource detail** — From the catalogue or datasets list, the DC opens a dataset detail page. The page includes a "Version History" tab or panel.
2. **View version list** — The version history panel lists all versions with: version number/ID, creation timestamp, status, and a "current" badge on the active version. Source: `GET /api/v1/versioning/versions/?resource_type=dataset&resource_id={id}`.
3. **View version detail** — Clicks a version row to see its full snapshot: schema fields, data statistics, semantic metadata. Source: `GET /api/v1/versioning/versions/{version_id}/`.
4. **Compare two versions** — Selects two versions and clicks "Compare" → `GET /api/v1/versioning/compare/?resource_type=dataset&id_a={v1}&id_b={v2}`. The diff view highlights added, removed, and modified fields with color coding.

## Error Handling

- **No versions** — Renders "No version history available" when the resource has only one version.
- **Compare failure** — `<ErrorDisplay>` if one or both version IDs are invalid.
- **Resource not found** — 404 handled via `<ErrorDisplay>`; back navigation available.
- **Cross-tenant access** — Attempting to view another tenant's resource version returns 404 (not 403 — no cross-tenant leak).

## Success Criteria

- DC can view the full version history of any accessible resource.
- Version comparison highlights schema differences with clear before/after indicators.
- Version history loads within 2 seconds for resources with <100 versions.
- Cross-tenant access attempts return 404 with no information leakage.

## Related

- E2E: Semantic E2E version history paths
- CLI: `datahub versioning list/get/diff`
- SDK: `client.versioning.get_version_history/get_version/compare_versions`
- Phase: 283.6.2 (Versioning CLI), 284 (GA promotion)
