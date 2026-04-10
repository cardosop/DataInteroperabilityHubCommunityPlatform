# Capacity Planning

Scaling guidelines for the Meshant platform. These targets apply to
the production environment; staging runs smaller instances.

## Horizontal Pod Autoscaling

All backend services use Kubernetes HPA. Default thresholds:

| Service           | Min Replicas | Max Replicas | CPU Target | Memory Target |
|-------------------|-------------|-------------|------------|---------------|
| API Backend       | 3           | 12          | 70%        | 80%           |
| Celery Workers    | 2           | 8           | 75%        | 80%           |
| Search Service    | 2           | 6           | 70%        | 75%           |
| Webhook Service   | 2           | 4           | 70%        | 80%           |

Review HPA metrics monthly and adjust limits based on observed
traffic patterns.

## Database Connections

PostgreSQL connection pooling is managed via PgBouncer:

- **Max connections (RDS)**: 500 (db.r6g.xlarge default)
- **PgBouncer pool size**: 20 per backend pod
- **Rule of thumb**: max pods x pool size must stay below RDS max
  connections, with 20% headroom for admin and migration connections.

Scale RDS vertically (instance size) or horizontally (read replicas)
when connection utilization consistently exceeds 70%.

## S3 Storage Growth

Estimated growth rates for key buckets:

| Bucket            | Growth Rate      | Retention     |
|-------------------|-----------------|---------------|
| Asset uploads     | ~50 GB/month    | Indefinite    |
| Backup snapshots  | ~10 GB/month    | 30 days       |
| Logs archive      | ~20 GB/month    | 90 days       |

Set up S3 lifecycle rules to transition older objects to Glacier or
expire them per retention policy.

## Redis Memory

ElastiCache Redis is used for caching and Celery broker:

- **Baseline memory**: ~500 MB
- **Growth**: scales with active tenant count and cache cardinality
- **Alert threshold**: 80% of `maxmemory`
- **Eviction policy**: `allkeys-lru`

If memory pressure is sustained, consider increasing node size or
adding a dedicated Redis instance for the Celery broker.

## Review Cadence

Review capacity metrics quarterly. Key signals:

- HPA frequently at max replicas
- Database connection pool above 70%
- Redis memory above 75%
- S3 lifecycle rules not expiring as expected

## Related

- [Monitoring](monitoring.md) -- dashboards for capacity metrics
- [Configuration Reference](configuration-reference.md) -- HPA and pool settings
