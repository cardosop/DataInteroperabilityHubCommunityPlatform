# UC-DB-018: Run dbt Transformation on Databricks

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P11 Test:** `hub/apps/transformation/tests/test_transformation_databricks_journeys.py::TestJOURNEYDB018RunDbtOnDatabricks::test_target_selection`

## Description

Run dbt transformations against Databricks compute — a SQL warehouse (direct) or a Databricks job — while Prefect orchestration stays unchanged and only the execution target switches from the local dbt-native execution path.

## Preconditions

- A registered workspace with a managed SQL warehouse (or job support).
- Credentials resolvable via the existing dbt credential resolver's Databricks branch.

## Steps

1. User defines a transformation and selects the Databricks target.
2. Artifacts and seeds stage through the workspace's managed volume.
3. The Prefect flow executes dbt against the Databricks target.
4. Results, run metadata, and lineage flow into Hub lineage and the cost ledger.

## Expected Outcome

- Warehouse-direct and job-based targets both complete end-to-end runs.
- Local-executor targets remain regression-free.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Warehouse stopped at run time | Retry/state error surfaced from the target |
| Credential resolution fails | Run fails with a masked credential error |

## Related

- Concepts: [Contracts](../concepts/contracts.md), [Lineage](../concepts/lineage.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-018 -- Run a dbt Transformation on Databricks](../journeys/JOURNEY-DB-018.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
