# JOURNEY-DB-012: Consume a Delta Share

**Persona:** [Data Consumer](../personas/data-consumer/), [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-012

## Overview

A data consumer accesses Hub datasets shared through the native Delta Sharing 1.0 server: they obtain a profile and a scoped bearer token, list shares/schemas/tables, and fetch data either as JSON query results or as Parquet snapshots served from the Hub's object storage. Assets opted out via `semantic_federate_optout` never appear.

## Journey Steps

1. **Obtain a profile and token** — The consumer downloads the Delta Sharing profile and a per-recipient bearer token scoped to specific share/schema/table triples.
2. **List shares** — The consumer (Spark, pandas, or any Delta Sharing client) lists shares, schemas, and tables through the protocol endpoints.
3. **Query data** — JSON query mode proxies a `SELECT` through the warehouse connector; Parquet mode returns presigned URLs to snapshot files in the Hub S3 bucket.
4. **Hit limits safely** — Requests are throttled per recipient token; every access emits `WAREHOUSE_SHARE_ACCESSED`; invalid tokens return 401 with `WAREHOUSE_SHARE_AUTH_FAILED`.
5. **Refresh** — Snapshot jobs refresh materialized Parquet on a TTL; the consumer sees consistent data within the snapshot window.

## Success Criteria

- Opted-out assets are hidden from listings and return 404 on direct fetch.
- Every protocol request is audited with the consumer's IP + user-agent.
- Presigned URLs expire and cannot be replayed past expiry.
- Snapshot jobs are idempotent (`DATABRICKS_SHARE_SNAPSHOT_COMPLETED` / `..._FAILED`).

## Related

- Concepts: [Datasets](../concepts/datasets.md), [Audit Events](../concepts/audit-events.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- How-To: [Data Consumer How-To Guides](../personas/data-consumer/how-to/)
- Journeys: [JOURNEY-DB-013](JOURNEY-DB-013.md) (Export a Dataset to Databricks)
