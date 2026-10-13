# UC-DB-017: Manage DLT Pipeline

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P10 Test:** `hub/apps/databricks_admin/tests/test_dlt_pipeline_journeys.py::TestJOURNEYDB017ManageDLTPipeline::test_update_polling`

## Description

Manage Delta Live Tables pipelines from the Hub: allowlist-validated settings, start updates with full or selective refresh, poll update state to terminal, and stop pipelines — with conflict detection and cost/lineage emission. The DLT page and the `dlt` CLI ride the same API surface.

## Preconditions

- A registered workspace; `databricks_control_plane_enabled=True` AND `databricks_dlt_pipelines_enabled=True` (the D7 surface flag, default off).
- Pipeline settings within the `databricks.dlt.create` chain allowlist — every cluster carries a policy id and the channel is one of `CURRENT`/`PREVIEW`.

## Steps

1. User creates a pipeline spec; the chain validates the settings allowlist, cluster policy, and channel before any Pipelines API call; a PASS ships the settings verbatim through the pipelines client.
2. User starts an update (`full_refresh` or `refresh_selection` — the API's documented `{tables, files}` object); the Hub polls the update state to a terminal state (`COMPLETED`/`FAILED`/`CANCELED`/`TIMED_OUT`).
3. Terminal states emit `DATABRICKS_DLT_UPDATE_SUCCEEDED` / `DATABRICKS_DLT_UPDATE_FAILED` (exactly once each) + OpenLineage + one DBU ledger row through the cost-recording seam.
4. Stop cancels the active update (a no-op when the pipeline is `IDLE`); a second start while active returns `DATABRICKS_DLT_UPDATE_CONFLICT` with zero API calls.

## Expected Outcome

- Pipeline and update state mirrors stay consistent with the Databricks side — states are the Pipelines API's reported values, never invented.
- Failures fire the `databricks.dlt.update.failed` webhook.

## Error Handling

| Condition                                   | Expected Response                                              |
|---------------------------------------------|----------------------------------------------------------------|
| `databricks_dlt_pipelines_enabled` flag off | `403` with `DATABRICKS_DLT_PIPELINES_DISABLED`                 |
| Active update already running               | `409` with `DATABRICKS_DLT_UPDATE_CONFLICT` (zero API calls)   |
| Settings outside the allowlist              | `400` chain refusal (`DATABRICKS_DLT_SETTING_FORBIDDEN`)       |
| Cluster without a policy id                 | `400` chain refusal (`DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED`) |
| Channel outside `CURRENT`/`PREVIEW`         | `400` chain refusal (`DATABRICKS_DLT_CHANNEL_INVALID`)         |

## Related

- Concepts: [Jobs](../concepts/jobs.md), [Lineage](../concepts/lineage.md)
- Journeys: [JOURNEY-DB-017 -- Manage a DLT Pipeline](../journeys/JOURNEY-DB-017.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
