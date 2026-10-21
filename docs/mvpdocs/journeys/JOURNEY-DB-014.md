# JOURNEY-DB-014: Ingest from a Databricks Source

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-014

## Overview

A data engineer ingests rows from a Databricks SQL warehouse table into the Hub. The ingestion form's workspace+warehouse picker stores the DERIVED `/sql/1.0/warehouses/{id}` path (never a hand-typed string) together with the workspace host. The run reads through the real `WarehouseQueryRunner` bound to the source's warehouse connection — the read SQL is bounded by an incremental cursor recorded in the dlt pipeline state, keyed per pipeline + asset: a re-run resumes from the last cursor, never a full re-read. Rows load through the dlt resource inside the guard-bypass executor scope, and the cursor advances ONLY after a successful load.

## Journey Steps

1. **Create the source** — The DE picks a workspace + warehouse in the form (the derived path and the host become the stored `source_config`); the submit is refused until a warehouse is picked.
2. **First run reads everything** — The full table read flows through the warehouse connector into the dlt load; the cursor records the max value seen.
3. **Re-runs resume from the cursor** — Subsequent runs read only rows after the recorded cursor (a parameterised `> :last_cursor` bound — the value never rides in the SQL text).
4. **Fail closed safely** — A source without a warehouse connection fails the run with `WAREHOUSE_CONNECTION_REQUIRED` before any warehouse work; a schema change on the source (the cursor column gone) resets the cursor by design — the next run re-reads everything.
5. **Audit** — Every Hub-side run emits the ingestion audit row (best-effort).

## Success Criteria

- A re-run reads ONLY the rows after the cursor — never a full re-read (pinned end-to-end).
- A connection-less source fails closed with zero warehouse HTTP.
- The stored `http_path` is the derived form the backend's `resolve_warehouse_id` accepts — never hand-typed, never placeholder-substituted.

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Datasets](../concepts/datasets.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-013](JOURNEY-DB-013.md) (Export a Dataset to Databricks)
