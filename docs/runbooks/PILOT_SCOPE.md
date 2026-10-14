# Pilot Scope — Week 3 Workshop Record

- **Date:** 2026-10-05
- **Change:** `openspec/changes/pilot-readiness` task 3.2
- **Method:** journey selection anchored to
  `docs/CRITICAL_UC_JOURNEY_IDS.yaml` FIRST, then supplemented — per the
  readiness plan. This record is contract-checked by
  `scripts/check_pilot_scope.py` (GATE-45).

## Journey selection

**20 IDs — 10 journeys + 10 use cases — all from the critical
registry.** The selection is the pilot's end-to-end story:
login (SSO) → connect Databricks → ingest → contract → publish →
consume, plus the governance/DQ edges the platform must demonstrate.

| # | ID | Role in the pilot story |
|---|---|---|
| 1 | JOURNEY-AUTH-001 | Login (SSO entry — the 3.1-verified surface) |
| 2 | JOURNEY-DE-001 | Data engineer connects the Databricks workspace |
| 3 | JOURNEY-DE-003 | Dataset creation from the ingested data |
| 4 | JOURNEY-DE-004 | Asset + contract registration |
| 5 | JOURNEY-INGESTION-001 | Scheduled ingestion of a source dataset |
| 6 | JOURNEY-INGESTION-003 | Incremental ingestion (the dlt cursor spine) |
| 7 | JOURNEY-EXPORT-001 | Export a dataset to a destination |
| 8 | JOURNEY-EXPORT-002 | Export with the dlt destination binding |
| 9 | JOURNEY-DB-013 | Export a dataset to Databricks (live-verified 2.3) |
| 10 | JOURNEY-DC-001 | Data consumer discovers + consumes a published asset |
| 11 | UC-AUTH-001 | User authentication |
| 12 | UC-AUTH-006 | SSO login (the shipped Databricks-as-IdP surface) |
| 13 | UC-INGEST-001 | Create an ingestion from a source |
| 14 | UC-INGEST-002 | Run the ingestion (execute_dlt_ingestion spine) |
| 15 | UC-INGEST-003 | Verify ingested data landed (destination roundtrip) |
| 16 | UC-EXPORT-001 | Create an export |
| 17 | UC-EXPORT-002 | Run the export end-to-end |
| 18 | UC-DB-001 | Connect the Databricks warehouse |
| 19 | UC-DB-003 | Query the warehouse (WarehouseQueryRunner) |
| 20 | UC-DB-013 | Export a dataset to Databricks |

Selection policy: critical-first (20/20 are critical-registry IDs —
the registry has 29 critical journeys + 35 critical UCs); the
non-critical supplements (billing upgrade, marketplace browsing,
advanced governance) stay out of P1 scope and are recorded as
deferred, not dropped.

## Capability manifest

**Surfaces ON for the pilot company** (the runtime mechanism:
`CAPABILITY_FLAGS` overrides in `hub/apps/api/capabilities.py`; each
flag defaults OFF in staging, the escape hatch flips a flag for a
single customer or a gradual rollout via
`CAPABILITY_FLAGS_ROLLOUT_TENANTS`):

| Runtime key | Pilot state | Rationale |
|---|---|---|
| `lineage.snapshots` | ON | the pilot's ingest→publish story must show lineage snapshots |
| `lineage.change_notifications` | ON | change notifications support the consume story |
| `lineage.cross_tenant_marketplace` | OFF | single-company pilot — cross-tenant marketplace is not needed |
| `lineage.field_level_mapping` | OFF | P1 demo scope — field-level lineage deferred |
| `lineage.openlineage_export` | OFF | OpenLineage export deferred |

Ops wiring: set `CAPABILITY_FLAGS` (the two ON keys) for the pilot
tenant via the rollout allow-list; the rest of the platform surface
(warehouses, dlt movement, contracts, marketplace, billing) is the
non-flagged MVP surface and stays ON as-is.

## Unity Catalog / Delta Sharing decision

**Unity Catalog: USED, not built.** The pilot account has Unity
Catalog enabled — proven live in 2.3 (three-part qualified reads
`samples.nyctaxi.trips`, the live catalog listing `workspace`,
`samples`, `system`, and the dbt view materialized into
`workspace.pilot_dbt_23`). No build work: the platform consumes the
account's native catalog.

**Delta Sharing: NOT built — not required for P1.** Consumers reach
pilot data through the platform's export/contract surfaces (dlt
exports, marketplace listings) rather than Delta Sharing. If the
company later requires Delta Sharing, the existing
`add-delta-sharing-server` change is the starting point and it ships
as its own change (proposal scope decision, confirmed here).

## Data-migration approach

The pilot migrates the company's existing datasets through the
**dlt spine proven end-to-end in 2.3** — no one-off scripts:

1. **Sources:** the shipped connectors (filesystem, HTTP, S3, CKAN)
   for the company's existing stores, plus the DATABRICKS_SOURCE
   branch for warehouse-resident data (live SELECT → dlt → destination,
   verified 2.3).
2. **Spine:** `execute_dlt_ingestion` per `ScheduledIngestion` — the
   incremental cursor lives in the dlt pipeline state and advances
   ONLY after a successful load (a failed run leaves it exactly where
   the last success put it — proven contract).
3. **Destinations:** dev MinIO `s3://hub-files` today; the customer
   AWS bucket via the 2.2 documented upgrade path when the pilot
   leaves the dev estate.
4. **Order per dataset:** register asset + contract → schedule the
   ingestion → verify with DQ checks → publish to the marketplace.
5. **Backfill strategy:** filesystem/S3 bulk loads first, incremental
   thereafter on each source's cursor field; warehouse sources use the
   bounded cursor read with the per-connection tag opt-out
   (`session_tags_enabled: false`) where the account rejects query
   tags (free-edition finding, 2.3).
