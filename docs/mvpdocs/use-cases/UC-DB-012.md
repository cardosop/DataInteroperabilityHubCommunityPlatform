# UC-DB-012: Consume Delta Share

**Persona:** [Data Consumer](../personas/data-consumer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P5 Test:** `hub/apps/databricks_admin/tests/test_delta_sharing_journeys.py::TestJOURNEYDB012ConsumeDeltaShare::test_protocol_shapes`

## Description

Consume Hub datasets through the native Delta Sharing 1.0 server: list shares/schemas/tables and fetch data as JSON query results or Parquet snapshots with presigned URLs, under a per-recipient bearer token with per-token throttling.

## Preconditions

- A `DeltaShareRecipient` with a valid `DeltaShareToken` scoped to share/schema/table triples.
- The shared asset has `semantic_federate_optout=False`.

## Steps

1. Consumer loads the share profile and lists shares, schemas, and tables.
2. Consumer queries a table (JSON mode proxies SELECT through the warehouse connector).
3. Consumer downloads Parquet data via presigned URLs to the Hub S3 snapshot.
4. Every access emits `WAREHOUSE_SHARE_ACCESSED`; the snapshot job refreshes materialized data on TTL.

## Expected Outcome

- Opted-out assets are invisible and return 404 on direct fetch.
- Presigned URLs expire and cannot be replayed.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Invalid/absent token | `401` with `WAREHOUSE_SHARE_AUTH_FAILED` |
| Opted-out asset | `404` |
| Per-token throttle exhausted | `429` with rate-limit audit event |

## Related

- Concepts: [Datasets](../concepts/datasets.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-012 -- Consume a Delta Share](../journeys/JOURNEY-DB-012.md)
- Personas: [Data Consumer](../personas/data-consumer/index.md)
