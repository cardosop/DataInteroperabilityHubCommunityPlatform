# API audit artifacts

This directory contains API audit reports, endpoint inventories, and discrepancy notes.

## Canonical API paths (current)

The following paths are the **canonical** API v1 URLs. Use these in new code and tests.

- **Tenants**: `/api/v1/tenants/` (list), `/api/v1/tenants/{id}/` (detail), `/api/v1/tenants/{id}/config/`, etc.
- **Users**: `/api/v1/users/` (list), `/api/v1/users/{id}/` (detail), `/api/v1/users/invite/`, `/api/v1/users/roles/`, etc.

Do **not** use duplicate segments such as `/api/v1/tenants/tenants/` or `/api/v1/users/users/`; those were legacy references and are not routed by the API.

Older audit artifacts (e.g. `documentation-endpoint-audit.json`, `openapi-spec-discrepancies.md`) may still mention the duplicate-segment paths as "Actual" or in context; treat those as historical. The live URL configuration is in `hub/apps/api/urls.py` and `hub/apps/tenants/urls.py`, `hub/apps/users/urls.py`.
