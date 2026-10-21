# JOURNEY-DB-017: Manage a DLT Pipeline

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-017

## Overview

A data engineer manages Delta Live Tables pipelines from the Hub: define settings (allowlist-validated, cluster policy attached), start updates with full or selective refresh, poll update state, and stop pipelines. Hub scheduled-ingestion/export/transformation configs map onto DLT specs. The whole surface sits behind the `databricks_dlt_pipelines_enabled` tenant flag (default off) — the DLT page and the `dlt` CLI ride the same API surface.

## Journey Steps

1. **List pipelines** — The user opens the DLT page showing each pipeline's state as reported by the Pipelines API (`IDLE`, `ACTIVE`, `DELETING`, `FAILED`, `DELETED` — never invented) and its latest update status, mirror-first with zero network reads on the page's behalf.
2. **Create a pipeline** — The user defines the pipeline spec; the `databricks.dlt.create` chain validates the settings allowlist, cluster policy, and channel before any Pipelines API call.
3. **Start an update** — The Hub starts a full or selective refresh (`full_refresh` / `refresh_selection` — the API's documented `{tables, files}` object, shipped verbatim) and polls the update through the 12-state vocabulary (`CREATING`, `QUEUED`, `WAITING_FOR_RESOURCES`, `SETTING_UP_TABLES`, `MAINTENANCE`, `RUNNING`, `STOPPING`, `CANCELING`, …) to a terminal state (`COMPLETED`, `FAILED`, `CANCELED`, or `TIMED_OUT`) with a non-blocking UI.
4. **Stop or edit** — Stop cancels the active update (a no-op with zero API calls when the pipeline is `IDLE`); edits go through the same allowlist validation.
5. **Observe** — Pipeline lifecycle actions emit `DATABRICKS_DLT_PIPELINE_CREATED/UPDATED/DELETED`; updates emit `DATABRICKS_DLT_UPDATE_STARTED/SUCCEEDED/FAILED`, OpenLineage events, and a DBU estimate into the P7 ledger; concurrent starts surface `DATABRICKS_DLT_UPDATE_CONFLICT` (409, zero API calls).

## Success Criteria

- A second update while one is active returns `DATABRICKS_DLT_UPDATE_CONFLICT`.
- Settings outside the allowlist, policy-less clusters, and invalid channels are rejected by the chain with zero Pipelines API calls.
- Terminal update states each emit exactly one audit event.
- Failures fire the `databricks.dlt.update.failed` webhook.

## Related

- Concepts: [Jobs](../concepts/jobs.md), [Lineage](../concepts/lineage.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-011](JOURNEY-DB-011.md) (Run a Databricks Job)
