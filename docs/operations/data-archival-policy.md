# Data Archival Policy

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## Storage Tiers

| Tier | Age | Storage | Cost | Access Latency |
|------|-----|---------|------|----------------|
| **Hot** | < 30 days | RDS (PostgreSQL) + S3 Standard | $$$ | < 10ms |
| **Warm** | 30–90 days | S3 Standard | $$ | < 100ms |
| **Cold** | 90–365 days | S3 Intelligent-Tiering / S3-IA | $ | < 1s |
| **Archive** | > 365 days | S3 Glacier Deep Archive | ¢ | < 12h |

## Participating Models

| Model | Table | Hot (days) | Archive Strategy |
|-------|-------|-----------|-----------------|
| `AuditEvent` | `audit_events` | 30 | Purge after retention policy expiry |
| `ComplianceRun` | `compliance_runs` | 90 | Archive to S3-IA, keep metadata in DB |
| `DQRun` | `dq_runs` | 90 | Archive to S3-IA, keep metadata in DB |
| `Job` | `jobs` | 30 | Purge completed jobs after 30d |
| `WebhookDelivery` | `webhook_deliveries` | 30 | Purge after 90d |
| `APIUsage` (BaaS) | `api_usage` | 30 | Aggregate to daily summaries after 30d |
| `Invoice` | `invoices` | 365 | Archive PDFs to S3 Glacier, keep metadata |
| `PaymentTransaction` | `payment_transactions` | 365 | Archive to S3 Glacier after 365d |
| `File` (soft-deleted) | `files` | 30 | S3 Glacier after `deleted_at + 90d` |
| `Dataset` (retired) | `datasets` | 30 | Keep metadata, archive file to Glacier |
| `TenantUsageSummary` | `tenant_usage_summaries` | 90 | Aggregate to monthly summaries, purge daily |

## Automation Schedule

| Job | Cadence | Script |
|-----|---------|--------|
| Hot → Warm (30d cutoff) | Daily | `scripts/archive_hot_to_warm.py` |
| Warm → Cold (90d cutoff) | Weekly | `scripts/archive_warm_to_cold.py` |
| Cold → Archive (365d cutoff) | Monthly | `scripts/archive_cold_to_glacier.py` |
| GDPR erasure sweep | Daily | `hub/manage.py tenant_hard_delete_sweep` |
| PII data map audit | Monthly | `scripts/audit_pii_fields.py` |
| Deletion coverage audit | Monthly | `scripts/audit_tenant_deletion_coverage.py` |

## Retention by Compliance Regime

| Regulation | Minimum Retention | Maximum Retention | Notes |
|------------|------------------|------------------|-------|
| GDPR | 30 days (after purpose fulfilled) | 10 years (financial records) | Right to erasure applies to non-financial data |
| CCPA | 30 days | 10 years | Opt-out of sale does not require deletion |
| SOC 2 | 90 days (audit logs) | 7 years | Audit trail retention for compliance evidence |

## GDPR Right to Erasure

The `tenant_hard_delete_sweep` management command handles per-tenant cascading deletes. The `scripts/audit_tenant_deletion_coverage.py` script audits that every tenant-scoped model has a deletion path. See `docs/operations/tenant-deletion-coverage.md` for current coverage.
