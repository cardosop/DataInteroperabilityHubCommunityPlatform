# Operator External Setup Checklist

**Document Version**: 1.0.0
**Last Updated**: 2026-03-26

---

## Overview

This checklist covers the external dependencies that must be provisioned before deploying Meshant to a new environment.

## PostgreSQL

### Setup
- Provision PostgreSQL 15+ instance with `pgbouncer` connection pooling
- Create database: `meshant` (or per-environment name)
- Create application user with appropriate grants
- Enable required extensions: `pg_trgm`, `uuid-ossp`

### Verification
```bash
pg_isready -h <host> -p 5432 -U meshant
kubectl exec -it <pod> -- python manage.py migrate --check
```

## Redis

Two separate Redis instances are required:

### redis-cache
- Used for: Django cache, session storage, search result caching
- Recommended: Redis 7+ with maxmemory-policy `allkeys-lru`

### redis-queue
- Used for: RQ job queue, Celery broker, webhook delivery queue
- Recommended: Redis 7+ with persistence enabled (AOF)

### Verification
```bash
redis-cli -h redis-cache -p 6379 ping
redis-cli -h redis-queue -p 6379 ping
kubectl exec -it <pod> -- python -c "from django.core.cache import cache; cache.set('test', 1); print(cache.get('test'))"
```

## AWS Secrets Manager

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->
AWS Secrets Manager is used for secrets management via ExternalSecret Operator.

### Setup
- Ensure AWS Secrets Manager is available in the target region
- Configure IRSA (IAM Roles for Service Accounts) for in-cluster access, or GitHub OIDC→AWS STS for CI/CD
- Store secrets at configured path (default: `hub/<env>/django`)
- Required secrets: `SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`

### Verification
```bash
aws secretsmanager get-secret-value --secret-id hub/staging/django --region <region>
kubectl get externalsecret -n meshant
```

## Prefect

Prefect is used for workflow orchestration (scheduled ingestion, data quality runs).

### Setup
- Deploy prefect-server or connect to Prefect Cloud
- Configure prefect-integration service with API URL
- Register work pools for scheduled tasks

### Verification
```bash
kubectl logs -l app=prefect-integration --tail=20
curl -s http://prefect-server:4200/api/health
```

## MinIO / S3

Object storage for file uploads and exports.

### Setup
- Provision S3-compatible storage (MinIO for self-hosted, AWS S3 for cloud)
- Create buckets: `meshant-uploads`, `meshant-exports`
- Configure CORS for frontend direct upload (if applicable)

### Verification
```bash
aws s3 ls s3://meshant-uploads/ --endpoint-url <minio-url>
kubectl exec -it <pod> -- python -c "from hub.apps.files.storage import get_storage; print(get_storage().exists('test'))"
```
