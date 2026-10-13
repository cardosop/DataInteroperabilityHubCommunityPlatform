# JOURNEY-DB-005: Browse the Unity Catalog

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-005

## Overview

A data engineer browses the tenant's registered workspace Unity Catalog through the Hub: catalogs, schemas, tables, views, volumes, and registered models, mirrored into RLS-scoped Hub models by the UC metadata sync job. Browsing is read-only and executes with the user's OBO token, so only objects the user can see in Databricks appear.

## Journey Steps

1. **Open the catalog browser** — The user opens the Databricks catalog browser for a workspace. The Hub serves the mirrored catalog list with search, filters, and pagination.
2. **Drill into a schema** — The user selects a catalog and browses its schemas, then its tables, with breadcrumbs and virtual scrolling for large catalogs.
3. **Open a table detail** — The Hub shows columns, types, and metadata from the mirror plus the LIVE effective-permissions answer (OBO-backed — the 1.3 table-detail contract).
4. **Check freshness** — The mirror shows its `last_synced_at` and a stale marker when the daily `DATABRICKS_UC_METADATA_SYNC` job has fallen behind.
5. **Search** — The UC search feed enriches the Hub [search](../concepts/search.md) index so catalog objects surface in global search results.

## Success Criteria

- Mirror rows are tenant-scoped via the workspace relationship (RLS) — tenant A never sees tenant B's catalogs.
- The sync job is idempotent and emits `DATABRICKS_UC_METADATA_SYNCED` / `DATABRICKS_UC_METADATA_SYNC_FAILED`.
- Browse endpoints are throttled (`databricks_uc_browse` 30/minute scope — the standard databricks throttle convention).
- Lineage reads enrich the [lineage](../concepts/lineage.md) subsystem (lands with task 1.6).

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Search](../concepts/search.md), [Lineage](../concepts/lineage.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-006](JOURNEY-DB-006.md) (Inspect Table Permissions)
