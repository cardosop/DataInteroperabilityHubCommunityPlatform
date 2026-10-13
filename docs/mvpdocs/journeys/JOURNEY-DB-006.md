# JOURNEY-DB-006: Inspect Table Permissions

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-006

## Overview

A data engineer checks who can do what on a Unity Catalog table — and what they themselves can do. The Hub surfaces effective permissions from the UC REST permissions API, and interactive access is enforced natively by Unity Catalog via the user's OBO token, so the Hub can always explain a denial.

## Journey Steps

1. **Open a table** — From the catalog browser the user opens a table detail page.
2. **View "my effective permissions"** — The Hub computes the user's effective privileges (`GET /api/2.1/unity-catalog/effective-permissions/...`) and renders them on the table page.
3. **View all assignments** — A platform admin additionally sees the direct permission assignments per principal from the live UC answer; the grants-bridge bindings (`APPLIED` / `OUT_OF_SYNC` / `REVOKED`) land with P2 (task 2.6).
4. **Understand a denial** — Without an OBO binding the detail fails closed (`502 DATABRICKS_OBO_REFRESH_FAILED`, zero network calls — the shipped P1 contract); the Hub-ABAC vs UC denial-origin distinction lands with P2 interactive execution.

## Success Criteria

- Effective permissions come from the UC API, never from stale Hub guesswork.
- The fail-closed OBO surface (no binding → `502 DATABRICKS_OBO_REFRESH_FAILED`) is visually distinct in the table detail.
- Cross-tenant access attempts return 404 (the shipped 1.3 tenant-scoping contract).

## Related

- Concepts: [Governance](../concepts/governance.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-005](JOURNEY-DB-005.md) (Browse the Unity Catalog), [JOURNEY-DB-009](JOURNEY-DB-009.md) (Manage UC Grants)
