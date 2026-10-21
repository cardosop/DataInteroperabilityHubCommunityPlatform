# JOURNEY-DB-011: Run a Databricks Job

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-011

## Overview

A data engineer runs Databricks jobs from the Hub. The jobs page is MIRROR-FIRST — the Hub mirrors the workspace's job definitions and run rows (`DatabricksJob`/`DatabricksJobRun`, refreshed live from the 2.1 jobs API) and never invents a state. Job definitions pass the jobs client's GATE-FIRST validation before any jobs API call: the task allowlist (Spark SQL, SQL warehouse, and notebook tasks; Python tasks flag-gated) plus the mandatory cluster policy on every job cluster — a refused definition raises `DATABRICKS_JOB_TASK_FORBIDDEN` with ZERO calls. Run-now dispatches through the 4.4 service onto the Hub `Job` machinery (`JobType.DATABRICKS_JOB_RUN`): the run is followed by a backoff poller (2s initial, ×1.5 per step, capped at 30s, wall-clock budget) to a terminal state, which emits the run's audit rows (`RUN_STARTED` at dispatch, `RUN_SUCCEEDED`/`RUN_FAILED` at the terminal state — one row per Hub-side transition), an OpenLineage run event (capability-gated), and a duration×size cost ESTIMATE stored on the Hub Job (`result_json.cost_estimate` — stored, not billed; cost attribution lands with P7). A terminal failure also fires the `databricks.job.run.failed` webhook.

## Journey Steps

1. **Browse jobs** — GET `/api/v1/databricks/workspaces/{id}/jobs/` returns the paginated mirror rows (zero network — the READ leg serves the 4.2 mirror; the workspace registry gates the surface); GET `.../jobs/{job_id}/runs/` lists the run rows nested under a job (the Databricks-side string id, not a UUID).
2. **Define a job (gated)** — the jobs client's gate runs BEFORE any jobs API call: tasks outside the allowlist (or ambiguous/malformed task shapes) and job clusters without a cluster policy id raise `DatabricksJobTaskError` (`DATABRICKS_JOB_TASK_FORBIDDEN` — 403 at the API boundary) with ZERO calls; an allowlisted definition ships the caller's fields exactly.
3. **Run now** — the 4.4 service creates a Hub `Job` (`DATABRICKS_JOB_RUN`, PENDING), calls the Databricks run-now API, and polls `runs/get` with backoff until a terminal lifecycle state (TERMINATED / INTERNAL_ERROR / SKIPPED) or the wall-clock budget (which fails the Job closed — never a fabricated success).
4. **Follow the run** — the Hub Job walks PENDING → RUNNING → terminal; the terminal transition records the run's audit row, the OpenLineage COMPLETE/FAIL event (behind the `lineage.openlineage_export` capability), and the stored cost estimate in `result_json`.
5. **See failures** — a failed dispatch, a terminal failure, or an exhausted poll budget fires the `databricks.job.run.failed` webhook (best-effort — a delivery outage never blocks the transition).

## Success Criteria

- Forbidden task types and policy-less job clusters are refused at definition time, with zero jobs API calls.
- The poller reaches a terminal state and emits the correct audit rows exactly once per Hub-side transition (RUN_STARTED + RUN_SUCCEEDED/RUN_FAILED) with tenant and actor attribution.
- Terminal failures fire the `databricks.job.run.failed` webhook for subscribed tenants; successes send none.
- The cost estimate is stored from the run's real duration and worker count — never billed (P7 attribution).
- Cross-tenant job access is impossible: RLS on the mirror rows and tenant-scoped lookups at every endpoint.

## Related

- Concepts: [Jobs](../concepts/jobs.md), [Lineage](../concepts/lineage.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-010](JOURNEY-DB-010.md) (Manage SQL Warehouses)
