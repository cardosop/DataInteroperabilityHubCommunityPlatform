# JOURNEY-DB-013: Export a Dataset to Databricks

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-013

## Overview

A data engineer exports a Hub dataset into a Databricks Unity Catalog table. The movement runs through the Hub's one dlt execution spine: the scheduled-export lifecycle (or the manual run endpoint) dispatches `execute_dlt_export`; the pre-export ODCS contract validation runs BEFORE any movement work; the Databricks path resolves the tenant's managed-volume staging target (`_dlt_staging_load_volume` under the per-tenant staging schema) and binds a scoped write credential resolved from the export's credential material; the dlt pipeline runs INSIDE the guard-bypass executor scope — the only place in the repo where the read-only SQL guard is bypassed. The run's terminal state records the movement outcome and every Hub-side transition emits an audit row.

## Journey Steps

1. **Schedule or trigger the export** — The DE creates a scheduled export with the `DATABRICKS_TABLE` destination (host, catalog, schema) or triggers a manual run. The worker-run lifecycle and the manual endpoint dispatch the same canonical spine.
2. **Pre-flight validation** — Every contract-bearing source in the export's scope must carry an ACTIVE ODCS contract whose validation status is VALID or WARNING_ONLY. An invalid contract refuses the run BEFORE any credential, staging, or pipeline work (zero side effects).
3. **Staging and credential scoping** — The managed-volume staging target resolves from the destination catalog/schema (the S3 external-location path only under the per-tenant opt-in). A scoped write credential binds the resolved token material to exactly that target — a credential-less export fails closed.
4. **The pipeline runs inside the guard scope** — The dlt pipeline executes inside the executor's guard-bypass scope; outside the pipeline context the read-only guard always blocks write SQL.
5. **Terminal state and audit** — The run records COMPLETED/FAILED with the dlt outcome; `WAREHOUSE_EXPORT_STARTED` is written at dispatch and `WAREHOUSE_EXPORT_FAILED`/`DLT_EXPORT_COMPLETED` at the terminal chokepoints.

## Success Criteria

- An invalid ODCS contract fails the run with `EXPORT_CONTRACT_VALIDATION_FAILED` and zero side effects (no staging objects, no pipeline work, no STARTED row).
- A Databricks export without a scoped write credential fails closed with `DLT_CREDENTIAL_NOT_RESOLVED`.
- The guard bypass exists ONLY inside the pipeline executor — never at any API boundary.
- Every Hub-side transition emits exactly one audit row (best-effort — an audit outage never blocks the movement).

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-014](JOURNEY-DB-014.md) (Ingest from a Databricks Source)
