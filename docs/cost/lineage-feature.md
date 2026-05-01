# Lineage feature — Cost forecast (Phase 228)

**Phase:** 228 (overall — 228.0/F1/F2/F3/F4/F5)
**Owner:** FinOps + Data Platform Eng
**Last reviewed:** 2026-05-01
**AWS resource tag (mandatory on new resources):** `cost-center=lineage-feature`

This doc is the canonical cost view for the Phase 228 lineage
feature surface. It complements [docs/capacity/lineage-storage.md](../capacity/lineage-storage.md)
(storage projection) and [docs/capacity/lineage-cost-12mo.md](../capacity/lineage-cost-12mo.md)
(per-phase 12-month forecast). Where this doc differs:

* The capacity docs are eng-driven and project hot-tier growth.
* This doc is FinOps-driven and aggregates the **total billable AWS
  spend across ALL phases** with a budget envelope FinOps signs off
  on.

## Total budget envelope (year 1)

| Phase | Resources introduced | Year-1 envelope (USD) |
|---|---|---|
| 228.0 Foundations | RDS storage delta + IOPS + RQ workers | **$24** |
| 228.F1 Cross-tenant marketplace | None new (re-uses 228.0 surface) | **$0** |
| 228.F2 Field-level mapping | RDS storage delta (field-level rows) | **$12** |
| 228.F3 Lineage notifications | Worker pods + SES (email dispatcher) | **$60** |
| 228.F4 OpenLineage integration | Marquez (EKS Helm chart + RDS Multi-AZ) | **$1,800** |
| 228.F5 Time-travel + archive | S3 archive bucket + Glacier transitions | **$240** |
| 228.X Cross-cutting | Prometheus alert evaluation overhead | **$0** |
| **Total Year-1 envelope** | | **~$2,136** |

The **$1,800** Marquez line is the dominant lever; everything else
is amortized into the existing platform spend. The capacity-review
cadence ([docs/capacity/lineage-capacity-review-cadence.md](../capacity/lineage-capacity-review-cadence.md))
includes a quarterly check against this envelope.

## Tagging policy

Every new AWS resource introduced by Phase 228 carries
`cost-center=lineage-feature`. Enforced at the Terraform level:

* [infrastructure/terraform/lineage_archive/main.tf](../../infrastructure/terraform/lineage_archive/main.tf)
  — `cost-center = "lineage-feature"` on the bucket.
* Marquez RDS in [docs/integrations/openlineage-infra.md](../integrations/openlineage-infra.md)
  — same tag.
* The S3 bucket lifecycle transitions (Standard → Glacier @ 36mo →
  Deep Archive @ 84mo) carry the parent bucket's tags by default.

The FinOps query
`aws ce get-cost-and-usage --filter '{"Tags":{"Key":"cost-center","Values":["lineage-feature"]}}'`
returns the actual spend for any window — used at every quarterly
review.

## Variance triggers

These trip an out-of-cycle FinOps review:

| Signal | Threshold | Likely cause |
|---|---|---|
| Marquez RDS storage growth | > 5 GB / month | Outbound emission volume spike. Investigate via `openlineage_outbound_total{result}`. |
| S3 archive bucket size | > forecast | Hot tier under-archived OR archival cron skipped runs. Check `archive_lineage_edges` cron history. |
| OpenLineage DLQ depth | > 100 sustained 24h | Marquez outage; re-deliveries not running. Runbook: [openlineage-dlq-replay.md](../runbooks/openlineage-dlq-replay.md). |
| Worker pod CPU (notifications) | > 50% sustained 1h | Notification storm. Runbook: [lineage-notification-storm.md](../runbooks/lineage-notification-storm.md). |

## Per-phase deep links

- [228.0 + per-phase 12-month forecast](../capacity/lineage-cost-12mo.md)
- [228.0 storage projection](../capacity/lineage-storage.md)
- [Quarterly capacity-review cadence](../capacity/lineage-capacity-review-cadence.md)
- [F4 Marquez infra cost shape](../integrations/openlineage-infra.md)
- [F5 archive lifecycle](../architecture/lineage-archive-op3.md)

## Sign-off

| Role | Name | Date |
|---|---|---|
| FinOps | _to be filled_ | _YYYY-MM-DD_ |
| Data Platform Eng | _to be filled_ | _YYYY-MM-DD_ |
| Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |

Sign-off is required before Phase 228 is marked GA in production
(228.DoD.6 + 228.DoD.4).
