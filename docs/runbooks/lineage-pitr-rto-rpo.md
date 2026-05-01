# Lineage archive — PITR, RTO, RPO

**Phase:** 228 F5 (228.F5.20)
**Owner:** Data Platform Eng + SRE
**Last reviewed:** 2026-05-01

This document captures the recovery objectives + the recovery
procedure for the three storage tiers under the lineage archival
pipeline. The objectives align with the platform DR baseline.

## Objectives

| Tier | RTO | RPO | Backup mechanism |
|------|-----|-----|------------------|
| `LineageEdge` (hot, RDS) | **≤ 4 h** | **≤ 15 min** | RDS PITR (5-min increments) |
| `LineageEdgeArchive` (warm, RDS) | **≤ 4 h** | **≤ 15 min** | RDS PITR + daily logical snapshot |
| S3 archive bucket | **≤ 24 h** | **≤ 24 h** | S3 versioning + cross-region replication (CRR) |

The 4 h / 15 min objective on the hot + warm tiers matches the
platform's existing customer-facing SLA (the lineage data is on
the read path of the product UI). The S3 tier is the cold fallback
— RTO loosens because Glacier restore latency dominates.

## RDS PITR coverage

The Hub RDS instance carries:

- `backup_retention_period = 35` (days)
- `backup_window = "03:00-04:00"` (UTC)
- Automated backups enabled
- Point-in-time recovery (PITR) enabled — Postgres WAL is shipped
  every 5 min, so the smallest recovery resolution is 5 min,
  matching the **15 min RPO** with comfortable margin.

`LineageEdgeArchive` lives in the same RDS so PITR covers it
automatically. Additionally, a **daily logical snapshot** of the
archive table is exported via `pg_dump --table=contracts_lineage_edge_archive`
to the same S3 bucket as the bundles (path prefix `dumps/`). The
dump is retained for 90 days. Procedure documented inline in
[infrastructure/terraform/lineage_archive/main.tf](../../infrastructure/terraform/lineage_archive/main.tf)
(future enhancement; the daily-dump cron is a separate Argo
workflow that mounts the same IAM role).

## S3 archive durability

- Versioning: **Enabled** (Terraform module).
- Cross-region replication: **Enabled** to `<region>-replica`
  (configured in the parent VPC module; the lineage_archive bucket
  is auto-included via tag-match).
- Glacier transition: **36 months**; Deep Archive: **84 months**;
  hard expiry: **25 years** (configurable via
  `var.expiration_days`).

## Recovery procedures

### Hot tier — restore via PITR

1. Open the RDS console + locate the `meshant-<env>` instance.
2. Choose "Restore to point in time" → pick the timestamp.
3. The restore creates a NEW instance (`meshant-<env>-restore-<ts>`).
4. Validate the data:
   ```bash
   psql -h meshant-<env>-restore-<ts>.rds.amazonaws.com -U readonly -d meshant -c \
       "SELECT count(*), max(valid_from), max(valid_to) FROM contracts_lineage_edge"
   ```
5. Cut over via the existing DR-runbook procedure (Helm value
   `database.host: meshant-<env>-restore-<ts>.rds...` + Argo sync).

### Warm tier — restore via daily snapshot

If the archive table is unrecoverable from PITR (rare), restore
from the daily `pg_dump`:

```bash
aws s3 cp s3://meshant-<env>-lineage-archive/dumps/$(date -I -d 'yesterday')/archive.sql.gz .
gunzip -c archive.sql.gz | psql -h meshant-<env>.rds.amazonaws.com -U app -d meshant
```

### S3 tier — restore object versions

```bash
# List versions of an object.
aws s3api list-object-versions --bucket meshant-<env>-lineage-archive \
    --prefix 2025/01/lineage-archive-abc123.jsonl.gz

# Restore the previous version (if the latest was corrupted).
aws s3api copy-object \
    --bucket meshant-<env>-lineage-archive \
    --key 2025/01/lineage-archive-abc123.jsonl.gz \
    --copy-source 'meshant-<env>-lineage-archive/2025/01/lineage-archive-abc123.jsonl.gz?versionId=<old-version-id>'
```

### Glacier / Deep Archive restore

```bash
aws s3 restore-object \
    --bucket meshant-<env>-lineage-archive \
    --key 2022/01/lineage-archive-old.jsonl.gz \
    --restore-request '{"Days":7,"GlacierJobParameters":{"Tier":"Standard"}}'
# Wait 5 min - 12 h for Flexible Retrieval (Glacier),
# or 12 - 48 h for Deep Archive.
```

## Drill cadence

Quarterly DR drill — the team picks one of the three tiers at
random and runs the restore procedure end-to-end against staging
(NEVER prod). The drill captures the actual RTO + RPO observed and
opens an issue if either exceeds the target above. Procedure
template at [destroy-staging.md](./destroy-staging.md).

## Related

- [Archive job failure runbook](./lineage-archive-job-failure.md)
- [Cost forecast](../capacity/lineage-cost-12mo.md)
- [Terraform module](../../infrastructure/terraform/lineage_archive/main.tf)
- [OP-3 sign-off doc](../architecture/lineage-archive-op3.md)
