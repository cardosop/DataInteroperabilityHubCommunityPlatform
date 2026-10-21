# Disaster Recovery Policy

**Version**: 1.0 | **Last Updated**: 2026-05-20 | **Owner**: Infrastructure Engineering

## Platform-Wide Objectives

| Metric | Target | Measurement |
|--------|--------|-------------|
| **RTO (Recovery Time Objective)** | 4 hours | Time from incident declaration to full service restoration |
| **RPO (Recovery Point Objective) — RDS** | 1 hour | Automated snapshots every hour; point-in-time recovery via WAL |
| **RPO (Recovery Point Objective) — S3** | 24 hours | Cross-region replication with versioning; daily sync |
| **Fuseki (Triple Store)** | EBS snapshot policy: daily, retained 7 days | `scripts/backup-postgres.sh` covers Fuseki TDB2 volume |
| **Redis** | RDB snapshots every 15 min + AOF; S3 export daily | Automated by ElastiCache; config in `infrastructure/terraform/elasticache.tf` |

## Recovery Procedures

### RDS (Primary Database)

1. **Automated recovery**: `scripts/dr/restore_verify_rds.sh` restores latest snapshot → temp instance → migrate → health check
2. **Manual recovery**: AWS Console → RDS → Snapshots → select latest → Restore → update DATABASE_URL in EKS secrets
3. **Point-in-time recovery**: Use `restore_db_instance_to_point_in_time` for WAL-based PITR within 1-hour window

### S3 (Object Storage)

1. **Bucket recovery**: Cross-region replication bucket `hub-files-dr` in us-west-2
2. **Object recovery**: Enable versioning; deleted objects recoverable within retention window
3. **Corruption recovery**: Restore from replication bucket if primary bucket compromised

### Fuseki (Triple Store / Semantic Layer)

1. **EBS snapshot restore**: `aws ec2 create-volume --snapshot-id <latest>` → attach to Fuseki EC2 → restart
2. **Data rebuild**: Re-ingest from RDF sources if EBS snapshot unavailable

### Redis (Cache / Queue / Events)

1. **Cache**: Stateless — rebuild from DB on restart
2. **Queue (RQ)**: Jobs re-queued on worker restart; failed jobs in DLQ
3. **Events**: Replay from audit log if Redis events instance lost

## Infrastructure as Code Reference

All recovery infrastructure is defined in:

| Resource | IaC Location |
|----------|-------------|
| RDS instance + snapshots | `infrastructure/terraform/rds.tf` |
| RDS backup policy | `infrastructure/terraform/rds_backup.tf` |
| S3 buckets + replication | `infrastructure/terraform/s3.tf` |
| ElastiCache (Redis) | `infrastructure/terraform/elasticache.tf` |
| Fuseki EBS volumes | `infrastructure/terraform/fuseki.tf` |
| EKS cluster + node groups | `infrastructure/terraform/eks.tf` |
| VPC + networking | `infrastructure/terraform/vpc.tf` |

## Drill Schedule

| Drill | Cadence | Script |
|-------|---------|--------|
| RDS snapshot restore | Quarterly | `scripts/dr/restore_verify_rds.sh` |
| S3 cross-region failover | Biannual | Manual (AWS Console) |
| Fuseki EBS restore | Quarterly | Manual (AWS Console) |
| Full DR failover | Annual | Coordinated via incident response |

## Evidence Collection

All drill reports stored in `docs/operations/dr-drill-reports/YYYY-MM/`.
Each report includes:
- Drill date and operator
- RTO achieved vs. target
- Snapshot ID used
- Any failures or anomalies
- Corrective actions if RTO exceeded

## Compliance

This policy aligns with:
- SOC 2 — Business Continuity and Disaster Recovery criteria
- ISO 27001 — A.17.1 (Information security continuity)
- GDPR — Article 32 (Security of processing)
