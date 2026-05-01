# Lineage storage capacity plan

**Phase:** 228 Foundations (228.0.4)
**Owner:** Data Platform Eng
**Last reviewed:** 2026-04-30

## Purpose

Project the 3-year `LineageEdge` row count and total storage footprint, and compare against the staging + production RDS instance class headroom. Output: a sized provisioning recommendation that ops can act on before Phase 228 ships.

## Inputs

- **Today's contract corpus** (production, 2026-04-30 snapshot): **~5,000** Contract rows across **~120** active tenants.
- **Average upstream-edges per contract** (sampled from `hub_contract_json.lineage`): **2.4 edges/contract** (median 1, p95 8, max 47).
- **Contract growth rate**: 2025 average **+200 contracts/quarter** (linear growth assumption — most tenants are stable, growth comes from new-tenant onboarding).
- **Edge-update frequency** (sampled from audit-event log): **1.1 edge mutations / contract / quarter** (most contracts are stable; iteration happens in concentrated bursts during onboarding).
- **SCD Type 2 retention**: closed edges are retained indefinitely (ADR-LIN-002) for the time-travel window.

## Row-count projection

Year-by-year, assuming linear contract growth:

| Year end | Total contracts | Open edges (live) | Closed edges (cumulative) | Total `LineageEdge` rows |
|---|---|---|---|---|
| 2026 (start, t0) | 5,000 | 12,000 | 0 | 12,000 |
| 2026 (end, t+1y) | 5,800 | 13,920 | 6,400 | 20,320 |
| 2027 (end, t+2y) | 6,600 | 15,840 | 14,000 | 29,840 |
| 2028 (end, t+3y) | 7,400 | 17,760 | 22,800 | 40,560 |

**3-year total: ~40,000 `LineageEdge` rows.**

## Storage footprint

Per-row size estimate (post-TOAST):

| Column group | Bytes |
|---|---|
| `id` (UUID, 16 B) + `created_at` + `valid_from` + `valid_to` (3 × 8 B) | 40 |
| `source_contract_id` + `target_contract_id` (2 × 16 B UUID FK) + indexes | 80 |
| `source_model` + `source_field` + `target_model` + `target_field` (4 × CharField, avg 24 chars) | 96 |
| `edge_type` (CharField, max 16 B) | 16 |
| `transformation_ref` + `job_ref` (2 × CharField, avg 32 chars) | 64 |
| `tenant_id` (UUID FK) | 16 |
| `created_by_run` (CharField, avg 24 chars) | 24 |
| Postgres heap overhead per row | 24 |
| Per-row total (estimated) | **~360 bytes** |

3-year storage: **40,560 × 360 ≈ 14.6 MB** (data) + **3 composite indexes × ~8 MB ≈ 24 MB** (indexes) → **~40 MB total**.

## RDS instance class assessment

Production: `db.r6g.large` (16 GiB RAM, 100 GiB gp3 storage). Staging: `db.t4g.medium` (4 GiB RAM, 40 GiB gp3 storage).

The 3-year `LineageEdge` footprint is **~0.04% of the production RDS allocation** and **~0.1% of staging**. **No instance-class change required** for Phase 228.

## Triggers for re-projection

This estimate **must be re-run** if any of the following hold:

- Contract count exceeds **15,000** (3× current — would push the linear assumption out of band).
- Edge-update frequency exceeds **5 mutations / contract / quarter** (would 5× the closed-edge accumulation rate).
- A new edge type is added that produces multiple-edges-per-field (e.g., field-level mapping in Phase 228 F2 ships, may amplify by 10×).

The re-projection trigger is implemented as a daily Prometheus query:

```promql
# Alert when row count crosses the 3-year projection's halfway point in year 1.
sum(pg_table_row_count{table="contracts_lineage_edge"}) > 25000
```

Alert routes to `#data-platform-oncall` with this doc as the runbook link.

## Long-term archival (out of scope for Phase 228)

If row count ever crosses **1,000,000** (a 25× over-shoot from current projection), the operational plan is:

1. Add a `archived_at: DateTimeField(null=True, db_index=True)` column to `LineageEdge`.
2. Move closed edges older than 2 years to S3 cold-storage (`s3://meshant-lineage-archive/<tenant>/<year>/`) via a nightly batch job.
3. Set `archived_at` and remove the row from the hot table.
4. Time-travel queries with `as_of < 2-years-ago` route through a separate read path that pulls from S3.

The above is a follow-up phase; the projected footprint does not require it.
