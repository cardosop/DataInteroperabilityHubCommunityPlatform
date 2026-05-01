# Lineage feature — 12-month cost forecast

**Phase:** 228 Foundations (228.0.5)
**Owner:** Data Platform Eng + FinOps
**Last reviewed:** 2026-04-30
**AWS resource tag (mandatory on new resources):** `cost-center=lineage-feature`

## Purpose

12-month forecast of incremental AWS spend introduced by Phase 228 lineage features (Foundations + F1–F5), broken down by phase. Tagging policy ensures the spend is attributable.

## Forecast (12 months from Phase 228 launch)

### 228.0 Foundations

| Resource | Driver | Estimated incremental cost | Notes |
|---|---|---|---|
| RDS storage | `LineageEdge` table + indexes (~40 MB end of year 1, see `lineage-storage.md`) | **<$1/mo** | Negligible against existing RDS spend. |
| RDS IOPS | Signal-driven writes (~5,000 edges/yr) + SCD-Type-2 close-then-insert | **<$1/mo** | Within existing burst credit. |
| RQ worker pods (`backfill_lineage_edges` runs) | One-shot ops command, ~30 min/qtr per tenant | **<$1/mo** | Uses existing worker capacity. |
| Prometheus storage | New metrics (`lineage_query_*`, `lineage_edge_writes_*`) | **<$1/mo** | Small label cardinality. |
| **228.0 sub-total** | | **<$5/mo** | |

### 228.F1 Cross-tenant marketplace lineage

| Resource | Driver | Estimated incremental cost | Notes |
|---|---|---|---|
| API egress (cross-tenant lineage browse) | Marketplace consumer pre-purchase reads | **~$5/mo** | Capped by rate limit. |
| Audit log retention (`LINEAGE_VIEWED_CROSS_TENANT`) | New audit rows on every cross-tenant read | **<$2/mo** | Existing audit-event retention policy. |
| **228.F1 sub-total** | | **~$7/mo** | |

### 228.F2 Field-level lineage mapping

| Resource | Driver | Estimated incremental cost | Notes |
|---|---|---|---|
| RDS storage (`LineageEdge` row count amplification by ~5×) | Field mappings produce one edge per field-pair | **~$1/mo** | Re-projected against 3-yr storage doc; still under instance class. |
| **228.F2 sub-total** | | **~$1/mo** | |

### 228.F3 Lineage change-notifications

| Resource | Driver | Estimated incremental cost | Notes |
|---|---|---|---|
| SES email volume (notification dispatcher) | Per-recipient summary emails (1/hr opt-in) | **~$3/mo** | Volume capped by debounce. |
| Redis (debounce buffer) | Sorted-set per recipient | **<$1/mo** | Eviction policy keeps hot set small. |
| RQ worker (dispatcher, runs every minute) | New `notifications` queue work | **~$5/mo** | Adds one minute-interval scheduled job. |
| **228.F3 sub-total** | | **~$9/mo** | |

### 228.F4 OpenLineage export

| Resource | Driver | Estimated incremental cost | Notes |
|---|---|---|---|
| RQ worker (new `openlineage` queue) | OpenLineage adapter dispatch | **~$3/mo** | Pod count scales with subscriber count. |
| Egress to OpenLineage receivers | HTTPS POST per `RunEvent` | **~$2/mo** | Capped by subscriber count. |
| **228.F4 sub-total** | | **~$5/mo** | |

### 228.F5 Lineage snapshots (already SCD-2; this is the user-facing snapshot UI)

| Resource | Driver | Estimated incremental cost | Notes |
|---|---|---|---|
| API egress (snapshot download) | User-initiated downloads | **~$2/mo** | Bounded by user count. |
| **228.F5 sub-total** | | **~$2/mo** | |

## 12-month total forecast

| Phase | Monthly | 12-month |
|---|---|---|
| 228.0 Foundations | <$5 | <$60 |
| 228.F1 Cross-tenant | ~$7 | ~$84 |
| 228.F2 Field-mapping | ~$1 | ~$12 |
| 228.F3 Notifications | ~$9 | ~$108 |
| 228.F4 OpenLineage | ~$5 | ~$60 |
| 228.F5 Snapshots | ~$2 | ~$24 |
| **Total** | **~$30/mo** | **~$348/yr** |

## Tagging policy

All new AWS resources created for Phase 228 lineage features SHALL carry the tag `cost-center=lineage-feature`. Specifically:

- New RDS table-level tagging is N/A (RDS tags are instance-level), but per-table cost is tracked via Performance Insights queries with the tag inherited at the instance level.
- New RQ worker deployment manifests in `helm/values-staging.yaml` and `helm/values-prod.yaml` carry `tags: [cost-center=lineage-feature]` in the deployment annotations.
- New CloudWatch log groups (`/meshant/lineage-sync`, `/meshant/openlineage-adapter`) are created via Terraform with the tag block.

A weekly Cost Explorer query grouped by tag `cost-center` is in the FinOps dashboard; an alert fires if the actual exceeds 150% of forecast for two consecutive weeks. Runbook link: TBD (FinOps team to populate).
