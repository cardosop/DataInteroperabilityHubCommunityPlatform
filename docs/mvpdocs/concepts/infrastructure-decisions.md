# Infrastructure Decisions

Key technology choices and the reasoning behind them.

## PostgreSQL

Primary database for all persistent data. Chosen for ACID compliance, complex
query support (JSONB, full-text search via tsvector, GIN indexes), and broad
enterprise adoption.

## Redis (4-Instance Strategy)

Redis is deployed as four separate instances to isolate failure domains:

| Instance | Port | Purpose | Eviction |
|----------|------|---------|----------|
| Cache | 6379 | HTTP response cache, contract cache, lineage cache | LRU/LFU |
| Queue | 6381 | RQ job queues (critical, default, low), job results | None (AOF persistence) |
| Events | 6382 | Pub/sub event delivery, deduplication | TTL-based |
| Channels | 6383 | WebSocket channel groups, real-time messaging | Ephemeral |

## S3 / MinIO

Object storage for file uploads, dataset payloads, contract exports. MinIO
provides S3-compatible API for local development and on-premises deployments.
AWS S3 is used in staging and production.

## RQ (not Celery)

Django RQ was chosen over Celery for background job processing:

- **Simpler architecture** -- no broker configuration beyond Redis
- **Native Django integration** -- management commands, admin UI
- **Priority queues** -- `job_critical`, `job_default`, `job_low` with configurable timeouts
- **Observability** -- job status, DLQ, retry are first-class concepts

## Kubernetes / Helm

Production orchestration via AWS EKS with Helm charts. Provides auto-scaling
(HPA), health-check-driven restarts, rolling updates with atomic rollback, and
PodDisruptionBudgets for zero-downtime deployments.

## Related

- [Architecture](architecture.md) -- service map and design principles
- [Configuration Reference](../operations/configuration-reference.md) -- environment variables
