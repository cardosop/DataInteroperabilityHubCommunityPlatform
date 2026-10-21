# UC-DB-006: View Effective Permissions

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P1 Test:** `hub/apps/databricks_admin/tests/test_uc_catalog_journeys.py::TestJOURNEYDB006InspectTablePermissions::test_effective_permissions_mapping`

## Description

View the effective permissions of a Unity Catalog object — both the user's own effective privileges and (for admins) all direct assignments — computed from the UC REST permissions API, and distinguish Hub-ABAC denials from Unity Catalog denials.

## Preconditions

- A registered `ACTIVE` workspace with mirrored catalog objects.

## Steps

1. User calls `GET /api/v1/databricks/workspaces/{id}/uc/tables/{table_id}/` — the table detail ALWAYS carries the effective permissions (reconciled: no separate expansion parameter).
2. The Hub reads `GET /api/2.1/unity-catalog/effective-permissions/table/{full_name}` with the user's OBO token.
3. The UI renders the user's privileges from the live UC answer (the 1.9 "my effective permissions" panel); the grants-bridge statuses (`APPLIED` / `OUT_OF_SYNC` / `REVOKED`) land with P2 (grants bridge, task 2.6).
4. The denial-origin distinction (Hub ABAC vs UC) lands with P2 interactive execution — P1 ships the fail-closed surface: without an OBO binding the detail answers `502 DATABRICKS_OBO_REFRESH_FAILED` with ZERO network calls.

## Expected Outcome

- Effective permissions reflect the live UC state, not cached guesswork.
- Cross-tenant attempts return 404 (the shipped 1.3 tenant-scoping contract).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| No OBO binding for the workspace | `502` with `DATABRICKS_OBO_REFRESH_FAILED` (fail-closed, zero network calls) |
| Object not found | `404` (DRF NotFound, the standard envelope) |
| UC API pagination edge (empty page with token) | The sync's `_list_pages` keeps paging until `next_page_token` is absent (pinned in test_uc_sync.py) |

## Related

- Concepts: [Governance](../concepts/governance.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-006 -- Inspect Table Permissions](../journeys/JOURNEY-DB-006.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
