# UC-DB-013: Export Dataset to Databricks

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P6 Test:** `hub/apps/databricks_admin/tests/test_dlt_movement_journeys.py::TestJOURNEYDB013ExportDatasetToDatabricks::test_export_spine`

## Description

Export a Hub dataset into a Databricks Unity Catalog table through the dlt movement spine: the scheduled-export lifecycle dispatches `execute_dlt_export`, ODCS pre-export validation runs before any movement work, the managed-volume staging target and a scoped write credential resolve fail-closed, and the pipeline runs inside the guard-bypass executor scope.

## Preconditions

- A `ScheduledExport` with the `DATABRICKS_TABLE` destination (host, catalog, schema).
- Every contract-bearing source carries an ACTIVE ODCS contract with VALID or WARNING_ONLY validation status.
- Credential material resolving to a token for the scoped write credential.

## Steps

1. Data engineer schedules (or manually triggers) the export.
2. The pre-flight validates the ODCS contracts of every scoped source.
3. The staging target resolves from the destination catalog/schema; the scoped write credential binds the material to the target.
4. The dlt pipeline runs inside the guard-bypass scope.
5. The run's terminal state records the outcome; audit rows record the transitions.

## Expected Outcome

- The run completes with the dlt load outcome recorded on the run row.
- Invalid contracts or missing credentials refuse the run with classified errors and zero side effects.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Invalid ODCS contract in scope | Refusal with `EXPORT_CONTRACT_VALIDATION_FAILED`, zero side effects |
| No scoped write credential material | Refusal with `DLT_CREDENTIAL_NOT_RESOLVED` |
| Invalid staging catalog/schema | Refusal with `DLT_STAGING_REFUSED` |
| Guard-bypass scope outside the pipeline | `DLT_PIPELINE_SCOPE_VIOLATION` |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Datasets](../concepts/datasets.md)
- Journeys: [JOURNEY-DB-013 -- Export a Dataset to Databricks](../journeys/JOURNEY-DB-013.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
