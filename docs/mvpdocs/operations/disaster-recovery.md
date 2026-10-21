# Disaster Recovery

This page documents disaster recovery procedures for the Meshant platform.

## RTO / RPO Targets

| Component   | RTO (Recovery Time) | RPO (Recovery Point) |
|-------------|---------------------|----------------------|
| API Backend | 15 minutes          | 0 (stateless)       |
| PostgreSQL  | 1 hour              | 5 minutes (WAL)     |
| Redis Cache | 5 minutes           | N/A (rebuilt)        |
| S3 Storage  | 30 minutes          | 0 (cross-region)    |

## Failover Procedures

### Application Layer

The EKS cluster runs across multiple availability zones. If a node
fails, Kubernetes reschedules pods automatically. For a full AZ
outage:

1. Verify pod redistribution via `kubectl get pods -o wide`.
2. Confirm health endpoints respond: `/health/ready/`.
3. If pods are not rescheduling, manually cordon the failed nodes
   and trigger a rollout: `kubectl rollout restart deployment/meshant`.

### Database (RDS PostgreSQL)

RDS Multi-AZ provides automatic failover. If manual intervention is
needed:

1. Check RDS events in the AWS Console.
2. Initiate failover: `aws rds failover-db-cluster --db-cluster-identifier meshant-<env>`.
3. Verify application reconnects (connection pool refreshes within 30s).

### Cache (ElastiCache Redis)

Redis is used as a cache only -- data loss is acceptable. If the
Redis node fails:

1. ElastiCache automatic failover promotes a replica (if Multi-AZ).
2. Otherwise, the application falls back to database queries.
3. Cache warms up organically through normal traffic.

### Object Storage (S3)

S3 provides 99.999999999% durability. Cross-region replication is
enabled for critical buckets. In case of regional outage:

1. Update the S3 endpoint environment variable to the replica region.
2. Redeploy via Helm.

## Related

- [Backup & Restore](backup-restore.md) -- scheduled backups and restore drills
- [Incident Response](incident-response.md) -- incident handling process
