# Lineage capacity-review cadence

**Phase:** 228 X (228.X.11 / REQ-LIN-X-008)
**Owner:** SRE + Data Platform Eng
**Last reviewed:** 2026-05-01

Quarterly capacity review for the lineage feature surface. The
review opens an issue at the start of each quarter (auto-created
by the GitHub Actions cron in
[lineage-snapshots-f5-dod.yml](../../.github/workflows/lineage-snapshots-f5-dod.yml));
this doc is the standing template SRE fills.

## Cadence

- **Frequency:** quarterly (Q1 / Q2 / Q3 / Q4 — first Monday of
  each quarter).
- **Owner of the review meeting:** the on-call SRE for the
  quarter; rotates every 3 months.
- **Stakeholders:** Data Platform Eng (lead), SRE, Compliance
  liaison, FinOps liaison.
- **Output artifact:** updated [lineage-cost-12mo.md](./lineage-cost-12mo.md) +
  a closeout comment on the quarterly review issue.

## Targets to inspect

| Resource | Source of truth | Threshold | Action if breached |
|---|---|---|---|
| `LineageEdge` rows | [scripts/lineage_history_growth.py](../../scripts/lineage_history_growth.py) | growth_factor ≤ 1.5 (REQ-LIN-F5-005) | Run `archive_lineage_edges --before=<12mo-ago>`. |
| `LineageEdgeArchive` rows | same script `--mode=projection` | within 3y RDS budget | Adjust archival cron cadence + cohort size. |
| S3 archive bucket size | `aws s3 ls --recursive --summarize meshant-prod-lineage-archive` | within forecast (`lineage-cost-12mo.md`) | Review lifecycle policy hit-rate. |
| Marquez Postgres size | RDS console; `meshant-marquez-prod` | within `db.r6g.large` budget | Schedule Marquez DB upsize. |
| Redis (lineage hot keys) | Redis console; key prefix `lineage:*` | < 4 GB used | Tune cache TTLs. |

## Procedure

1. Open the quarterly issue (auto-created by the schedule).
2. For each row in the table above, paste the current value +
   the threshold + the disposition.
3. If any threshold is breached, file a P2 capacity ticket with
   a fix proposal + owner.
4. Update [lineage-cost-12mo.md](./lineage-cost-12mo.md) with the
   12-month forward forecast.
5. Close the quarterly issue with a comment summarizing the
   findings + linked tickets.

## Out-of-cycle review triggers

Any of these jumps the next review forward:

- The `LineageEdgeRowGrowthInvariantBreached` alert fires.
- A tenant's lineage row count exceeds 10× the median across all
  tenants (single-tenant dominance — investigate).
- Marquez Postgres free-disk drops below 20%.

## Related

- [Capacity script](../../scripts/lineage_history_growth.py)
- [12-month cost forecast](./lineage-cost-12mo.md)
- [Archive failure runbook](../runbooks/lineage-archive-job-failure.md)
- [PITR / RTO / RPO](../runbooks/lineage-pitr-rto-rpo.md)
