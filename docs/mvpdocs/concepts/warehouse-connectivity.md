# Warehouse Connectivity (Phase 275)

## DQ + Compliance Live-Query Contract (275.A.13)

DQ and compliance services do NOT have direct warehouse access.
Instead, the Hub mediates:
1. Hub executes `LIMIT N` query against the warehouse
2. Hub materialises sample rows
3. Hub POSTs sample to dq-service `/run-dataframe`
4. Compliance scan runs on the materialised sample (not live warehouse)

Audit code: `WAREHOUSE_DQ_SAMPLE_MATERIALIZED`.

This closes the security-perimeter ambiguity: no new credential surface
in dq-service or compliance-service.
