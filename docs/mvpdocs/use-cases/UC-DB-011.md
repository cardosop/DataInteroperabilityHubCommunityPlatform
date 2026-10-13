# UC-DB-011: Run Databricks Job

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P4 Test:** `hub/apps/databricks_admin/tests/test_jobs_journeys.py::TestJOURNEYDB011RunDatabricksJob::test_poller_state_machine`

## Description

Run Databricks jobs from the Hub: browse the mirrored job/run fleet (the 4.2 mirror — zero network on the READ leg), define jobs through the jobs client's gate-first validation (the task allowlist and the mandatory cluster policy — refused definitions never reach the jobs API), and dispatch run-now through the 4.4 service, which polls `runs/get` with backoff to a terminal state and emits the run's audit rows, an OpenLineage event, a stored duration×size cost estimate, and the failure webhook.

## Preconditions

- A registered `ACTIVE` workspace; the tenant's `databricks_control_plane_enabled` flag.
- Task types within the allowlist (Spark SQL, SQL warehouse, notebook); Python tasks only behind `databricks_jobs_python_tasks_enabled`.
- Every job cluster carries a `cluster_policy_id` (an `existing_cluster_id` task is not a job cluster — the guard leaves it alone).

## Steps

1. User GETs `/api/v1/databricks/workspaces/{id}/jobs/` — the paginated mirror rows (`job_id`/`name`/`task_config`/`schedule`), tenant- and workspace-scoped, zero network; `.../jobs/{job_id}/runs/` lists the nested run rows (`run_id`/`lifecycle_state`/`result_state`/`duration_ms`/`error_message`).
2. The jobs client's gate validates the definition BEFORE any jobs API call: a task outside the allowlist (or a malformed/ambiguous shape) or a job cluster without a cluster policy id raises `DatabricksJobTaskError` (`DATABRICKS_JOB_TASK_FORBIDDEN`).
3. User triggers run-now — the 4.4 service creates a Hub `Job` (`JobType.DATABRICKS_JOB_RUN`, PENDING), calls the Databricks run-now API, records the run id, and polls `runs/get` with backoff until a terminal lifecycle state or the wall-clock budget.
4. The terminal transition records the run's audit row (`RUN_SUCCEEDED`/`RUN_FAILED` — one row per Hub-side transition), the OpenLineage COMPLETE/FAIL event, and the stored cost estimate in `result_json`.

## Expected Outcome

- Polling terminates in a recorded state with exactly one terminal audit row (plus the dispatch-time `RUN_STARTED`), attributed to the acting user.
- Terminal failures fire the `databricks.job.run.failed` webhook for subscribed tenants; a delivery outage never blocks the transition.
- The Hub Job's `result_json` carries the `databricks_run_state` and the stored cost estimate (`duration_seconds`, `size_factor`, `dbh_rate`, `estimated_cost`).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Forbidden task type (allowlist / Python flag off) | `DatabricksJobTaskError` `DATABRICKS_JOB_TASK_FORBIDDEN` (403 at the API boundary), ZERO jobs API calls |
| Job cluster without a cluster policy id | `DatabricksJobTaskError` `DATABRICKS_JOB_TASK_FORBIDDEN`, ZERO jobs API calls |
| Run-now dispatch rejected by the workspace | Hub Job FAILED with the classified code + `RUN_FAILED` (no `RUN_STARTED` for a run that never dispatched), webhook fired |
| Run cancelled mid-flight | Terminal `result_state` `CANCELED` → Hub Job `CANCELLED` recorded |
| Poll budget exhausted (never terminal) | Hub Job FAILED "poll budget exhausted" + `RUN_FAILED` (fail-closed — never a fabricated success) |
| Terminal state without a result state | Hub Job FAILED (fail-closed — never a fabricated success) |

## Related

- Concepts: [Jobs](../concepts/jobs.md), [Lineage](../concepts/lineage.md)
- Journeys: [JOURNEY-DB-011 -- Run a Databricks Job](../journeys/JOURNEY-DB-011.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
