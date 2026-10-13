# UC-DB-014: Ingest from Databricks

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P6 Test:** `hub/apps/databricks_admin/tests/test_dlt_movement_journeys.py::TestJOURNEYDB014IngestFromDatabricksSource::test_ingestion_spine`

## Description

Ingest rows from a Databricks SQL warehouse table into the Hub through the dlt movement spine: the source form's workspace+warehouse picker stores the derived `/sql/1.0/warehouses/{id}` path; the read goes through the real `WarehouseQueryRunner` bounded by an incremental cursor in the dlt pipeline state (keyed per pipeline + asset) — a re-run resumes from the last cursor, never a full re-read.

## Preconditions

- A `ScheduledIngestion` with `DATABRICKS_SOURCE` whose `source_config` carries `warehouse_connection_id`, `table`, and optionally `cursor_field` (default `updated_at`).
- The warehouse connection's encrypted config holds the workspace credential material.

## Steps

1. Data engineer picks a workspace + warehouse in the create form (the derived path + host become the stored config).
2. The first run reads the full table and records the incremental cursor.
3. Re-runs read only rows after the cursor (the value rides as a parameter, never in the SQL text).
4. The cursor advances only after a successful load; a schema change on the source resets it by design.

## Expected Outcome

- Re-runs load only new rows — never a full re-read.
- A connection-less source fails closed with zero warehouse HTTP.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Missing `warehouse_connection_id` / no tenant-scoped connection | `WAREHOUSE_CONNECTION_REQUIRED` (409), zero HTTP |
| Invalid table ref or cursor field | `DATABRICKS_SOURCE_INCREMENTAL_ERROR` (500), fail-closed |
| Source schema change (cursor column gone) | Cursor reset — the next run re-reads everything |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Datasets](../concepts/datasets.md)
- Journeys: [JOURNEY-DB-014 -- Ingest from a Databricks Source](../journeys/JOURNEY-DB-014.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
