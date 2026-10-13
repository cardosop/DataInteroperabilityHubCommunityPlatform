# JOURNEY-DB-018: Run a dbt Transformation on Databricks

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-018

## Overview

A data engineer runs dbt transformations against Databricks compute instead of the local dbt-native execution path (the SM-path secret profiles). Orchestration stays on the existing Prefect transformation flow — only the execution target changes: a Databricks SQL warehouse (direct) or a Databricks job.

## Journey Steps

1. **Create a transformation** — The user defines a dbt transformation as usual in the Hub.
2. **Pick a Databricks target** — The user selects the Databricks warehouse or job target; credentials resolve from the registered workspace/`WarehouseConnection` (the dbt adapter already supports Databricks profiles).
3. **Stage artifacts** — Seeds and artifacts stage through the workspace's managed volume.
4. **Run** — The Prefect flow executes dbt against the Databricks target; results, run metadata, and lineage flow back into Hub lineage and the P7 cost ledger.
5. **Keep local options** — Non-warehouse targets keep the existing local dbt-native execution path; the deprecated DuckDB/Polars engine remains under the legacy migration command.

## Success Criteria

- Prefect orchestration is unchanged — only the execution target switches.
- Warehouse-direct and job-based targets both complete an end-to-end dbt run.
- Lineage and DBU attribution land in the Hub subsystems.
- Local-executor regression tests stay green.

## Related

- Concepts: [Contracts](../concepts/contracts.md), [Lineage](../concepts/lineage.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-013](JOURNEY-DB-013.md) (Export a Dataset to Databricks)
