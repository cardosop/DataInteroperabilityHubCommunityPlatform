# Deployment & Operations

> Kubernetes, Docker Compose, monitoring, troubleshooting, and release
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

# Kubernetes Deployment Documentation

Complete guide for deploying services to Kubernetes using the provided manifests.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Manifest Structure](#manifest-structure)
4. [Deployment Procedures](#deployment-procedures)
5. [Service-Specific Configuration](#service-specific-configuration)
6. [Testing Manifests](#testing-manifests)
7. [Troubleshooting](#troubleshooting)

---

## Overview

All Kubernetes manifests are organized using Kustomize for environment-specific configurations. The manifests follow Kubernetes best practices including:

- **Security**: Pod security standards, RBAC, network policies
- **High Availability**: Multiple replicas, pod anti-affinity, HPA
- **Observability**: Health checks, metrics endpoints
- **Resource Management**: Resource quotas, priority classes, limits

**Services Deployed:**
- Prefect Server (with PostgreSQL database)
- Prefect Workers
- Prefect Integration Service
- Search Service
- Observability Service
- Webhook Service

---

## Prerequisites

### Required Tools

- **kubectl** 1.24+ - Kubernetes CLI
- **kustomize** 4.0+ - Kustomize for manifest management
- **Kubernetes cluster** access (staging or production)

### Required Access

- Kubernetes cluster access with appropriate permissions
- Container registry access (for pulling images)
- Secrets manager access (for managing secrets)

### Required Knowledge

- Kubernetes basics (Deployments, Services, ConfigMaps, Secrets)
- Kustomize for environment-specific configurations
- RBAC and security policies

---

## Manifest Structure

### Directory Structure

```
k8s/
├── prefect-server/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secret.yaml
│   │   ├── service-account.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── hpa.yaml
│   │   ├── network-policy.yaml
│   │   ├── resource-quota.yaml
│   │   ├── priority-class.yaml
│   │   ├── pod-security-standards.yaml
│   │   ├── prefect-db-deployment.yaml
│   │   └── kustomization.yaml
│   └── overlays/
│       ├── staging/
│       │   └── kustomization.yaml
│       └── production/
│           └── kustomization.yaml
├── prefect-workers/
│   └── base/
├── prefect-integration/
│   └── base/
├── search-service/
│   └── base/
├── observability-service/
│   └── base/
└── webhook-service/
    └── base/
```

### Base Manifests

Each service has a `base/` directory containing:
- **namespace.yaml** - Namespace definition
- **configmap.yaml** - Configuration (non-secret)
- **secret.yaml** - Secrets template (replace with actual secrets)
- **service-account.yaml** - Service account and RBAC
- **deployment.yaml** - Deployment configuration
- **service.yaml** - Service definition
- **ingress.yaml** - Ingress configuration (if needed)
- **hpa.yaml** - Horizontal Pod Autoscaler (if applicable)
- **network-policy.yaml** - Network policies (if applicable)
- **kustomization.yaml** - Kustomize configuration

### Overlays

Environment-specific configurations in `overlays/`:
- **staging/** - Staging environment (reduced resources, single replica)
- **production/** - Production environment (HA, higher resources)

---

## Deployment Procedures

### 1. Validate Manifests

Before deploying, validate all manifests:

```bash
# Validate all manifests
./scripts/test_k8s_manifests.sh --dry-run

# Validate specific service
./scripts/test_k8s_manifests.sh --dry-run --service prefect-server
```

### 2. Configure Secrets

**IMPORTANT**: Update all secret files with actual values before deployment.

```bash
# Edit secrets (use external secrets manager in production)
kubectl create secret generic prefect-server-secrets \
  --from-literal=PREFECT_API_KEY='your-api-key' \
  --from-literal=PREFECT_DB_PASSWORD='your-password' \
  --namespace=prefect \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Production Recommendation**: Use External Secrets Operator with AWS Secrets Manager.

#### 2.1 Marketplace Connector Secrets

The API Service and Worker Service require marketplace connector secrets. Update the following Secret files:

**API Service Secrets** (`k8s/api-service/base/secret.yaml`):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-service-secrets
type: Opaque
stringData:
  # dados.gov.br Swagger API (NOT CKAN) - JWT Bearer token
  DADOS_GOV_BR_API_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  # CKAN instances (demo.ckan.org, data.gov) - Standard API key
  CKAN_TEST_API_KEY: "your-ckan-test-api-key-here"
  # Backward compatibility (deprecated)
  CKAN_DADOS_GOV_BR_API_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  # Snowflake Data Marketplace connector configuration
  SNOWFLAKE_ACCOUNT: "xy12345.us-east-1"
  SNOWFLAKE_USER: "MARKETPLACE_USER"
  SNOWFLAKE_TOKEN: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  SNOWFLAKE_WAREHOUSE: "MARKETPLACE_WAREHOUSE"
  SNOWFLAKE_ROLE: "MARKETPLACE_ROLE"
  SNOWFLAKE_DATABASE: "MARKETPLACE_DB"
```

**Worker Service Secrets** (`k8s/worker-service/base/secret.yaml`):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: worker-service-secrets
type: Opaque
stringData:
  # Same marketplace secrets as API Service
  DADOS_GOV_BR_API_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  CKAN_TEST_API_KEY: "your-ckan-test-api-key-here"
  CKAN_DADOS_GOV_BR_API_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  SNOWFLAKE_ACCOUNT: "xy12345.us-east-1"
  SNOWFLAKE_USER: "MARKETPLACE_USER"
  SNOWFLAKE_TOKEN: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  SNOWFLAKE_WAREHOUSE: "MARKETPLACE_WAREHOUSE"
  SNOWFLAKE_ROLE: "MARKETPLACE_ROLE"
  SNOWFLAKE_DATABASE: "MARKETPLACE_DB"
```

**Create Secrets from Command Line:**
```bash
# Create API Service secrets
kubectl create secret generic api-service-secrets \
  --from-literal=DADOS_GOV_BR_API_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  --from-literal=CKAN_TEST_API_KEY='your-ckan-test-api-key-here' \
  --from-literal=SNOWFLAKE_ACCOUNT='xy12345.us-east-1' \
  --from-literal=SNOWFLAKE_USER='MARKETPLACE_USER' \
  --from-literal=SNOWFLAKE_TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  --from-literal=SNOWFLAKE_WAREHOUSE='MARKETPLACE_WAREHOUSE' \
  --from-literal=SNOWFLAKE_ROLE='MARKETPLACE_ROLE' \
  --from-literal=SNOWFLAKE_DATABASE='MARKETPLACE_DB' \
  --namespace=default \
  --dry-run=client -o yaml | kubectl apply -f -

# Create Worker Service secrets
kubectl create secret generic worker-service-secrets \
  --from-literal=DADOS_GOV_BR_API_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  --from-literal=CKAN_TEST_API_KEY='your-ckan-test-api-key-here' \
  --from-literal=SNOWFLAKE_ACCOUNT='xy12345.us-east-1' \
  --from-literal=SNOWFLAKE_USER='MARKETPLACE_USER' \
  --from-literal=SNOWFLAKE_TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  --from-literal=SNOWFLAKE_WAREHOUSE='MARKETPLACE_WAREHOUSE' \
  --from-literal=SNOWFLAKE_ROLE='MARKETPLACE_ROLE' \
  --from-literal=SNOWFLAKE_DATABASE='MARKETPLACE_DB' \
  --namespace=default \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Production Recommendation**: Use External Secrets Operator with AWS Secrets Manager to manage secrets. See [Marketplace Secrets Documentation](../k8s/MARKETPLACE_SECRETS.md) for details.

### 3. Deploy to Staging

```bash
# Deploy all services to staging
./scripts/deploy_k8s_staging.sh

# Deploy specific service
./scripts/deploy_k8s_staging.sh --service prefect-server

# Dry run (validate without deploying)
./scripts/deploy_k8s_staging.sh --dry-run
```

### 4. Deploy to Production

```bash
# Deploy Prefect Server
kubectl apply -k k8s/prefect-server/overlays/production

# Deploy Prefect Workers
kubectl apply -k k8s/prefect-workers/base

# Deploy Prefect Integration Service
kubectl apply -k k8s/prefect-integration/base

# Deploy Search Service
kubectl apply -k k8s/search-service/base

# Deploy Observability Service
kubectl apply -k k8s/observability-service/base

# Deploy Webhook Service
kubectl apply -k k8s/webhook-service/base
```

### 5. Verify Deployment

```bash
# Check all deployments
kubectl get deployments --all-namespaces

# Check Prefect Server
kubectl get pods -n prefect -l app=prefect-server

# Check service health
kubectl get endpoints -n prefect prefect-server

# View logs
kubectl logs -n prefect -l app=prefect-server --tail=100
```

---

## Deployment Hardening (Phase 120D)

### Cosign Image Verification

All container images are signed with Cosign in CI. Before deploying, verify signatures:

```bash
cosign verify --key cosign.pub ghcr.io/datahub/api-service:latest
cosign verify --key cosign.pub ghcr.io/datahub/frontend:latest
cosign verify --key cosign.pub ghcr.io/datahub/worker:latest
```

A Kubernetes admission webhook (Kyverno or OPA Gatekeeper) rejects pods with unsigned images in production namespaces.

### PgBouncer Deployment

PgBouncer runs as a separate deployment with transaction-mode pooling:

- **Pool mode**: `transaction` (default 100 connections, configurable via `PGBOUNCER_MAX_CLIENT_CONN`)
- **Auth**: `scram-sha-256` via `userlist.txt` from ExternalSecrets-managed Secret
- **ConfigMap**: `pgbouncer-config` with `pgbouncer.ini` — checksum annotation triggers rolling restart on config change
- **Health check**: TCP probe on port 6432
- **Backend TLS**: SSL connection to PostgreSQL

### Database Backup CronJob

Automated backups run daily at 02:00 UTC:

```yaml
schedule: "0 2 * * *"
```

- **Script**: `scripts/backup-postgres.sh` — pg_dump via `POSTGRES_DIRECT_HOST` (bypasses PgBouncer)
- **Compression**: gzip -9
- **Integrity**: SHA-256 manifest (`sha256sum` with `openssl dgst` Alpine fallback)
- **Upload**: S3 with `--sse aws:kms --storage-class STANDARD_IA`
- **Retention**: Configurable via `BACKUP_RETENTION_DAYS` (default: 30)

### Worker Deployment Profiles

Two worker profiles for different workloads:

| Profile | Queues | Termination Grace | HPA Target | Use Case |
|---------|--------|-------------------|------------|----------|
| `worker-heavy` | `job_critical, job_default` | 1800s | CPU 70% + `queued_rq_jobs` | Long-running transformations, ML training |
| `worker-light` | `job_low` | 120s | CPU 70% | Notifications, cache warming, cleanup |

### Ingress Template

The Helm chart includes an Ingress template with:

- TLS termination via cert-manager annotations
- Rate limiting via Traefik middleware annotations
- Path-based routing: `/api/` → api-service, `/` → frontend
- Health check paths excluded from rate limiting

### PostgreSQL Exporter Metrics

`pg_exporter` sidecar collects PostgreSQL metrics for Prometheus:

- `pg_stat_activity` — active connections, wait events
- `pg_stat_user_tables` — table sizes, dead tuples, seq vs index scans
- `pg_replication_lag` — replication lag in bytes
- Custom query: `hub_tenant_count`, `hub_subscription_active_count`

---

## Service-Specific Configuration

### Prefect Server

**Namespace**: `prefect`

**Resources**:
- **Staging**: 1 replica, 256Mi-1Gi memory, 100m-500m CPU
- **Production**: 3 replicas (HA), 1Gi-4Gi memory, 500m-2000m CPU

**Endpoints**:
- API: Port 4200
- UI: Port 4201

**Dependencies**:
- PostgreSQL database (StatefulSet in same namespace)

**Configuration**:
- `PREFECT_API_URL` - API endpoint URL
- `PREFECT_API_DATABASE_CONNECTION_URL` - Database connection string
- `PREFECT_API_KEY` - API key (from secret)

### Prefect Workers

**Namespace**: `prefect`

**Resources**:
- **Staging**: 3 replicas, 256Mi-1Gi memory, 100m-500m CPU
- **Production**: 3-20 replicas (auto-scaling), 256Mi-1Gi memory, 100m-500m CPU

**Auto-scaling**:
- Min: 3 replicas
- Max: 20 replicas
- CPU threshold: 70%
- Memory threshold: 80%

**Configuration**:
- `PREFECT_API_URL` - Prefect Server URL
- `PREFECT_WORKER_POOL_NAME` - Worker pool name (default: "default")
- `PREFECT_WORKER_TYPE` - Worker type (default: "process")

### Prefect Integration Service

**Namespace**: `default`

**Port**: 8084

**Resources**: 256Mi-512Mi memory, 100m-500m CPU

**Configuration**:
- `PREFECT_API_URL` - Prefect Server URL
- `PREFECT_API_KEY` - API key (from secret)
- `DATABASE_URL` - Database connection string

### Search Service

**Namespace**: `default`

**Port**: 8085

**Resources**: 512Mi-2Gi memory, 250m-1000m CPU

**Configuration**:
- `DATABASE_URL` - Database connection string
- `SEARCH_INDEX_UPDATE_INTERVAL_SECONDS` - Index update interval (default: 60)
- `SEARCH_RESULT_LIMIT` - Max results per query (default: 100)

### Observability Service

**Namespace**: `default`

**Port**: 8086

**Resources**: 512Mi-2Gi memory, 250m-1000m CPU

**Configuration**:
- `DATABASE_URL` - Database connection string
- `PROMETHEUS_URL` - Prometheus endpoint
- `METRICS_UPDATE_INTERVAL_SECONDS` - Metrics update interval (default: 60)
- `FRESHNESS_CHECK_INTERVAL_SECONDS` - Freshness check interval (default: 300)

### Webhook Service

**Namespace**: `default`

**Port**: 8087

**Resources**: 256Mi-1Gi memory, 100m-500m CPU

**Configuration**:
- `DATABASE_URL` - Database connection string
- `WEBHOOK_RETRY_MAX_ATTEMPTS` - Max retry attempts (default: 5)
- `WEBHOOK_RETRY_BACKOFF_SECONDS` - Retry backoff (default: "1,5,30,300,1800")
- `WEBHOOK_TIMEOUT_SECONDS` - Request timeout (default: 30)

---

## Marketplace Environment Variables

The Data Interoperability Hub supports integration with multiple marketplace instances for harvesting data. This section documents all marketplace-related environment variables and configuration requirements.

### Marketplace Environment Variables Reference

| Variable | Description | Required | Default | Example | ConfigMap/Secret |
|----------|-------------|----------|---------|---------|------------------|
| `DADOS_GOV_BR_API_KEY` | JWT Bearer token for dados.gov.br Swagger API (NOT CKAN). Format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Yes* | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Secret |
| `CKAN_DADOS_GOV_BR_API_KEY` | **DEPRECATED** - Use `DADOS_GOV_BR_API_KEY` instead. Still supported for backward compatibility. | No | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Secret |
| `CKAN_TEST_URL` | Marketplace connector instance URL for testing (supports both CKAN and Swagger). Used for test instances like demo.ckan.org. | No | `https://demo.ckan.org` | `https://demo.ckan.org` or `https://dados.gov.br` | ConfigMap |
| `CKAN_TEST_API_KEY` | API key for CKAN test instances (demo.ckan.org, data.gov). Not required for dados.gov.br (uses JWT token). | No | None | `test-key-abc123...` | Secret |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g., `xy12345.us-east-1`). Required for Snowflake Data Marketplace connector. | No** | None | `xy12345.us-east-1` | Secret |
| `SNOWFLAKE_USER` | Snowflake user name for authentication. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_USER` | Secret |
| `SNOWFLAKE_TOKEN` | Snowflake authentication token (JWT or OAuth token). Required for Snowflake Data Marketplace connector. | No** | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Secret |
| `SNOWFLAKE_WAREHOUSE` | Snowflake warehouse name for executing queries. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_WAREHOUSE` | Secret |
| `SNOWFLAKE_ROLE` | Snowflake role for access control. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_ROLE` | Secret |
| `SNOWFLAKE_DATABASE` | Snowflake database name for marketplace data. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_DB` | Secret |
| `MOCK_SERVER_URL` | Mock server URL for testing marketplace connectors (internal service). Used for integration testing. | No | `http://mock-server.default.svc.cluster.local:8080` | `http://mock-server.default.svc.cluster.local:8080` | ConfigMap |

\* Required for dados.gov.br Swagger API connector. Other CKAN instances (demo.ckan.org, data.gov) use standard API keys and don't require JWT tokens.

\** Required if using Snowflake Data Marketplace connector. All Snowflake variables must be set together.

### Marketplace Configuration Requirements

#### 1. dados.gov.br (Brazilian Government Open Data Portal)

**Type**: Swagger API (NOT CKAN)
**Base URL**: `https://dados.gov.br`
**Authentication**: JWT Bearer token
**Connector**: `DadosGovBrConnector` (Swagger-based)

**Required Configuration:**
- **Secret**: `DADOS_GOV_BR_API_KEY` (JWT token format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)
- **ConfigMap**: Not required (uses default Swagger spec URL)

**Kubernetes Configuration:**
```yaml
# In Secret (api-service-secrets or worker-service-secrets)
stringData:
  DADOS_GOV_BR_API_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Notes:**
- Uses custom Swagger APIs (`/dados/api/publico/conjuntos-dados`), NOT standard CKAN APIs
- Swagger spec automatically loaded from `https://dados.gov.br/v3/api-docs`
- JWT token must be valid and not expired
- Backward compatibility: `CKAN_DADOS_GOV_BR_API_KEY` still works but is deprecated

#### 2. CKAN Instances (demo.ckan.org, data.gov)

**Type**: Standard CKAN API
**Base URLs**:
- `https://demo.ckan.org` (default test instance)
- `https://data.gov` (US Government Open Data Portal)
**Authentication**: Standard CKAN API key (not JWT token)
**Connector**: `CKANConnector` (standard CKAN API)

**Required Configuration:**
- **ConfigMap**: `CKAN_TEST_URL` (instance URL)
- **Secret**: `CKAN_TEST_API_KEY` (API key from CKAN instance)

**Kubernetes Configuration:**
```yaml
# In ConfigMap (api-service-config or worker-service-config)
data:
  CKAN_TEST_URL: "https://demo.ckan.org"

# In Secret (api-service-secrets or worker-service-secrets)
stringData:
  CKAN_TEST_API_KEY: "your-ckan-test-api-key-here"
```

**Notes:**
- API keys can be obtained from CKAN instance user profile
- Standard CKAN API key format (not JWT token)
- API keys should have read permissions for harvest operations

#### 3. Snowflake Data Marketplace

**Type**: Snowflake Data Marketplace
**Authentication**: Snowflake account, user, token, warehouse, role, database
**Connector**: Snowflake Data Marketplace connector

**Required Configuration** (all must be set together):
- **Secret**: `SNOWFLAKE_ACCOUNT` (account identifier)
- **Secret**: `SNOWFLAKE_USER` (user name)
- **Secret**: `SNOWFLAKE_TOKEN` (authentication token)
- **Secret**: `SNOWFLAKE_WAREHOUSE` (warehouse name)
- **Secret**: `SNOWFLAKE_ROLE` (role name)
- **Secret**: `SNOWFLAKE_DATABASE` (database name)

**Kubernetes Configuration:**
```yaml
# In Secret (api-service-secrets or worker-service-secrets)
stringData:
  SNOWFLAKE_ACCOUNT: "xy12345.us-east-1"
  SNOWFLAKE_USER: "MARKETPLACE_USER"
  SNOWFLAKE_TOKEN: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  SNOWFLAKE_WAREHOUSE: "MARKETPLACE_WAREHOUSE"
  SNOWFLAKE_ROLE: "MARKETPLACE_ROLE"
  SNOWFLAKE_DATABASE: "MARKETPLACE_DB"
```

**Notes:**
- All Snowflake variables must be set together
- Token can be JWT or OAuth token format
- Account identifier format: `xy12345.us-east-1` (account.region)
- See [Snowflake Data Marketplace Documentation](https://docs.snowflake.com/user-guide/gen-conn-config)

#### 4. Mock Server (Testing)

**Type**: Mock server for integration testing
**Base URL**: `http://mock-server.default.svc.cluster.local:8080` (internal Kubernetes service)
**Authentication**: None (testing only)
**Purpose**: Simulate marketplace APIs for testing

**Required Configuration:**
- **ConfigMap**: `MOCK_SERVER_URL` (default: `http://mock-server.default.svc.cluster.local:8080`)

**Kubernetes Configuration:**
```yaml
# In ConfigMap (api-service-config or worker-service-config)
data:
  MOCK_SERVER_URL: "http://mock-server.default.svc.cluster.local:8080"
```

**Notes:**
- Only used in development/testing environments
- Internal Kubernetes service (not exposed externally)
- Used for integration testing of marketplace connectors

### ConfigMap and Secret Management

**ConfigMaps** (Non-sensitive configuration):
- `api-service-config` / `worker-service-config`
- Contains: `CKAN_TEST_URL`, `MOCK_SERVER_URL`
- Can be version controlled (no secrets)

**Secrets** (Sensitive credentials):
- `api-service-secrets` / `worker-service-secrets`
- Contains: All API keys, tokens, and credentials
- **MUST NOT** be committed to Git
- Use External Secrets Operator with AWS Secrets Manager in production

**Production Best Practices:**
1. **Use External Secrets Manager**: AWS Secrets Manager (Phase 211: replaced HashiCorp Vault with AWS Secrets Manager)
2. **Enable Encryption at Rest**: Kubernetes Secrets are base64 encoded by default (not encrypted)
3. **Rotate Credentials Regularly**: Rotate API keys and tokens every 90 days
4. **Use Least Privilege**: API keys should have minimal required permissions
5. **Monitor Access**: Enable audit logging for secret access

For detailed marketplace connector deployment and troubleshooting, see [Marketplace Connector Deployment Runbook](./runbooks/marketplace-connector-deployment.md) and [Marketplace Secrets Documentation](../k8s/MARKETPLACE_SECRETS.md).

---

## Testing Manifests

### Validate Manifests

```bash
# Validate all manifests (dry-run)
./scripts/test_k8s_manifests.sh --dry-run

# Validate specific service
./scripts/test_k8s_manifests.sh --dry-run --service prefect-server

# Validate with kubectl
kubectl apply --dry-run=client -k k8s/prefect-server/base
```

### Test Deployment

```bash
# Deploy to staging (dry-run)
./scripts/deploy_k8s_staging.sh --dry-run

# Deploy to staging
./scripts/deploy_k8s_staging.sh

# Check deployment status
kubectl get pods --all-namespaces

# Check service health
kubectl get endpoints --all-namespaces
```

### Health Checks

```bash
# Check Prefect Server health
kubectl exec -n prefect deployment/prefect-server -- curl -f http://localhost:4200/api/health

# Check service endpoints
kubectl get endpoints -n prefect prefect-server
kubectl get endpoints -n default search-service
```

---

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status
kubectl get pods -n prefect

# Check pod logs
kubectl logs -n prefect <pod-name>

# Check pod events
kubectl describe pod -n prefect <pod-name>
```

#### 2. Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n prefect

# Verify image exists in registry
docker pull hub/prefect-integration-service:latest
```

#### 3. Database Connection Errors

```bash
# Check database service
kubectl get svc -n prefect prefect-db

# Test database connection
kubectl exec -n prefect deployment/prefect-server -- \
  psql -h prefect-db -U prefect -d prefect -c "SELECT 1"
```

#### 4. Network Policy Issues

```bash
# Check network policies
kubectl get networkpolicies -n prefect

# Test connectivity
kubectl exec -n prefect deployment/prefect-server -- \
  curl -f http://prefect-db:5432
```

#### 5. Resource Quota Exceeded

```bash
# Check resource quotas
kubectl get resourcequota -n prefect

# Check resource usage
kubectl top pods -n prefect
```

### Debugging Commands

```bash
# Get all resources in namespace
kubectl get all -n prefect

# Describe deployment
kubectl describe deployment -n prefect prefect-server

# View events
kubectl get events -n prefect --sort-by='.lastTimestamp'

# Check HPA status
kubectl get hpa -n prefect

# Check ingress
kubectl get ingress --all-namespaces
```

---

## Security Best Practices

### Secrets Management

**DO NOT** commit secrets to Git. Use:
- External Secrets Operator with AWS Secrets Manager
<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->

### Network Policies

All services have network policies restricting:
- Ingress: Only from allowed sources
- Egress: Only to required destinations

### Pod Security Standards

All pods use:
- `runAsNonRoot: true`
- `seccompProfile: RuntimeDefault`
- Restricted security context

### RBAC

All services use least-privilege RBAC:
- Service accounts with minimal permissions
- Role-based access control
- No cluster-admin permissions

---

## Production Considerations

### High Availability

- **Prefect Server**: 3 replicas with pod anti-affinity
- **Prefect Workers**: Auto-scaling (3-20 replicas)
- **Other Services**: 2-3 replicas based on load

### Resource Limits

- Set appropriate resource requests and limits
- Monitor resource usage
- Adjust based on actual workload

### Monitoring

- Enable Prometheus metrics scraping
- Set up Grafana dashboards
- Configure alerting rules

### Backup

- Prefect Server database: Regular backups
- ConfigMaps and Secrets: Version controlled
- Persistent volumes: Snapshot regularly

---

## Rollback Procedures

### Rollback Deployment

```bash
# Rollback to previous revision
kubectl rollout undo deployment/prefect-server -n prefect

# Rollback to specific revision
kubectl rollout undo deployment/prefect-server -n prefect --to-revision=2

# Check rollout history
kubectl rollout history deployment/prefect-server -n prefect
```

### Delete Deployment

```bash
# Delete service (use with caution)
kubectl delete -k k8s/prefect-server/base

# Delete with namespace
kubectl delete namespace prefect
```

---

## Next Steps

1. ✅ All manifests created
2. ⏳ Configure secrets management
3. ⏳ Set up CI/CD for automated deployment
4. ⏳ Configure monitoring and alerting
5. ⏳ Test in staging environment
6. ⏳ Deploy to production

---

**Last Updated:** 2025-01-15


---

# Docker Compose Deployment Guide

Complete guide for deploying the Data Interoperability Hub using Docker Compose in development, staging, and production environments.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment Steps](#deployment-steps) — [Step 0: Release gate (Phase 12A + sign-off)](#step-0-run-phase-12a-and-obtain-sign-off-release-gate) must be satisfied before proceeding
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Troubleshooting](#troubleshooting)
7. [Rollback Procedures](#rollback-procedures)
8. [Maintenance](#maintenance)
9. [Best Practices](#best-practices)

---

## Overview

The Data Interoperability Hub is deployed using Docker Compose, which orchestrates **all services** in a single stack:

- **Infrastructure**: PostgreSQL, Redis (cache, queue, events, channels), MinIO, Fuseki, Redis exporters
- **Core**: API Service, Worker Service, Frontend
- **Workflow**: Workflow Engine, Workflow Registry
- **Event Bus**: Event Bus Health, Event Schema Registry
- **Microservices**: Semantic, DQ, Compliance, DataContract, Search, Observability, Webhook
- **Gateways**: API Gateway, Traefik
- **Orchestration**: Prefect Server, Prefect DB, Prefect Workers, Prefect Integration Service
- **Monitoring**: Prometheus, Grafana, Jaeger, Alertmanager
- **Support**: MailHog (dev), Mock Server (marketplace tests), CKAN test DB/Solr/Redis (optional), ODH Training Operator, ODH Inference Scheduler

**Run all services:**

```bash
# Production-style full stack (docker-compose.yml)
docker compose up -d

# Development full stack with hot-reload (docker-compose.dev.yml)
docker compose -f docker-compose.dev.yml up -d
```

**Deployment Environments:**
- **Development**: Local development with hot-reload (`docker-compose.dev.yml`) — all services run via Docker Compose
- **Staging**: Pre-production testing (`docker-compose.staging.yml`)
- **Production**: Production deployment (`docker-compose.yml`)

**Project approach**: Deployment is Docker Compose–based for development, staging, and production. Kubernetes (K8s) is used only where already in place (e.g. Prefect workers, scheduled ingestion); see [DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md](DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md) for that flow.

**Release gate (deploy after green tests)**  
Do **not** deploy to staging or production until the full test suite is green and (when gap remediation applies) sign-off is obtained. Use the **same suite and evidence location** every time:

- **Suite**: Phase 12A full run — `./scripts/run_phase_12a_full_suites.sh` (backend unit/integration/E2E, frontend unit/E2E, security, performance, concurrency, regression). See [RUNBOOKS.md — Full test suite (Phase 12A-style)](RUNBOOKS.md#full-test-suite-phase-12a-style) and [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md).
- **Evidence location**: `test_reports_comprehensive/{date}/` (unit/, integration/, e2e/, security/, performance/, concurrency/, regression/, frontend-unit/, frontend-e2e/, `phase_12a_1_summary.json`, `phase_12a_3_summary.json`). Generate the test summary report with `./scripts/generate_test_summary_report.sh YYYY-MM-DD`.
- **Sign-off**: When gap remediation applies, follow [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation). Release MUST NOT proceed until sign-off is obtained.

Canonical release criteria: [RELEASE.md](RELEASE.md).

---

## Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU**: 4 cores
- **Memory**: 8GB RAM
- **Disk**: 50GB free space
- **Network**: Internet access for pulling images

#### Recommended Requirements
- **CPU**: 8+ cores
- **Memory**: 16GB+ RAM
- **Disk**: 100GB+ free space (SSD recommended)
- **Network**: Stable internet connection

#### Production Requirements
- **CPU**: 16+ cores
- **Memory**: 32GB+ RAM
- **Disk**: 500GB+ free space (SSD required)
- **Network**: High-bandwidth, low-latency connection

### Software Requirements

#### Required Software
- **Docker Engine** 20.10+ or Docker Desktop 4.0+
- **Docker Compose** 2.0+ (included with Docker Desktop)
- **Git** 2.30+ (for cloning repository)
- **Bash** 4.0+ (for running scripts)

#### Optional Software
- **PostgreSQL Client** (for database operations)
- **Redis CLI** (for Redis operations)
- **curl** or **wget** (for health checks)
- **jq** (for JSON processing)

### Access Requirements

#### Required Access
- **Docker Hub** or container registry access (for pulling images)
- **Git Repository** access (for cloning code)
- **System Administrator** privileges (for Docker operations)
- **Network Access** to required external services

#### Optional Access
- **Monitoring Tools** access (Prometheus, Grafana)
- **Log Aggregation** access (if using external logging)
- **Backup Storage** access (for database backups)

### Knowledge Requirements

#### Required Knowledge
- Docker and Docker Compose basics
- Linux/Unix command line
- Basic networking concepts
- Service health checking

#### Recommended Knowledge
- Docker networking and volumes
- Database administration (PostgreSQL)
- Monitoring and observability
- CI/CD concepts

### Environment-Specific Prerequisites

#### Development Environment
- Python 3.12+ (for local development tools)
- Code editor/IDE
- Git configured with credentials

#### Staging Environment
- Staging-specific credentials and secrets
- Access to staging external services
- Test data preparation

#### Production Environment
- Production credentials and secrets (securely stored)
- Access to production external services
- Backup and disaster recovery procedures
- Monitoring and alerting configured

---

## Pre-Deployment Checklist

### System Verification

- [ ] Docker Engine is installed and running
- [ ] Docker Compose is installed and accessible
- [ ] Sufficient disk space available
- [ ] Sufficient memory available
- [ ] Network connectivity verified
- [ ] Required ports are not in use
- [ ] Firewall rules configured (if applicable)

### Configuration Verification

- [ ] Docker Compose file selected (dev/staging/production)
- [ ] Environment variables configured
- [ ] Secrets and credentials prepared
- [ ] Database credentials verified
- [ ] External service endpoints verified
- [ ] SSL certificates prepared (if using HTTPS)

### Test and sign-off verification (release gate)

- [ ] Phase 12A full suite run and all critical suites green (`./scripts/run_phase_12a_full_suites.sh`)
- [ ] Evidence present in `test_reports_comprehensive/{date}/` (see [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md#directory-structure))
- [ ] Test summary report generated (`./scripts/generate_test_summary_report.sh YYYY-MM-DD`)
- [ ] Sign-off obtained when gap remediation applies (see [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation))

Full release gate: [RELEASE.md](RELEASE.md).

### Backup Verification

- [ ] Database backup created (if upgrading)
- [ ] Volume backups created (if upgrading)
- [ ] Configuration backups created
- [ ] Rollback plan documented

### Documentation Verification

- [ ] Deployment procedures reviewed
- [ ] Troubleshooting guide reviewed
- [ ] Rollback procedures reviewed
- [ ] Emergency contacts available

---

## Deployment Steps

### Step 0: Run Phase 12A and obtain sign-off (release gate)

Before deploying to staging or production, ensure the same test suite and evidence layout are used so deployment is consistent with "green Phase 12A + sign-off":

1. **Run full Phase 12A suite**:
   ```bash
   ./scripts/run_phase_12a_full_suites.sh
   ```
   Ensure all critical suites are green; fix failures at root cause before proceeding. Backend-only option: `./scripts/run_phase_12a_backend_suites.sh` if frontend/12A.3 are not required for the change.

2. **Evidence location**: Artifacts are written to `test_reports_comprehensive/YYYY-MM-DD/` (set `DATE` to override). See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md#directory-structure).

3. **Generate test summary report**:
   ```bash
   ./scripts/generate_test_summary_report.sh YYYY-MM-DD
   ```
   Use the date of the run. Verify the report contains execution summary and evidence links.

4. **Sign-off** (when gap remediation applies): Product/tech lead confirms per [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation). Release MUST NOT proceed until sign-off is obtained.

If any of the above is not satisfied, do not proceed to Step 1. Fix issues and re-run the suite.

### Step 1: Prepare Environment

#### 1.1 Clone Repository

```bash
# Clone repository
git clone <repository-url>
cd DataInteroperabilityHub

# Checkout desired branch/tag
git checkout <branch-or-tag>
```

#### 1.2 Configure Environment Variables

Create environment-specific configuration:

**Development** (`.env.dev`):
```bash
# Database
POSTGRES_USER=hub_dev
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=hub_dev

# Application
SECRET_KEY=dev-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Email (console backend for development)
EMAIL_BACKEND=console

# Marketplace Connectors (see Marketplace Configuration section below)
DADOS_GOV_BR_API_KEY=your-jwt-token-here
CKAN_TEST_URL=https://demo.ckan.org
CKAN_TEST_API_KEY=your-test-api-key-here
```

**Staging** (`.env.staging`):
```bash
# Database
POSTGRES_USER=hub_staging
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=hub_staging

# Application
SECRET_KEY=<staging-secret-key>
DEBUG=False
ALLOWED_HOSTS=staging.hub.example.com

# Email
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=<smtp-username>
SMTP_PASSWORD=<smtp-password>

# Marketplace Connectors (see Marketplace Configuration section below)
DADOS_GOV_BR_API_KEY=<jwt-token-from-secrets-manager>
CKAN_TEST_URL=https://dados.gov.br
CKAN_TEST_API_KEY=<api-key-from-secrets-manager>
SNOWFLAKE_ACCOUNT=<snowflake-account>
SNOWFLAKE_USER=<snowflake-user>
SNOWFLAKE_TOKEN=<snowflake-token>
SNOWFLAKE_WAREHOUSE=<snowflake-warehouse>
SNOWFLAKE_ROLE=<snowflake-role>
SNOWFLAKE_DATABASE=<snowflake-database>
```

**Production** (`.env.production`):
```bash
# Database
POSTGRES_USER=hub_prod
POSTGRES_PASSWORD=<secure-production-password>
POSTGRES_DB=hub_prod

# Application
SECRET_KEY=<production-secret-key>
DEBUG=False
ALLOWED_HOSTS=hub.example.com,api.hub.example.com

# Email
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.production.com
SMTP_PORT=587
SMTP_USERNAME=<smtp-username>
SMTP_PASSWORD=<smtp-password>

# Marketplace Connectors (see Marketplace Configuration section below)
# IMPORTANT: Use AWS Secrets Manager for production
DADOS_GOV_BR_API_KEY=<jwt-token-from-secrets-manager>
CKAN_TEST_URL=https://dados.gov.br
CKAN_TEST_API_KEY=<api-key-from-secrets-manager>
SNOWFLAKE_ACCOUNT=<snowflake-account>
SNOWFLAKE_USER=<snowflake-user>
SNOWFLAKE_TOKEN=<snowflake-token>
SNOWFLAKE_WAREHOUSE=<snowflake-warehouse>
SNOWFLAKE_ROLE=<snowflake-role>
SNOWFLAKE_DATABASE=<snowflake-database>
```

#### 1.2.1 Marketplace Connector Configuration

The Data Interoperability Hub supports integration with multiple marketplace instances for harvesting data. Configure the following environment variables based on your requirements:

**Marketplace Environment Variables:**

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `DADOS_GOV_BR_API_KEY` | JWT Bearer token for dados.gov.br Swagger API (NOT CKAN). Format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Yes* | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `CKAN_DADOS_GOV_BR_API_KEY` | **DEPRECATED** - Use `DADOS_GOV_BR_API_KEY` instead. Still supported for backward compatibility. | No | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `CKAN_TEST_URL` | Marketplace connector instance URL for testing (supports both CKAN and Swagger). Used for test instances like demo.ckan.org. | No | `https://demo.ckan.org` | `https://demo.ckan.org` or `https://dados.gov.br` |
| `CKAN_TEST_API_KEY` | API key for CKAN test instances (demo.ckan.org, data.gov). Not required for dados.gov.br (uses JWT token). | No | None | `test-key-abc123...` |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g., `xy12345.us-east-1`). Required for Snowflake Data Marketplace connector. | No** | None | `xy12345.us-east-1` |
| `SNOWFLAKE_USER` | Snowflake user name for authentication. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_USER` |
| `SNOWFLAKE_TOKEN` | Snowflake authentication token (JWT or OAuth token). Required for Snowflake Data Marketplace connector. | No** | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `SNOWFLAKE_WAREHOUSE` | Snowflake warehouse name for executing queries. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_WAREHOUSE` |
| `SNOWFLAKE_ROLE` | Snowflake role for access control. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_ROLE` |
| `SNOWFLAKE_DATABASE` | Snowflake database name for marketplace data. Required for Snowflake Data Marketplace connector. | No** | None | `MARKETPLACE_DB` |
| `MOCK_SERVER_URL` | Mock server URL for testing marketplace connectors (internal service). Used for integration testing. | No | `http://mock-server:8080` | `http://mock-server:8080` |

\* Required for dados.gov.br Swagger API connector. Other CKAN instances (demo.ckan.org, data.gov) use standard API keys and don't require JWT tokens.

\** Required if using Snowflake Data Marketplace connector. All Snowflake variables must be set together.

**Marketplace Configuration Requirements:**

**1. dados.gov.br (Brazilian Government Open Data Portal)**
- **Type**: Swagger API (NOT CKAN)
- **Base URL**: `https://dados.gov.br`
- **Authentication**: JWT Bearer token
- **Required Variables**:
  - `DADOS_GOV_BR_API_KEY` (JWT token format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)
- **Connector**: `DadosGovBrConnector` (Swagger-based)
- **Swagger Spec**: Automatically loaded from `https://dados.gov.br/v3/api-docs`
- **Note**: Uses custom Swagger APIs (`/dados/api/publico/conjuntos-dados`), NOT standard CKAN APIs

**2. CKAN Instances (demo.ckan.org, data.gov)**
- **Type**: Standard CKAN API
- **Base URLs**:
  - `https://demo.ckan.org` (default test instance)
  - `https://data.gov` (US Government Open Data Portal)
- **Authentication**: Standard CKAN API key (not JWT token)
- **Required Variables**:
  - `CKAN_TEST_URL` (instance URL)
  - `CKAN_TEST_API_KEY` (API key from CKAN instance)
- **Connector**: `CKANConnector` (standard CKAN API)
- **Note**: API keys can be obtained from CKAN instance user profile

**3. Snowflake Data Marketplace**
- **Type**: Snowflake Data Marketplace
- **Authentication**: Snowflake account, user, token, warehouse, role, database
- **Required Variables** (all must be set together):
  - `SNOWFLAKE_ACCOUNT` (account identifier)
  - `SNOWFLAKE_USER` (user name)
  - `SNOWFLAKE_TOKEN` (authentication token)
  - `SNOWFLAKE_WAREHOUSE` (warehouse name)
  - `SNOWFLAKE_ROLE` (role name)
  - `SNOWFLAKE_DATABASE` (database name)
- **Connector**: Snowflake Data Marketplace connector
- **Documentation**: See [Snowflake Data Marketplace Documentation](https://docs.snowflake.com/user-guide/gen-conn-config)

**4. Mock Server (Testing)**
- **Type**: Mock server for integration testing
- **Base URL**: `http://mock-server:8080` (internal Docker network)
- **Authentication**: None (testing only)
- **Required Variables**:
  - `MOCK_SERVER_URL` (default: `http://mock-server:8080`)
- **Purpose**: Simulate marketplace APIs for testing
- **Note**: Only used in development/testing environments

**Configuration Examples:**

**Development Environment:**
```bash
# Minimal configuration for development
DADOS_GOV_BR_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
CKAN_TEST_URL=https://demo.ckan.org
CKAN_TEST_API_KEY=test-key-abc123
MOCK_SERVER_URL=http://mock-server:8080
```

**Staging Environment:**
```bash
# Full configuration for staging
DADOS_GOV_BR_API_KEY=<jwt-token-from-secrets-manager>
CKAN_TEST_URL=https://dados.gov.br
CKAN_TEST_API_KEY=<api-key-from-secrets-manager>
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=MARKETPLACE_USER
SNOWFLAKE_TOKEN=<token-from-secrets-manager>
SNOWFLAKE_WAREHOUSE=MARKETPLACE_WAREHOUSE
SNOWFLAKE_ROLE=MARKETPLACE_ROLE
SNOWFLAKE_DATABASE=MARKETPLACE_DB
MOCK_SERVER_URL=http://mock-server:8080
```

**Production Environment:**
```bash
# Production configuration (use secrets manager)
# IMPORTANT: Never hardcode secrets in production
# Use AWS Secrets Manager
DADOS_GOV_BR_API_KEY=<from-secrets-manager>
CKAN_TEST_URL=https://dados.gov.br
CKAN_TEST_API_KEY=<from-secrets-manager>
SNOWFLAKE_ACCOUNT=<from-secrets-manager>
SNOWFLAKE_USER=<from-secrets-manager>
SNOWFLAKE_TOKEN=<from-secrets-manager>
SNOWFLAKE_WAREHOUSE=<from-secrets-manager>
SNOWFLAKE_ROLE=<from-secrets-manager>
SNOWFLAKE_DATABASE=<from-secrets-manager>
```

**Security Best Practices:**
- **Never commit secrets to Git**: Use `.gitignore` to exclude `.env*` files
- **Use secrets managers in production**: AWS Secrets Manager
- **Rotate credentials regularly**: Rotate API keys and tokens every 90 days
- **Use least privilege**: API keys should have minimal required permissions
- **Monitor access**: Enable audit logging for API key usage

For detailed marketplace connector deployment and troubleshooting, see [Marketplace Connector Deployment Runbook](./runbooks/marketplace-connector-deployment.md).

#### 1.3 Select Docker Compose File

```bash
# Development
export COMPOSE_FILE=docker-compose.dev.yml
export ENVIRONMENT=development

# Staging
export COMPOSE_FILE=docker-compose.staging.yml
export ENVIRONMENT=staging

# Production
export COMPOSE_FILE=docker-compose.yml
export ENVIRONMENT=production
```

#### 1.4 Test runtime (integration and E2E)

For running integration and E2E tests against a Compose stack:

- **Compose file**: Use `docker-compose.dev.yml` (service `api-service`) or `docker-compose.test.yml` (service `api-service-test`). With `docker-compose.test.yml`, set `export COMPOSE_FILE=docker-compose.test.yml` before starting the stack and before running Phase 12A scripts so they target `api-service-test`.
- **Required env for pytest**: Set `PYTEST_DOCKER_COMPOSE_RUNTIME=1` when using `--docker-compose-runtime` so integration and E2E run consistently.
- **Commands and minimal services**: See [TEST_EXECUTION_PLAN — Docker Compose and test runtime](./TEST_EXECUTION_PLAN.md#docker-compose-and-test-runtime-integration-and-e2e) for which compose file to use, how to start the stack, and how to run `pytest tests/integration/ -v --docker-compose-runtime` and E2E with no silent dependency gaps.

### Step 2: Validate Configuration

#### 2.1 Validate Docker Compose File

```bash
# Validate syntax
docker compose -f ${COMPOSE_FILE} config > /dev/null

# View resolved configuration
docker compose -f ${COMPOSE_FILE} config

# Check for errors
docker compose -f ${COMPOSE_FILE} config --quiet
```

#### 2.2 Check Prerequisites

```bash
# Check Docker version
docker --version
docker compose version

# Check disk space
df -h

# Check available memory
free -h

# Check port availability
netstat -tuln | grep -E "8000|5432|6379|9000"
```

### Step 3: Pull Images

#### 3.1 Pull All Images

```bash
# Pull all images
docker compose -f ${COMPOSE_FILE} pull

# Pull specific images
docker compose -f ${COMPOSE_FILE} pull postgres redis minio
```

#### 3.2 Verify Images

```bash
# List pulled images
docker images | grep hub

# Verify image tags
docker compose -f ${COMPOSE_FILE} config | grep image:
```

### Step 4: Start Infrastructure Services

#### 4.1 Start Infrastructure

```bash
# Start infrastructure services first
docker compose -f ${COMPOSE_FILE} up -d postgres redis minio fuseki

# Wait for services to be healthy
docker compose -f ${COMPOSE_FILE} ps

# Check health
./scripts/health-checks/health-check-all.sh
```

#### 4.2 Verify Infrastructure

```bash
# Check PostgreSQL
docker compose -f ${COMPOSE_FILE} exec postgres pg_isready -U hub

# Check Redis
docker compose -f ${COMPOSE_FILE} exec redis redis-cli ping

# Check MinIO
curl http://localhost:9000/minio/health/live

# Check Fuseki
curl http://localhost:3030/\$/ping
```

### Step 5: Initialize Database

#### 5.1 Run Migrations

```bash
# Run Django migrations
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py migrate

# Check migration status
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py showmigrations
```

#### 5.2 Create Superuser (if needed)

```bash
# Create superuser interactively
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py createsuperuser

# Or create superuser non-interactively
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py createsuperuser --noinput \
  --username admin \
  --email admin@example.com
```

#### 5.3 Load Initial Data (optional)

```bash
# Load fixtures
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py loaddata fixtures/initial_data.json

# Load test data (development/staging only)
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py loaddata fixtures/test_data.json
```

### Step 6: Start Application Services

#### 6.1 Start Core Services

```bash
# Start API and Worker services
docker compose -f ${COMPOSE_FILE} up -d api-service worker-service

# Wait for services to be healthy
sleep 30
docker compose -f ${COMPOSE_FILE} ps
```

#### 6.2 Start Workflow Services

```bash
# Start workflow services
docker compose -f ${COMPOSE_FILE} up -d workflow-engine-service workflow-registry-service

# Wait for services to be healthy
sleep 30
docker compose -f ${COMPOSE_FILE} ps
```

#### 6.3 Start Event Bus Services

```bash
# Start event bus services
docker compose -f ${COMPOSE_FILE} up -d event-bus-health-service event-schema-registry-service

# Wait for services to be healthy
sleep 30
docker compose -f ${COMPOSE_FILE} ps
```

#### 6.4 Start Microservices

```bash
# Start all microservices
docker compose -f ${COMPOSE_FILE} up -d \
  semantic-service \
  dq-service \
  compliance-service \
  datacontract-service \
  search-service \
  observability-service \
  webhook-service \
  prefect-integration-service

# Wait for services to be healthy
sleep 30
docker compose -f ${COMPOSE_FILE} ps
```

### Step 7: Start Monitoring Services

#### 7.1 Start Monitoring Stack

```bash
# Start monitoring services
docker compose -f ${COMPOSE_FILE} up -d prometheus grafana jaeger alertmanager

# Wait for services to be healthy
sleep 30
docker compose -f ${COMPOSE_FILE} ps
```

#### 7.2 Verify Monitoring

```bash
# Check Prometheus
curl http://localhost:9090/-/healthy

# Check Grafana
curl http://localhost:3000/api/health

# Check Jaeger
curl http://localhost:16686/

# Check Alertmanager
curl http://localhost:9093/-/healthy
```

### Step 8: Start API Gateway

#### 8.1 Start Traefik

```bash
# Start Traefik
docker compose -f ${COMPOSE_FILE} up -d traefik

# Wait for service to be healthy
sleep 10
docker compose -f ${COMPOSE_FILE} ps traefik
```

#### 8.2 Verify API Gateway

```bash
# Check Traefik dashboard
curl http://localhost:8080/ping

# Access dashboard (if enabled)
open http://localhost:8080
```

### Step 9: Start Prefect Services (if needed)

#### 9.1 Start Prefect Stack

```bash
# Start Prefect services
docker compose -f ${COMPOSE_FILE} up -d prefect-db prefect-server prefect-worker

# Wait for services to be healthy
sleep 30
docker compose -f ${COMPOSE_FILE} ps
```

#### 9.2 Verify Prefect

```bash
# Check Prefect Server
curl http://localhost:4200/health

# Access Prefect UI
open http://localhost:4201
```

#### 9.3 Configure Prefect Worker for Scheduled Ingestion

The Prefect worker requires hub API configuration to execute scheduled ingestion flows:

```bash
# Set hub API configuration in .env file
HUB_BASE_URL=http://api-service:8000
HUB_WORKER_API_KEY=<your-api-key>

# Generate API key if needed (from api-service container)
docker compose exec api-service python hub/manage.py create_api_key \
  --scopes scheduled_ingestion:internal

# Restart prefect-worker to pick up configuration
docker compose restart prefect-worker

# Verify worker can reach hub API
docker compose exec prefect-worker curl -f http://api-service:8000/health
```

**Note**: The Prefect worker image includes the scheduled ingestion flow and tasks via volume mount (`./services/prefect-integration:/app:ro`). For production, consider building a custom worker image that includes the workflows.

### Step 10: Complete Deployment

#### 10.1 Start All Remaining Services

```bash
# Start all services (if not already started)
docker compose -f ${COMPOSE_FILE} up -d

# Verify all services are running
docker compose -f ${COMPOSE_FILE} ps
```

#### 10.2 Run Health Checks

```bash
# Run comprehensive health checks
./scripts/health-checks/health-check-all.sh

# Check specific service groups
./scripts/health-checks/health-check-workflow.sh
./scripts/health-checks/health-check-event-bus.sh
./scripts/health-checks/health-check-service-layer.sh
```

---

## Post-Deployment Verification

### Service Health Verification

#### 1. Check All Services

```bash
# Run health check script
./scripts/health-checks/health-check-all.sh

# Expected output: All services healthy
```

#### 2. Verify Service Endpoints

```bash
# API Service
curl http://localhost:8000/health

# Worker Service
curl http://localhost:8080/healthz

# Workflow Engine
curl http://localhost:8088/healthz

# All microservices
curl http://localhost:8081/health  # Semantic
curl http://localhost:8082/health  # Compliance
curl http://localhost:8083/health  # DQ
curl http://localhost:8085/health  # Search
curl http://localhost:8086/health  # Observability
curl http://localhost:8087/health  # Webhook
```

### Functional Verification

#### 1. Test API Endpoints

```bash
# Test API health
curl http://localhost:8000/health

# Test API endpoints (if authenticated)
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/contracts/

# Test API documentation
open http://localhost:8000/api/docs
```

#### 2. Test Worker Functionality

```bash
# Check worker logs
docker compose -f ${COMPOSE_FILE} logs worker-service | tail -20

# Verify worker is processing jobs
docker compose -f ${COMPOSE_FILE} exec worker-service python -c "from django_rq import get_worker; print(get_worker().queues)"
```

#### 3. Test Workflow Engine

```bash
# Check workflow engine logs
docker compose -f ${COMPOSE_FILE} logs workflow-engine-service | tail -20

# Verify workflow registry
curl http://localhost:8089/health
```

### Monitoring Verification

#### 1. Verify Prometheus

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Check Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up
```

#### 2. Verify Grafana

```bash
# Access Grafana (default: admin/admin)
open http://localhost:3000

# Verify dashboards are loaded
curl -u admin:admin http://localhost:3000/api/dashboards/home
```

#### 3. Verify Jaeger

```bash
# Access Jaeger UI
open http://localhost:16686

# Check for traces
curl http://localhost:16686/api/traces?service=api-service
```

### Database Verification

#### 1. Verify Database Connection

```bash
# Connect to database
docker compose -f ${COMPOSE_FILE} exec postgres psql -U hub -d hub

# Check tables
\dt

# Check migrations
SELECT * FROM django_migrations ORDER BY applied DESC LIMIT 10;
```

#### 2. Verify Data Integrity

```bash
# Check table counts
docker compose -f ${COMPOSE_FILE} exec postgres psql -U hub -d hub -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';"

# Verify critical tables have data
docker compose -f ${COMPOSE_FILE} exec postgres psql -U hub -d hub -c "SELECT COUNT(*) FROM auth_user;"
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Services Won't Start

**Symptoms:**
- Services fail to start
- Containers exit immediately
- Error messages in logs

**Diagnosis:**
```bash
# Check service status
docker compose -f ${COMPOSE_FILE} ps

# Check service logs
docker compose -f ${COMPOSE_FILE} logs <service-name>

# Check container logs
docker logs <container-name>
```

**Solutions:**
1. **Check dependencies**: Ensure infrastructure services are running
2. **Check ports**: Verify ports are not in use
3. **Check volumes**: Verify volumes are accessible
4. **Check environment variables**: Verify all required variables are set
5. **Check resource limits**: Ensure sufficient resources available

#### Issue 2: Database Connection Failures

**Symptoms:**
- Services can't connect to database
- Database connection errors in logs
- Migration failures

**Diagnosis:**
```bash
# Check PostgreSQL is running
docker compose -f ${COMPOSE_FILE} ps postgres

# Test database connection
docker compose -f ${COMPOSE_FILE} exec postgres pg_isready -U hub

# Check database logs
docker compose -f ${COMPOSE_FILE} logs postgres | tail -50
```

**Solutions:**
1. **Verify credentials**: Check POSTGRES_USER and POSTGRES_PASSWORD
2. **Check network**: Ensure services are on same network
3. **Check database exists**: Verify POSTGRES_DB is created
4. **Restart database**: `docker compose -f ${COMPOSE_FILE} restart postgres`

#### Issue 2b: Postgres or Prefect-DB taking forever to start (old/corrupt data)

**Symptoms:**
- `postgres` or `prefect-db` container stays in "health: starting" or "starting" for many minutes
- Logs show "syncing data directory (fsync)" or "database system was not properly shut down; automatic recovery in progress"
- Dependent services (api-service, prefect-server, etc.) never start

**Solution: reset Postgres-related volumes and bring the stack up clean:**

```bash
# From repo root (removes pgdata, prefect-db-data, ckan-test-db-data and starts fresh)
./scripts/reset_postgres_volumes_and_up.sh --detach
```

If you see "container name already in use" errors, run once:

```bash
docker rm -f $(docker ps -aq --filter 'name=hub-') 2>/dev/null
docker compose up -d
```

Then run migrations and recreate users as needed (see "Initial deployment" in this doc).

#### Issue 2c: API or services — "no pg_hba.conf entry ... no encryption" (main postgres)

**Symptoms:**
- api-service (or other services) fail to start; logs show: `connection to server at "postgres" ... failed: FATAL: no pg_hba.conf entry for host "…", user "hub", database "hub", no encryption`

**Cause:** The main PostgreSQL (hub-postgres) by default may only allow SSL from remote hosts; Django and others connect without SSL.

**Fix for existing postgres volume (one-off):** Run once, then restart api-service (and any other service that uses postgres):

```bash
docker compose exec postgres sh -c 'echo "host all all 0.0.0.0/0 scram-sha-256" >> "$PGDATA/pg_hba.conf"'
docker compose exec postgres psql -U hub -d template1 -c "SELECT pg_reload_conf();"
docker compose restart api-service
```

**If API then fails with "database \"hub\" does not exist":** Create the database and restart:

```bash
docker compose exec postgres psql -U hub -d template1 -c "CREATE DATABASE hub;"
docker compose restart api-service
```

**New installs:** The repo mounts `infrastructure/postgres/02-pg-hba-host.sh` into postgres initdb so the rule is added on first creation. For existing pgdata volume, use the one-off above or reset volumes (see Issue 2b).

#### Issue 2d: Prefect server — "no pg_hba.conf entry ... no encryption" (prefect-db)

**Symptoms:**
- Prefect server logs: `InvalidAuthorizationSpecificationError: no pg_hba.conf entry for host "…", user "prefect", database "prefect", no encryption`

**Cause:** The Prefect DB (PostgreSQL) by default may only allow SSL connections from remote hosts; Prefect uses asyncpg, which connects without SSL unless configured.

**Fix for existing prefect-db volume (one-off):** Run once so prefect-db allows non-SSL connections, then reload config and restart Prefect server. Use `template1` for the reload (it always exists):

```bash
docker compose exec prefect-db sh -c 'echo "host all all 0.0.0.0/0 scram-sha-256" >> "$PGDATA/pg_hba.conf"'
docker compose exec prefect-db psql -U prefect -d template1 -c "SELECT pg_reload_conf();"
docker compose restart prefect-server
```

**If Prefect then fails with "database \"prefect\" does not exist":** The volume was likely created without `POSTGRES_DB=prefect`. Create the database and restart Prefect:

```bash
docker compose exec prefect-db psql -U prefect -d template1 -c "CREATE DATABASE prefect;"
docker compose restart prefect-server
```

**New installs:** The repo mounts `infrastructure/prefect-db/02-pg-hba-host.sh` into prefect-db's initdb; that script adds the same rule on first database creation. If you already had prefect-db-data, use the one-off above or remove the volume and bring the stack up again (see Issue 2b for volume reset).

#### Issue 2e: API service unhealthy or Prefect server restart loop

**Symptoms:**
- `api-service` shows "unhealthy" in `docker compose ps`
- `prefect-server` restarts repeatedly (e.g. "Restarting (0)" or "Up X seconds (health: starting)" then restarts)

**Causes and fixes (already applied in this repo):**
- **Prefect 3**: Use `prefect server start --host 0.0.0.0`. Set Redis messaging env vars (`PREFECT_MESSAGING_BROKER`, `PREFECT_REDIS_MESSAGING_*`) and depend on `redis-queue` so the server has a messaging broker. Health endpoint is `/api/health`; healthcheck uses `http://localhost:4200/api/health` with `start_period: 120s`.
- **API (Django)**: The compose healthcheck uses **liveness** only: `http://localhost:8000/health/live/`. That endpoint always returns 200 if the process is up (no DB/Redis check), so the container is marked healthy once Django is serving. Use `GET /health/` for **readiness** (returns 503 when DB or Redis is down).

**If still unhealthy after a clean start:**
- Check API liveness: `docker compose exec api-service curl -s http://localhost:8000/health/live/`
- Check API readiness: `docker compose exec api-service curl -s http://localhost:8000/health/`
- Check Prefect health: `docker compose exec prefect-server curl -s http://localhost:4200/api/health`
- Inspect logs: `docker compose logs api-service --tail=100` and `docker compose logs prefect-server --tail=100`

#### Issue 3: Health checks failing

**Symptoms:**
- Health check endpoints return errors
- Services marked as unhealthy
- Containers restarting

**Diagnosis:**
```bash
# Test health endpoint manually
curl -v http://localhost:<port>/<endpoint>

# Check service logs
docker compose -f ${COMPOSE_FILE} logs <service-name> | tail -50

# Check container health status
docker inspect <container-name> | grep -A 10 Health
```

**Solutions:**
1. **Check endpoint exists**: Verify health endpoint is implemented
2. **Check service is ready**: Wait for service to fully start
3. **Check dependencies**: Ensure all dependencies are healthy
4. **Increase timeout**: Adjust health check timeout if needed

#### Issue 4: Port Conflicts

**Symptoms:**
- Services fail to start
- "Port already in use" errors
- Services can't bind to ports

**Diagnosis:**
```bash
# Find process using port
lsof -i :8000
netstat -tuln | grep 8000

# Check Docker port mappings
docker compose -f ${COMPOSE_FILE} ps
```

**Solutions:**
1. **Stop conflicting service**: Stop service using the port
2. **Change port**: Modify port mapping in compose file
3. **Kill process**: `kill -9 <PID>` (use with caution)

#### Issue 5: Volume Mount Issues

**Symptoms:**
- Services can't access volumes
- Permission denied errors
- Data not persisting

**Diagnosis:**
```bash
# Check volumes exist
docker volume ls | grep hub

# Check volume permissions
docker volume inspect <volume-name>

# Check mount points
docker inspect <container-name> | grep -A 10 Mounts
```

**Solutions:**
1. **Create volumes**: `docker volume create <volume-name>`
2. **Fix permissions**: Adjust volume permissions
3. **Check paths**: Verify volume paths are correct

#### Issue 6: Network Issues

**Symptoms:**
- Services can't communicate
- Connection refused errors
- DNS resolution failures

**Diagnosis:**
```bash
# Check network exists
docker network ls | grep hub-net

# Inspect network
docker network inspect hub-net

# Test connectivity
docker compose -f ${COMPOSE_FILE} exec api-service ping postgres
```

**Solutions:**
1. **Recreate network**: `docker network create hub-net`
2. **Restart services**: Restart services to reconnect to network
3. **Check service names**: Verify service names match DNS names

### Advanced Troubleshooting

#### Viewing Logs

```bash
# View all logs
docker compose -f ${COMPOSE_FILE} logs

# View specific service logs
docker compose -f ${COMPOSE_FILE} logs -f api-service

# View last 100 lines
docker compose -f ${COMPOSE_FILE} logs --tail=100 api-service

# View logs with timestamps
docker compose -f ${COMPOSE_FILE} logs -t api-service
```

#### Debugging Containers

```bash
# Execute command in container
docker compose -f ${COMPOSE_FILE} exec api-service bash

# Check environment variables
docker compose -f ${COMPOSE_FILE} exec api-service env

# Check process list
docker compose -f ${COMPOSE_FILE} exec api-service ps aux

# Check network connectivity
docker compose -f ${COMPOSE_FILE} exec api-service curl http://postgres:5432
```

#### Resource Monitoring

```bash
# Check resource usage
docker stats

# Check specific container
docker stats <container-name>

# Check disk usage
docker system df

# Check volume usage
docker system df -v
```

---

## Rollback Procedures

If a **release fails** after deployment (e.g. critical errors, failed health checks, misconfiguration), roll back **application** (previous image/version) or **configuration** (restore previous config) using the scenarios below. No new tooling is required. After rollback, fix the root cause and re-run Phase 12A; obtain sign-off again before re-release. See [RUNBOOKS.md — Deployment and rollback](RUNBOOKS.md#deployment-and-rollback) for the release gate and evidence location.

### Rollback Scenarios

#### Scenario 1: Failed Deployment

**Symptoms:**
- Services fail to start after deployment
- Health checks failing
- Critical errors in logs

**Rollback Steps:**

1. **Stop Failed Deployment**
   ```bash
   # Stop all services
   docker compose -f ${COMPOSE_FILE} down
   ```

2. **Restore Previous Version**
   ```bash
   # Checkout previous version
   git checkout <previous-tag-or-commit>

   # Use previous compose file
   export COMPOSE_FILE=docker-compose.yml  # or previous version
   ```

3. **Restore Volumes (if needed)**
   ```bash
   # Stop services
   docker compose -f ${COMPOSE_FILE} down

   # Restore volume from backup
   docker run --rm \
     -v <volume-name>:/data \
     -v $(pwd):/backup \
     alpine tar xzf /backup/<backup-file>.tar.gz -C /
   ```

4. **Restart Services**
   ```bash
   # Start services with previous version
   docker compose -f ${COMPOSE_FILE} up -d

   # Verify services are healthy
   ./scripts/health-checks/health-check-all.sh
   ```

#### Scenario 2: Database Migration Failure

**Symptoms:**
- Migration errors
- Database schema inconsistencies
- Application errors related to database

**Rollback Steps:**

1. **Stop Application Services**
   ```bash
   # Stop services that use database
   docker compose -f ${COMPOSE_FILE} stop api-service worker-service
   ```

2. **Restore Database Backup**
   ```bash
   # Restore database from backup
   docker compose -f ${COMPOSE_FILE} exec -T postgres psql -U hub hub < backup_$(date +%Y%m%d).sql

   # Or restore from volume backup
   docker run --rm \
     -v hub-pgdata:/data \
     -v $(pwd):/backup \
     alpine tar xzf /backup/pgdata-backup.tar.gz -C /
   ```

3. **Revert Code Changes**
   ```bash
   # Checkout previous code version
   git checkout <previous-commit>

   # Rebuild services
   docker compose -f ${COMPOSE_FILE} build api-service
   ```

4. **Restart Services**
   ```bash
   # Start services
   docker compose -f ${COMPOSE_FILE} up -d api-service worker-service

   # Verify services are healthy
   ./scripts/health-checks/health-check-service-layer.sh
   ```

#### Scenario 3: Configuration Error

**Symptoms:**
- Services start but misconfigured
- Wrong environment variables
- Incorrect service settings

**Rollback Steps:**

1. **Identify Configuration Issue**
   ```bash
   # Check current configuration
   docker compose -f ${COMPOSE_FILE} config

   # Compare with previous configuration
   git diff <previous-commit> docker-compose.yml
   ```

2. **Restore Configuration**
   ```bash
   # Restore previous configuration
   git checkout <previous-commit> -- docker-compose.yml
   git checkout <previous-commit> -- .env.*
   ```

3. **Restart Services**
   ```bash
   # Restart services with corrected configuration
   docker compose -f ${COMPOSE_FILE} up -d

   # Verify configuration
   docker compose -f ${COMPOSE_FILE} config
   ```

#### Scenario 4: Partial Rollback

**Rollback Specific Service:**

1. **Stop Specific Service**
   ```bash
   # Stop specific service
   docker compose -f ${COMPOSE_FILE} stop <service-name>
   ```

2. **Restore Service to Previous Version**
   ```bash
   # Checkout previous service code
   git checkout <previous-commit> -- services/<service-name>/

   # Rebuild service
   docker compose -f ${COMPOSE_FILE} build <service-name>
   ```

3. **Restart Service**
   ```bash
   # Start service
   docker compose -f ${COMPOSE_FILE} up -d <service-name>

   # Verify service health
   ./scripts/health-checks/health-check-all.sh
   ```

### Rollback Best Practices

1. **Always Backup Before Deployment**
   - Database backups
   - Volume backups
   - Configuration backups

2. **Test Rollback Procedures**
   - Practice rollback in staging
   - Document rollback steps
   - Verify backups are restorable

3. **Maintain Rollback Documentation**
   - Document rollback procedures
   - Keep backup locations documented
   - Maintain rollback runbooks

4. **Monitor After Rollback**
   - Verify services are healthy
   - Check application functionality
   - Monitor for issues

---

## Maintenance

### Regular Maintenance Tasks

#### Daily Tasks
- Monitor service health
- Review error logs
- Check disk usage
- Verify backups

#### Weekly Tasks
- Review service logs for errors
- Check resource usage trends
- Verify monitoring is working
- Review security alerts

#### Monthly Tasks
- Update dependencies
- Review and optimize resource limits
- Clean up old logs and data
- Review and update documentation
- Security patches

#### Quarterly Tasks
- Review and update deployment procedures
- Performance testing
- Disaster recovery testing
- Capacity planning

### Backup Procedures

> **Important**: Always preserve `ENCRYPTION_KEY` alongside database backups.
> Encrypted credential fields cannot be decrypted without it. See
> § "Database Backup / Restore" for details.

#### Database Backups

```bash
# Create database backup
docker compose -f ${COMPOSE_FILE} exec postgres pg_dump -U hub hub > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated daily backup script
#!/bin/bash
BACKUP_DIR=/backups/postgres
mkdir -p ${BACKUP_DIR}
docker compose -f ${COMPOSE_FILE} exec -T postgres pg_dump -U hub hub | gzip > ${BACKUP_DIR}/backup_$(date +%Y%m%d).sql.gz
```

#### Volume Backups

```bash
# Backup PostgreSQL volume
docker run --rm \
  -v hub-pgdata:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/pgdata-backup_$(date +%Y%m%d).tar.gz /data

# Backup all volumes
for volume in $(docker volume ls -q | grep hub); do
  docker run --rm \
    -v ${volume}:/data \
    -v $(pwd):/backup \
    alpine tar czf /backup/${volume}-backup_$(date +%Y%m%d).tar.gz /data
done
```

### Update Procedures

#### Updating Services

```bash
# Pull latest images
docker compose -f ${COMPOSE_FILE} pull

# Rebuild services (if code changed)
docker compose -f ${COMPOSE_FILE} build

# Restart services
docker compose -f ${COMPOSE_FILE} up -d

# Run migrations (if needed)
docker compose -f ${COMPOSE_FILE} exec api-service python manage.py migrate
```

#### Updating Dependencies

```bash
# Update requirements
pip install -r requirements.txt --upgrade

# Update Docker images
docker compose -f ${COMPOSE_FILE} pull

# Rebuild services
docker compose -f ${COMPOSE_FILE} build --no-cache
```

---

## Management Command Cron Schedules (Phase 120D)

The following management commands should be scheduled as cron jobs (Kubernetes CronJob or system crontab):

| Command | Schedule | Description |
|---------|----------|-------------|
| `python manage.py reconcile_stripe` | `0 3 * * *` (daily 03:00 UTC) | Reconcile local subscription status with Stripe. Detects and fixes drift. Creates audit events for corrections. |
| `python manage.py revoke_expired_access` | `0 * * * *` (hourly) | Revoke access requests and entitlements past their `expires_at` date. Prevents stale access. |
| `python manage.py refresh_kyc_status` | `0 4 * * *` (daily 04:00 UTC) | Check KYC expiration and update tenant `kyc_status` to `EXPIRED` when `kyc_expires_at` is past. |
| `python manage.py billing_cleanup --webhook-days=90 --usage-months=24` | `0 5 * * 0` (weekly Sun 05:00 UTC) | Clean up old Stripe webhook events (>90 days) and usage records (>24 months). Batch 1000 at a time. |
| `python manage.py expire_entitlements` | `0 * * * *` (hourly) | Mark entitlements with `expires_at` in the past as `EXPIRED`. |
| `scripts/backup-postgres.sh` | `0 2 * * *` (daily 02:00 UTC) | Database backup to S3 with SHA-256 manifest and retention sweep. |

### Kubernetes CronJob Example

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: reconcile-stripe
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: reconcile
            image: ghcr.io/datahub/api-service:latest
            command: ["python", "manage.py", "reconcile_stripe"]
            envFrom:
            - secretRef:
                name: hub-api-secrets
          restartPolicy: OnFailure
```

---

## Best Practices

### Deployment Best Practices

1. **Always Test in Staging First**
   - Deploy to staging before production
   - Test all functionality in staging
   - Verify health checks pass

2. **Use Version Control**
   - Tag releases
   - Document changes
   - Maintain changelog

3. **Automate Where Possible**
   - Use deployment scripts
   - Automate health checks
   - Automate backups

4. **Monitor Deployments**
   - Watch logs during deployment
   - Monitor health checks
   - Verify functionality after deployment

5. **Have Rollback Plan**
   - Document rollback procedures
   - Test rollback in staging
   - Keep backups available

### Security Best Practices

1. **Secure Credentials**
   - Use environment variables for secrets
   - Never commit secrets to repository
   - Rotate credentials regularly

2. **Network Security**
   - Use Docker networks for isolation
   - Restrict external access
   - Use firewall rules

3. **Image Security**
   - Use official images
   - Keep images updated
   - Scan images for vulnerabilities

4. **Access Control**
   - Limit who can deploy
   - Use least privilege principle
   - Audit deployments

### Operational Best Practices

1. **Documentation**
   - Keep deployment docs updated
   - Document all changes
   - Maintain runbooks

2. **Monitoring**
   - Set up comprehensive monitoring
   - Configure alerts
   - Review metrics regularly

3. **Backup Strategy**
   - Regular automated backups
   - Test backup restoration
   - Store backups securely

4. **Disaster Recovery**
   - Have disaster recovery plan
   - Test recovery procedures
   - Document recovery steps

---

## References

- [Docker Compose Structure Documentation](./DOCKER_COMPOSE_STRUCTURE.md)
- [Staging Deployment Guide](./STAGING_DEPLOYMENT.md)
- [Development Deployment Guide](./DEVELOPMENT_DEPLOYMENT.md)
- [Health Check Scripts Documentation](./HEALTH_CHECK_SCRIPTS.md)
- [Docker Compose Official Documentation](https://docs.docker.com/compose/)


---

# Service Deployment Guide

Complete guide for deploying workflow engine service, event bus service, and service layer components.

## Table of Contents

1. [Overview](#overview)
2. [Workflow Engine Service Deployment](#workflow-engine-service-deployment)
3. [Event Bus Service Deployment](#event-bus-service-deployment)
4. [Service Layer Deployment](#service-layer-deployment)
5. [Service Configuration](#service-configuration)
6. [Service Troubleshooting](#service-troubleshooting)

---

## Overview

This guide covers deployment procedures, configuration, and troubleshooting for:

- **Workflow Engine Service**: Processes workflow instances continuously
- **Event Bus Service**: Provides event-driven communication infrastructure
- **Service Layer**: Core business logic services with standardized communication

All services support deployment via Docker Compose (development/staging) and Kubernetes (production).

---

## Workflow Engine Service Deployment

### Overview

The Workflow Engine Service is a long-running service that processes workflow instances continuously. It polls for workflow instances in `DRAFT` or `RUNNING` status and executes them using the workflow engine.

**Key Features:**
- Continuous workflow processing
- Health check endpoints (`/healthz`, `/ready`, `/metrics`)
- Prometheus metrics integration
- OpenTelemetry tracing support
- Graceful shutdown support

### Architecture

```
┌─────────────────────────────────────┐
│   Workflow Engine Service          │
│                                     │
│  ┌─────────────────────────────┐  │
│  │  Health Check Server         │  │
│  │  (Port 8088)                 │  │
│  │  - /healthz (liveness)       │  │
│  │  - /ready (readiness)        │  │
│  │  - /metrics (Prometheus)      │  │
│  └─────────────────────────────┘  │
│                                     │
│  ┌─────────────────────────────┐  │
│  │  Workflow Processor          │  │
│  │  - Polls for DRAFT workflows │  │
│  │  - Polls for RUNNING workflows│  │
│  │  - Executes workflows        │  │
│  └─────────────────────────────┘  │
│                                     │
│  ┌─────────────────────────────┐  │
│  │  Workflow Engine             │  │
│  │  - Task registry             │  │
│  │  - Step execution            │  │
│  │  - Error handling            │  │
│  └─────────────────────────────┘  │
└─────────────────────────────────────┘
         │                    │
         ▼                    ▼
    PostgreSQL          Redis (Event Bus)
```

### Docker Compose Deployment

#### Configuration

The workflow engine service is configured in `docker-compose.yml`:

```yaml
workflow-engine-service:
  build:
    context: .
    dockerfile: services/workflow-engine/Dockerfile
  container_name: hub-workflow-engine
  command: python services/workflow-engine/main.py --poll-interval ${WORKFLOW_ENGINE_POLL_INTERVAL:-5} --batch-size ${WORKFLOW_ENGINE_BATCH_SIZE:-10}
  ports:
    - "${WORKFLOW_ENGINE_HEALTH_PORT:-8088}:8088"
  environment:
    # Database configuration
    - DATABASE_URL=postgresql://${POSTGRES_USER:-hub}:${POSTGRES_PASSWORD:-hub}@postgres:5432/${POSTGRES_DB:-hub}
    # Redis configuration
    - REDIS_URL=redis://redis:6379/0
    # Workflow engine configuration
    - WORKFLOW_ENGINE_HEALTH_PORT=${WORKFLOW_ENGINE_HEALTH_PORT:-8088}
    - WORKFLOW_ENGINE_POLL_INTERVAL=${WORKFLOW_ENGINE_POLL_INTERVAL:-5}
    - WORKFLOW_ENGINE_BATCH_SIZE=${WORKFLOW_ENGINE_BATCH_SIZE:-10}
    # Django settings
    - DJANGO_SETTINGS_MODULE=hub.settings
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8088/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
```

#### Deployment Steps

1. **Start Infrastructure Services**:
   ```bash
   docker compose up -d postgres redis
   ```

2. **Wait for Infrastructure Health**:
   ```bash
   # Wait for PostgreSQL
   docker compose exec postgres pg_isready -U hub
   
   # Wait for Redis
   docker compose exec redis redis-cli ping
   ```

3. **Start Workflow Engine Service**:
   ```bash
   docker compose up -d workflow-engine-service
   ```

4. **Verify Deployment**:
   ```bash
   # Check container status
   docker compose ps workflow-engine-service
   
   # Check health endpoint
   curl http://localhost:8088/healthz
   
   # Check readiness endpoint
   curl http://localhost:8088/ready
   
   # Check metrics endpoint
   curl http://localhost:8088/metrics
   ```

5. **Check Logs**:
   ```bash
   docker compose logs -f workflow-engine-service
   ```

### Kubernetes Deployment

#### Prerequisites

- Kubernetes cluster access
- kubectl configured
- PostgreSQL and Redis services available

#### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-engine-service
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: workflow-engine-service
  template:
    metadata:
      labels:
        app: workflow-engine-service
    spec:
      containers:
      - name: workflow-engine
        image: hub-workflow-engine:latest
        ports:
        - containerPort: 8088
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        - name: WORKFLOW_ENGINE_POLL_INTERVAL
          value: "5"
        - name: WORKFLOW_ENGINE_BATCH_SIZE
          value: "10"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8088
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8088
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: workflow-engine-service
spec:
  selector:
    app: workflow-engine-service
  ports:
  - port: 8088
    targetPort: 8088
  type: ClusterIP
```

#### Deployment Steps

1. **Create Secrets**:
   ```bash
   kubectl create secret generic database-secret \
     --from-literal=url=postgresql://hub:hub@postgres:5432/hub
   
   kubectl create secret generic redis-secret \
     --from-literal=url=redis://redis:6379/0
   ```

2. **Deploy Service**:
   ```bash
   kubectl apply -f k8s/workflow-engine/deployment.yaml
   ```

3. **Verify Deployment**:
   ```bash
   # Check pods
   kubectl get pods -l app=workflow-engine-service
   
   # Check service
   kubectl get svc workflow-engine-service
   
   # Check logs
   kubectl logs -l app=workflow-engine-service --tail=100
   ```

### Configuration

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_ENGINE_HEALTH_PORT` | `8088` | Health check server port |
| `WORKFLOW_ENGINE_POLL_INTERVAL` | `5` | Polling interval in seconds |
| `WORKFLOW_ENGINE_BATCH_SIZE` | `10` | Number of workflows to process per batch |
| `DATABASE_URL` | - | PostgreSQL connection URL |
| `REDIS_URL` | - | Redis connection URL |
| `DJANGO_SETTINGS_MODULE` | `hub.settings` | Django settings module |
| `OPENTELEMETRY_ENABLED` | `true` | Enable OpenTelemetry tracing |
| `OPENTELEMETRY_METRICS_ENABLED` | `true` | Enable Prometheus metrics |
| `JAEGER_AGENT_HOST` | `jaeger` | Jaeger agent host |
| `JAEGER_AGENT_PORT` | `6831` | Jaeger agent port |

#### Command-Line Arguments

```bash
python services/workflow-engine/main.py \
  --poll-interval 5 \
  --batch-size 10
```

- `--poll-interval`: Polling interval in seconds (default: 5)
- `--batch-size`: Number of workflows to process per batch (default: 10)

### Health Checks

#### Liveness Probe (`/healthz`)

Returns 200 OK if the process is running:

```bash
curl http://localhost:8088/healthz
```

Response:
```json
{
  "status": "ok"
}
```

#### Readiness Probe (`/ready`)

Returns 200 OK if dependencies (database, Redis) are available:

```bash
curl http://localhost:8088/ready
```

Response:
```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected"
}
```

#### Metrics Endpoint (`/metrics`)

Prometheus metrics endpoint:

```bash
curl http://localhost:8088/metrics
```

### Monitoring

#### Prometheus Metrics

The service exposes Prometheus metrics at `/metrics`:

- `workflow_instances_created_total` - Total workflow instances created
- `workflow_instances_started_total` - Total workflow instances started
- `workflow_instances_completed_total` - Total workflow instances completed
- `workflow_instances_failed_total` - Total workflow instances failed
- `workflow_execution_duration_seconds` - Workflow execution duration histogram
- `workflow_instances_running` - Current running workflows (gauge)
- `workflow_instances_pending` - Current pending workflows (gauge)
- `workflow_instances_failed_current` - Current failed workflows (gauge)

#### Grafana Dashboard

Import the workflow orchestration dashboard:

```bash
# Dashboard file: monitoring/grafana/dashboards/workflow-orchestration.json
```

Dashboard includes:
- Workflow instance throughput
- Success/failure rates
- Execution duration (P95)
- Current workflow counts
- Retry and timeout rates

### Troubleshooting

#### Service Not Starting

**Symptoms**: Container exits immediately or fails health checks

**Diagnosis**:
```bash
# Check container logs
docker compose logs workflow-engine-service

# Check container status
docker compose ps workflow-engine-service

# Check health endpoint
curl http://localhost:8088/healthz
```

**Solutions**:
1. Verify database connection:
   ```bash
   docker compose exec postgres pg_isready -U hub
   ```

2. Verify Redis connection:
   ```bash
   docker compose exec redis redis-cli ping
   ```

3. Check environment variables:
   ```bash
   docker compose exec workflow-engine-service env | grep -E "DATABASE|REDIS|WORKFLOW"
   ```

4. Verify dependencies are healthy:
   ```bash
   docker compose ps postgres redis
   ```

#### Workflows Not Processing

**Symptoms**: Workflows remain in DRAFT or RUNNING status

**Diagnosis**:
```sql
-- Check workflow status distribution
SELECT status, COUNT(*) 
FROM workflow_instances 
GROUP BY status;

-- Check for failed workflows
SELECT id, workflow_name, status, error_message 
FROM workflow_instances 
WHERE status = 'FAILED' 
ORDER BY created_at DESC 
LIMIT 10;
```

**Solutions**:
1. Verify workflow tasks are registered:
   ```bash
   # Check service logs for "Registered task" messages
   docker compose logs workflow-engine-service | grep "Registered task"
   ```

2. Check workflow task registry:
   ```python
   from hub.apps.orchestration.engine import WorkflowEngine
   engine = WorkflowEngine()
   print(engine.task_registry.keys())
   ```

3. Verify workflow classes are imported:
   ```python
   # Check hub/apps/orchestration/workflows/__init__.py
   ```

4. Check for database locks:
   ```sql
   SELECT * FROM pg_locks WHERE relation = 'workflow_instances'::regclass;
   ```

#### Performance Issues

**Symptoms**: Slow workflow processing, high latency

**Diagnosis**:
```bash
# Check workflow execution metrics
curl http://localhost:8088/metrics | grep workflow_execution_duration

# Check database connections
docker compose exec postgres psql -U hub -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';"
```

**Solutions**:
1. Increase batch size:
   ```bash
   export WORKFLOW_ENGINE_BATCH_SIZE=20
   docker compose restart workflow-engine-service
   ```

2. Adjust poll interval:
   ```bash
   export WORKFLOW_ENGINE_POLL_INTERVAL=10
   docker compose restart workflow-engine-service
   ```

3. Scale horizontally (Kubernetes):
   ```bash
   kubectl scale deployment workflow-engine-service --replicas=3
   ```

4. Optimize database queries:
   - Add indexes on `workflow_instances.status`
   - Add indexes on `workflow_instances.created_at`
   - Review slow query log

---

## Event Bus Service Deployment

### Overview

The Event Bus Service provides event-driven communication infrastructure using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence, replay, and audit.

**Key Features:**
- Redis Pub/Sub for real-time event delivery
- PostgreSQL persistence for replay and audit
- Connection pooling for optimal performance
- Health check endpoints (`/health`, `/healthz`, `/ready`, `/metrics`)
- Dead letter queue support
- Event replay functionality

### Architecture

```
┌─────────────────────────────────────┐
│   Event Bus Service                 │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Health Service              │   │
│  │  (Port 8090)                 │   │
│  │  - /health (comprehensive)   │   │
│  │  - /healthz (liveness)       │   │
│  │  - /ready (readiness)        │   │
│  │  - /metrics (Prometheus)     │   │
│  │  - /stats (pool stats)       │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  EventBusClient             │   │
│  │  - Connection pooling       │   │
│  │  - Health checks            │   │
│  │  - Retry logic              │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  EventBus                   │   │
│  │  - Publish/Subscribe         │   │
│  │  - Event persistence        │   │
│  │  - Dead letter queue        │   │
│  │  - Event replay             │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
         │                    │
         ▼                    ▼
    Redis Pub/Sub        PostgreSQL
```

### Docker Compose Deployment

#### Configuration

The event bus health service is configured in `docker-compose.yml`:

```yaml
event-bus-health-service:
  build:
    context: .
    dockerfile: services/event-bus/Dockerfile
  container_name: hub-event-bus-health
  ports:
    - "${EVENT_BUS_HEALTH_PORT:-8090}:8090"
  environment:
    # Database configuration
    - DATABASE_URL=postgresql://${POSTGRES_USER:-hub}:${POSTGRES_PASSWORD:-hub}@postgres:5432/${POSTGRES_DB:-hub}
    # Redis configuration
    - REDIS_URL=redis://redis:6379/0
    # Event bus configuration
    - EVENT_BUS_REDIS_POOL_SIZE=${EVENT_BUS_REDIS_POOL_SIZE:-50}
    - EVENT_BUS_REDIS_MAX_CONNECTIONS=${EVENT_BUS_REDIS_MAX_CONNECTIONS:-100}
    - EVENT_BUS_REDIS_SOCKET_TIMEOUT=${EVENT_BUS_REDIS_SOCKET_TIMEOUT:-5}
    - EVENT_BUS_CHANNEL_PREFIX=${EVENT_BUS_CHANNEL_PREFIX:-events}
    - EVENT_BUS_ENABLE_PERSISTENCE=${EVENT_BUS_ENABLE_PERSISTENCE:-true}
    - EVENT_BUS_MAX_RETRIES=${EVENT_BUS_MAX_RETRIES:-3}
    - EVENT_BUS_HEALTH_PORT=${EVENT_BUS_HEALTH_PORT:-8090}
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8090/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
```

#### Deployment Steps

1. **Start Infrastructure Services**:
   ```bash
   docker compose up -d postgres redis
   ```

2. **Wait for Infrastructure Health**:
   ```bash
   # Wait for PostgreSQL
   docker compose exec postgres pg_isready -U hub
   
   # Wait for Redis
   docker compose exec redis redis-cli ping
   ```

3. **Start Event Bus Health Service**:
   ```bash
   docker compose up -d event-bus-health-service
   ```

4. **Verify Deployment**:
   ```bash
   # Check container status
   docker compose ps event-bus-health-service
   
   # Check health endpoint
   curl http://localhost:8090/healthz
   
   # Check readiness endpoint
   curl http://localhost:8090/ready
   
   # Check comprehensive health
   curl http://localhost:8090/health
   
   # Check metrics endpoint
   curl http://localhost:8090/metrics
   
   # Check connection pool stats
   curl http://localhost:8090/stats
   ```

5. **Check Logs**:
   ```bash
   docker compose logs -f event-bus-health-service
   ```

### Kubernetes Deployment

#### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-bus-health-service
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: event-bus-health-service
  template:
    metadata:
      labels:
        app: event-bus-health-service
    spec:
      containers:
      - name: event-bus-health
        image: hub-event-bus-health:latest
        ports:
        - containerPort: 8090
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        - name: EVENT_BUS_REDIS_POOL_SIZE
          value: "50"
        - name: EVENT_BUS_REDIS_MAX_CONNECTIONS
          value: "100"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8090
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8090
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
---
apiVersion: v1
kind: Service
metadata:
  name: event-bus-health-service
spec:
  selector:
    app: event-bus-health-service
  ports:
  - port: 8090
    targetPort: 8090
  type: ClusterIP
```

### Configuration

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `EVENT_BUS_REDIS_POOL_SIZE` | `50` | Initial connection pool size |
| `EVENT_BUS_REDIS_MAX_CONNECTIONS` | `100` | Maximum connections in pool |
| `EVENT_BUS_REDIS_SOCKET_TIMEOUT` | `5` | Socket timeout in seconds |
| `EVENT_BUS_REDIS_SOCKET_CONNECT_TIMEOUT` | `5` | Connection timeout in seconds |
| `EVENT_BUS_REDIS_RETRY_ON_TIMEOUT` | `true` | Retry on timeout |
| `EVENT_BUS_REDIS_HEALTH_CHECK_INTERVAL` | `30` | Health check interval in seconds |
| `EVENT_BUS_CHANNEL_PREFIX` | `events` | Redis channel prefix |
| `EVENT_BUS_ENABLE_PERSISTENCE` | `true` | Enable PostgreSQL persistence |
| `EVENT_BUS_MAX_RETRIES` | `3` | Maximum retry attempts |
| `EVENT_BUS_HEALTH_PORT` | `8090` | Health service port |
| `DATABASE_URL` | - | PostgreSQL connection URL |

#### Redis Configuration

Redis is configured in `docker-compose.yml` with:

```yaml
redis:
  command: >
    redis-server
    --appendonly yes
    --maxmemory ${REDIS_MAX_MEMORY:-2gb}
    --maxmemory-policy ${REDIS_MAXMEMORY_POLICY:-allkeys-lru}
```

### Health Checks

#### Liveness Probe (`/healthz`)

Returns 200 OK if the process is running:

```bash
curl http://localhost:8090/healthz
```

#### Readiness Probe (`/ready`)

Returns 200 OK if dependencies (Redis, database) are available:

```bash
curl http://localhost:8090/ready
```

Response:
```json
{
  "status": "ready",
  "redis": {
    "connected": true,
    "latency_ms": 1.2
  },
  "database": {
    "connected": true
  }
}
```

#### Comprehensive Health Check (`/health`)

Returns detailed health status:

```bash
curl http://localhost:8090/health
```

Response:
```json
{
  "status": "healthy",
  "service": "event-bus-health-service",
  "timestamp": 1234567890.123,
  "redis": {
    "connected": true,
    "latency_ms": 1.2,
    "pool_stats": {
      "created_connections": 50,
      "available_connections": 45,
      "in_use_connections": 5,
      "max_connections": 100
    }
  },
  "database": {
    "connected": true
  }
}
```

#### Connection Pool Statistics (`/stats`)

Returns connection pool statistics:

```bash
curl http://localhost:8090/stats
```

Response:
```json
{
  "created_connections": 50,
  "available_connections": 45,
  "in_use_connections": 5,
  "max_connections": 100,
  "connection_utilization": 5.0
}
```

### Monitoring

#### Prometheus Metrics

The service exposes Prometheus metrics at `/metrics`:

- `event_published_total` - Total events published
- `event_publish_failed_total` - Total publish failures
- `event_consumed_total` - Total events consumed
- `event_consume_failed_total` - Total consume failures
- `event_publish_duration_seconds` - Publish latency histogram
- `event_processing_duration_seconds` - Processing latency histogram
- `event_dlq_size` - Dead letter queue size (gauge)
- `event_bus_redis_connection_errors_total` - Redis connection errors
- `event_bus_redis_pool_utilization_percent` - Connection pool utilization

#### Grafana Dashboard

Import the event bus dashboard:

```bash
# Dashboard file: monitoring/grafana/dashboards/event-bus-health.json
```

### Troubleshooting

#### Connection Pool Exhausted

**Symptoms**: `ConnectionPoolExhausted` errors, high connection pool utilization

**Diagnosis**:
```bash
# Check connection pool stats
curl http://localhost:8090/stats

# Check health endpoint
curl http://localhost:8090/health | jq '.redis.pool_stats'
```

**Solutions**:
1. Increase max connections:
   ```bash
   export EVENT_BUS_REDIS_MAX_CONNECTIONS=200
   docker compose restart event-bus-health-service
   ```

2. Check for connection leaks:
   ```python
   from services.event_bus.client import get_event_bus_client
   client = get_event_bus_client()
   stats = client.get_connection_pool_stats()
   print(f"In-use connections: {stats['in_use_connections']}")
   ```

3. Monitor connection pool metrics:
   ```bash
   curl http://localhost:8090/metrics | grep event_bus_redis_pool
   ```

#### Redis Connection Failures

**Symptoms**: Health checks fail, events not publishing

**Diagnosis**:
```bash
# Check Redis health
curl http://localhost:8090/health | jq '.redis'

# Check Redis directly
docker compose exec redis redis-cli ping

# Check Redis logs
docker compose logs redis
```

**Solutions**:
1. Verify Redis is running:
   ```bash
   docker compose ps redis
   ```

2. Check Redis configuration:
   ```bash
   docker compose exec redis redis-cli CONFIG GET "*"
   ```

3. Verify Redis URL:
   ```bash
   docker compose exec event-bus-health-service env | grep REDIS_URL
   ```

4. Test Redis connectivity:
   ```bash
   docker compose exec event-bus-health-service python -c "
   import redis
   r = redis.from_url('redis://redis:6379/0')
   print(r.ping())
   "
   ```

#### High Latency

**Symptoms**: Slow event publishing/consumption

**Diagnosis**:
```bash
# Check Redis latency
curl http://localhost:8090/health | jq '.redis.latency_ms'

# Check event publish latency metrics
curl http://localhost:8090/metrics | grep event_publish_duration_seconds
```

**Solutions**:
1. Optimize Redis configuration:
   ```yaml
   redis:
     command: >
       redis-server
       --appendonly yes
       --maxmemory 4gb
       --maxmemory-policy allkeys-lru
   ```

2. Increase connection pool size:
   ```bash
   export EVENT_BUS_REDIS_POOL_SIZE=100
   export EVENT_BUS_REDIS_MAX_CONNECTIONS=200
   ```

3. Check network latency:
   ```bash
   docker compose exec event-bus-health-service ping redis
   ```

4. Monitor Redis performance:
   ```bash
   docker compose exec redis redis-cli --latency
   ```

#### Dead Letter Queue Growth

**Symptoms**: DLQ size increasing, events not being consumed

**Diagnosis**:
```bash
# Check DLQ size
curl http://localhost:8090/metrics | grep event_dlq_size

# Query DLQ events
python manage.py shell
>>> from hub.apps.core.events.models import DeadLetterQueue
>>> DeadLetterQueue.objects.count()
```

**Solutions**:
1. Review DLQ events:
   ```python
   from hub.apps.core.events.models import DeadLetterQueue
   events = DeadLetterQueue.objects.all()[:10]
   for event in events:
       print(f"Event: {event.event_type}, Error: {event.error_message}")
   ```

2. Replay DLQ events:
   ```python
   from hub.apps.core.events.bus import get_event_bus
   bus = get_event_bus()
   bus.replay_dlq_events(event_type="contract.created", limit=10)
   ```

3. Fix root cause:
   - Review error messages in DLQ
   - Fix subscriber handlers
   - Update event schemas if needed

---

## Service Layer Deployment

### Overview

The service layer provides core business logic services with standardized communication patterns, service discovery, and health checks.

**Key Components:**
- Service Discovery: Centralized service URL resolution
- Service-to-Service Communication: Standardized HTTP client
- Health Checks: Service health monitoring
- Configuration Management: Environment-based configuration

### Service Discovery

#### Docker Compose

Services are accessible via Docker DNS service names:

```python
from hub.apps.core.services.discovery import get_service_url

# Get service URL
url = get_service_url("api-service")
# Returns: "http://api-service:8000"
```

#### Kubernetes

Services are accessible via Kubernetes DNS:

```python
from hub.apps.core.services.discovery import get_service_url

# Get service URL
url = get_service_url("api-service", namespace="default")
# Returns: "http://api-service.default.svc.cluster.local:8000"
```

### Service-to-Service Communication

#### Using ServiceClient

```python
from hub.apps.core.services.cross_service_access import ServiceClient

# Create client
client = ServiceClient("api-service")

# Make GET request
data = client.get("/api/v1/contracts/123", tenant_id="tenant-uuid")

# Make POST request
result = client.post("/api/v1/contracts", data={"name": "..."}, tenant_id="tenant-uuid")
```

#### Features

- Automatic retry with exponential backoff
- Tenant isolation (automatic `X-Tenant-Id` header)
- OpenTelemetry tracing integration
- Error handling (converts HTTP errors to `ServiceError`)
- Configurable timeouts

### Health Checks

#### Check Single Service

```python
from hub.apps.core.services.health import check_service_health

result = check_service_health("api-service")
# Returns: {"status": "healthy", "latency_ms": 10.5, ...}
```

#### Monitor All Services

```python
from hub.apps.core.services.health import ServiceHealthMonitor

monitor = ServiceHealthMonitor()
results = monitor.check_all_services()
healthy_services = monitor.get_healthy_services()
unhealthy_services = monitor.get_unhealthy_services()
```

### Configuration

#### Environment Variables

Configure service URLs via environment variables:

```bash
# Docker Compose
API_SERVICE_URL=http://api-service:8000
CONTRACT_SERVICE_URL=http://contract-service:8001

# Kubernetes
API_SERVICE_URL=http://api-service.default.svc.cluster.local:8000
```

#### Django Settings

Service URLs can also be configured in Django settings:

```python
# settings.py
API_SERVICE_URL = env('API_SERVICE_URL', default='http://api-service:8000')
CONTRACT_SERVICE_URL = env('CONTRACT_SERVICE_URL', default='http://contract-service:8001')
```

### Docker Compose Configuration

```yaml
services:
  api-service:
    ports:
      - "8000:8000"
    environment:
      - CONTRACT_SERVICE_URL=http://contract-service:8001
      - ASSET_SERVICE_URL=http://asset-service:8002
    networks:
      - hub-net
```

### Kubernetes Configuration

```yaml
env:
  - name: API_SERVICE_URL
    value: "http://api-service.default.svc.cluster.local:8000"
  - name: CONTRACT_SERVICE_URL
    value: "http://contract-service.default.svc.cluster.local:8001"
```

### Troubleshooting

#### Service Not Found

**Symptoms**: `ServiceNotFoundError` or URL resolution fails

**Solutions**:
1. Check service is registered:
   ```python
   from hub.apps.core.services.discovery import ServiceRegistry
   config = ServiceRegistry.get_service_config("api-service")
   print(config)
   ```

2. Check environment variable:
   ```bash
   docker compose exec api-service env | grep API_SERVICE_URL
   ```

3. Verify Docker network:
   ```bash
   docker network inspect hub-net
   ```

4. Check Kubernetes service:
   ```bash
   kubectl get svc api-service
   ```

#### Health Check Failures

**Symptoms**: Health checks return "unhealthy"

**Solutions**:
1. Verify service is running:
   ```bash
   docker compose ps api-service
   # or
   kubectl get pods -l app=api-service
   ```

2. Check health endpoint:
   ```bash
   curl http://api-service:8000/health
   ```

3. Check network connectivity:
   ```bash
   docker compose exec api-service ping contract-service
   ```

4. Review service logs:
   ```bash
   docker compose logs api-service
   # or
   kubectl logs -l app=api-service
   ```

#### Service Communication Failures

**Symptoms**: Service-to-service calls fail

**Solutions**:
1. Check service URLs:
   ```python
   from hub.apps.core.services.discovery import get_service_url
   url = get_service_url("api-service")
   print(url)
   ```

2. Verify network connectivity:
   ```bash
   docker compose exec api-service curl http://contract-service:8001/health
   ```

3. Check firewall rules:
   - Ensure ports are open
   - Verify network policies (Kubernetes)

4. Verify tenant context:
   ```python
   # Ensure X-Tenant-Id header is set
   client = ServiceClient("api-service")
   result = client.get("/api/v1/contracts/123", tenant_id="tenant-uuid")
   ```

---

## Service Configuration

### Common Configuration Patterns

#### Environment-Based Configuration

All services support environment-based configuration:

```bash
# Development
export ENVIRONMENT=development
export DEBUG=True
export LOG_LEVEL=DEBUG

# Staging
export ENVIRONMENT=staging
export DEBUG=False
export LOG_LEVEL=INFO

# Production
export ENVIRONMENT=production
export DEBUG=False
export LOG_LEVEL=WARNING
```

#### Database Configuration

```bash
# PostgreSQL connection
export DATABASE_URL=postgresql://user:password@host:5432/database
export POSTGRES_HOST=postgres
export POSTGRES_PORT=5432
export POSTGRES_USER=hub
export POSTGRES_PASSWORD=hub
export POSTGRES_DB=hub
```

#### Redis Configuration

```bash
# Redis connection
export REDIS_URL=redis://host:6379/0
export REDIS_HOST=redis
export REDIS_PORT=6379
export REDIS_MAX_MEMORY=2gb
export REDIS_MAXMEMORY_POLICY=allkeys-lru
```

#### OpenTelemetry Configuration

```bash
# Enable tracing and metrics
export OPENTELEMETRY_ENABLED=true
export OPENTELEMETRY_METRICS_ENABLED=true
export JAEGER_AGENT_HOST=jaeger
export JAEGER_AGENT_PORT=6831
export ENVIRONMENT=production
export APP_VERSION=1.0.0
```

### Service-Specific Configuration

#### Workflow Engine Service

```bash
export WORKFLOW_ENGINE_HEALTH_PORT=8088
export WORKFLOW_ENGINE_POLL_INTERVAL=5
export WORKFLOW_ENGINE_BATCH_SIZE=10
```

#### Event Bus Service

```bash
export EVENT_BUS_REDIS_POOL_SIZE=50
export EVENT_BUS_REDIS_MAX_CONNECTIONS=100
export EVENT_BUS_REDIS_SOCKET_TIMEOUT=5
export EVENT_BUS_CHANNEL_PREFIX=events
export EVENT_BUS_ENABLE_PERSISTENCE=true
export EVENT_BUS_MAX_RETRIES=3
export EVENT_BUS_HEALTH_PORT=8090
```

### Configuration Files

#### Docker Compose Environment Files

Create `.env.dev`, `.env.staging`, `.env.production` files:

```bash
# .env.dev
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://hub:hub@postgres:5432/hub
REDIS_URL=redis://redis:6379/0
```

#### Kubernetes ConfigMaps

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: service-config
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  WORKFLOW_ENGINE_POLL_INTERVAL: "5"
  WORKFLOW_ENGINE_BATCH_SIZE: "10"
```

#### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: database-secret
type: Opaque
stringData:
  url: "postgresql://hub:hub@postgres:5432/hub"
  password: "secure-password"
```

---

## Service Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Symptoms**: Container exits immediately, health checks fail

**Diagnosis Steps**:
1. Check container logs:
   ```bash
   docker compose logs service-name
   # or
   kubectl logs pod-name
   ```

2. Check health endpoints:
   ```bash
   curl http://localhost:PORT/healthz
   curl http://localhost:PORT/ready
   ```

3. Verify dependencies:
   ```bash
   docker compose ps postgres redis
   # or
   kubectl get pods -l app=postgres
   ```

**Common Causes**:
- Database connection failure
- Redis connection failure
- Missing environment variables
- Port conflicts
- Insufficient resources

**Solutions**:
- Verify database/Redis are running and healthy
- Check environment variables are set correctly
- Verify ports are not in use
- Check resource limits (memory, CPU)

#### 2. Service Health Checks Failing

**Symptoms**: Health checks return unhealthy, service appears down

**Diagnosis Steps**:
1. Check health endpoint directly:
   ```bash
   curl -v http://service-name:port/health
   ```

2. Check dependency health:
   ```bash
   curl http://service-name:port/ready
   ```

3. Review service logs:
   ```bash
   docker compose logs -f service-name
   ```

**Common Causes**:
- Database connection issues
- Redis connection issues
- Service initialization failures
- Resource exhaustion

**Solutions**:
- Verify database/Redis connectivity
- Check service initialization logs
- Review resource usage (memory, CPU)
- Verify service dependencies are healthy

#### 3. Service Communication Failures

**Symptoms**: Service-to-service calls fail, timeouts, connection errors

**Diagnosis Steps**:
1. Test service connectivity:
   ```bash
   docker compose exec service1 curl http://service2:port/health
   ```

2. Check service URLs:
   ```python
   from hub.apps.core.services.discovery import get_service_url
   url = get_service_url("service-name")
   print(url)
   ```

3. Review service logs:
   ```bash
   docker compose logs service-name | grep -i error
   ```

**Common Causes**:
- Network connectivity issues
- Service not running
- Incorrect service URLs
- Firewall/network policies blocking traffic

**Solutions**:
- Verify services are on same network
- Check service URLs are correct
- Verify services are running
- Review network policies (Kubernetes)

#### 4. High Latency

**Symptoms**: Slow response times, timeouts

**Diagnosis Steps**:
1. Check service metrics:
   ```bash
   curl http://service-name:port/metrics | grep duration
   ```

2. Check database performance:
   ```sql
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   ```

3. Check Redis latency:
   ```bash
   docker compose exec redis redis-cli --latency
   ```

**Common Causes**:
- Database query performance issues
- Redis latency
- Network latency
- Resource constraints

**Solutions**:
- Optimize database queries
- Add database indexes
- Increase connection pool sizes
- Scale services horizontally
- Optimize Redis configuration

#### 5. Memory/CPU Issues

**Symptoms**: OOM kills, high CPU usage, slow performance

**Diagnosis Steps**:
1. Check resource usage:
   ```bash
   docker stats service-name
   # or
   kubectl top pod service-name
   ```

2. Check service metrics:
   ```bash
   curl http://service-name:port/metrics | grep memory
   ```

3. Review service logs for OOM errors:
   ```bash
   docker compose logs service-name | grep -i oom
   ```

**Common Causes**:
- Memory leaks
- Insufficient resource limits
- High load
- Inefficient code

**Solutions**:
- Increase resource limits
- Optimize memory usage
- Scale services horizontally
- Review code for memory leaks
- Use connection pooling

### Diagnostic Commands

#### Check Service Status

```bash
# Docker Compose
docker compose ps
docker compose ps service-name

# Kubernetes
kubectl get pods
kubectl get pods -l app=service-name
```

#### Check Service Logs

```bash
# Docker Compose
docker compose logs service-name
docker compose logs -f service-name
docker compose logs --tail=100 service-name

# Kubernetes
kubectl logs pod-name
kubectl logs -f pod-name
kubectl logs --tail=100 pod-name
```

#### Check Service Health

```bash
# Health endpoints
curl http://localhost:PORT/healthz
curl http://localhost:PORT/ready
curl http://localhost:PORT/health
curl http://localhost:PORT/metrics
```

#### Check Network Connectivity

```bash
# Docker Compose
docker compose exec service1 ping service2
docker compose exec service1 curl http://service2:port/health

# Kubernetes
kubectl exec pod-name -- ping service-name
kubectl exec pod-name -- curl http://service-name:port/health
```

#### Check Database Connectivity

```bash
# PostgreSQL
docker compose exec postgres pg_isready -U hub
docker compose exec service-name python -c "
import os
import psycopg2
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
print('Connected')
"

# Kubernetes
kubectl exec pod-name -- pg_isready -U hub
```

#### Check Redis Connectivity

```bash
# Redis
docker compose exec redis redis-cli ping
docker compose exec service-name python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
print(r.ping())
"

# Kubernetes
kubectl exec pod-name -- redis-cli ping
```

### Escalation Procedures

#### Level 1: Service Restart

```bash
# Docker Compose
docker compose restart service-name

# Kubernetes
kubectl rollout restart deployment/service-name
```

#### Level 2: Service Recreate

```bash
# Docker Compose
docker compose up -d --force-recreate service-name

# Kubernetes
kubectl delete pod pod-name
# Pod will be recreated automatically
```

#### Level 3: Full Service Redeployment

```bash
# Docker Compose
docker compose down service-name
docker compose up -d service-name

# Kubernetes
kubectl delete deployment service-name
kubectl apply -f deployment.yaml
```

#### Level 4: Infrastructure Check

```bash
# Check all infrastructure services
docker compose ps
docker compose logs

# Check Kubernetes cluster
kubectl get nodes
kubectl get pods --all-namespaces
kubectl get events --sort-by='.lastTimestamp'
```

### Best Practices

1. **Always Check Logs First**: Logs provide the most detailed information
2. **Verify Dependencies**: Ensure all dependencies are healthy before troubleshooting
3. **Use Health Endpoints**: Health endpoints provide quick status checks
4. **Monitor Metrics**: Use Prometheus metrics for performance analysis
5. **Test Connectivity**: Verify network connectivity between services
6. **Review Configuration**: Check environment variables and configuration files
7. **Scale Gradually**: Start with restart, then recreate, then redeploy
8. **Document Issues**: Keep track of issues and solutions for future reference

---

## Related Documentation

- [Docker Compose Deployment](./DOCKER_COMPOSE_DEPLOYMENT.md)
- [Kubernetes Deployment](./KUBERNETES_DEPLOYMENT.md)
- [Service Layer Deployment](./SERVICE_LAYER_DEPLOYMENT.md)
- [Workflow Monitoring Setup](./WORKFLOW_MONITORING_SETUP.md)
- [Event Bus Monitoring](./EVENT_BUS_MONITORING.md)
- [Service Layer Monitoring](./SERVICE_LAYER_MONITORING.md)
- [Deployment Scripts](./DEPLOYMENT_SCRIPTS.md)
- [Health Check Scripts](./HEALTH_CHECK_SCRIPTS.md)
- [Monitoring Scripts](./MONITORING_SCRIPTS.md)


---

# Operations Runbook

Production operational procedures for Meshant (DataInteroperabilityHub).

**Related runbooks**: [Prefect Integration Runbook](ops/prefect-runbook.md) | [Capability Degradation Guide](capability-degradation.md) | [Operator Setup Checklist](operator-external-setup-checklist.md)

---

## Rotating ENCRYPTION_KEY

The `ENCRYPTION_KEY` is used by Fernet symmetric encryption for all credential
fields at rest (9 fields across 7 apps — see `docs/SECURITY_AND_COMPLIANCE.md`
§ "Credentials Encrypted at Rest"). Rotation re-encrypts all encrypted data
under a new key.

**Affected data**: webhook secrets (`v1:` prefix), integration credentials,
scheduled ingestion/export configs, SSO config, DQ alerting channel config,
virtualization sources, transformation pipeline definitions, and node configs
(all stored as `{"_encrypted": "..."}`).

### Steps

1. **Generate new key**:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Back up the current key** — store `$OLD_KEY` securely (you need it for step 3):
   ```bash
   echo $ENCRYPTION_KEY  # save this value
   ```

3. **Rotate webhook secrets** (dry run first):
   ```bash
   python manage.py rotate_webhook_encryption_key \
     --old-key=$OLD_KEY --new-key=$NEW_KEY --dry-run
   python manage.py rotate_webhook_encryption_key \
     --old-key=$OLD_KEY --new-key=$NEW_KEY
   ```

4. **Re-encrypt JSONField credentials** — roll back each data migration
   (decrypts with old key), then switch to new key and re-apply (encrypts
   with new key):
   ```bash
   # Step 4a: roll back with OLD key still active (decrypts to plaintext)
   export ENCRYPTION_KEY=$OLD_KEY
   python manage.py migrate scheduled_ingestion 0008
   python manage.py migrate scheduled_export 0004
   python manage.py migrate tenants 0020
   python manage.py migrate dq 0004
   python manage.py migrate virtualization 0005
   python manage.py migrate transformation 0001

   # Step 4b: re-apply with NEW key (encrypts from plaintext)
   export ENCRYPTION_KEY=$NEW_KEY
   python manage.py migrate scheduled_ingestion
   python manage.py migrate scheduled_export
   python manage.py migrate tenants
   python manage.py migrate dq
   python manage.py migrate virtualization
   python manage.py migrate transformation
   ```

5. **Deploy new key** to environment:
   - AWS Secrets Manager: `aws secretsmanager update-secret --secret-id hub/production/django --secret-string '{"ENCRYPTION_KEY":"'$NEW_KEY'"}'`
   - Or update `.env.production` and redeploy

6. **Verify** webhooks and encrypted fields work correctly:
   ```bash
   curl -X POST https://$DOMAIN/api/v1/webhooks/$ID/test/
   # Spot-check an API response that returns a decrypted field:
   curl https://$DOMAIN/api/v1/scheduled-ingestion/ -H "Authorization: Bearer $TOKEN" | jq '.[0].source_config'
   ```

7. **Remove old key** from AWS Secrets Manager (after confirming all services work).

---

## PgBouncer Constraints

PgBouncer `pool_mode=transaction` is incompatible with session-scoped
PostgreSQL features. See `docs/ops/pgbouncer-constraints.md` for full details.

### Incompatible Features

| Feature | Why it breaks | Alternative |
|---------|--------------|-------------|
| `pg_advisory_lock()` | Lock released on connection return | Redis `SETNX` / `redis.lock()` |
| `pg_advisory_xact_lock()` | May be held by wrong client | Redis `SETNX` / `redis.lock()` |
| `LISTEN/NOTIFY` | Notifications go to wrong client | Redis Pub/Sub (`channels_redis`) |
| Named cursors | Cursor lost on connection return | Django pagination / `iterator()` |

### Automated Guard

```bash
pytest hub/tests/test_advisory_lock_not_used.py -v
```

This static scan fails if any production code uses `pg_advisory_lock`.

### Redis Lock Alternative

```python
from django_rq import get_connection

r = get_connection()
lock = r.lock("my-resource-lock", timeout=30)
if lock.acquire(blocking=False):
    try:
        # critical section
        pass
    finally:
        lock.release()
```

### PgBouncer Pool Stats

```bash
# Connect to PgBouncer admin console
psql -p 6432 -U pgbouncer pgbouncer -c "SHOW POOLS;"
psql -p 6432 -U pgbouncer pgbouncer -c "SHOW STATS;"
```

Key metrics: `cl_active` (client connections in use), `sv_active` (server connections in use),
`sv_idle` (available server connections). Alert threshold: `sv_active >= default_pool_size`.

---

## Database Backup / Restore

> **ENCRYPTION_KEY must be preserved alongside backups.** The database contains
> Fernet-encrypted credential fields (9 fields across 7 apps). If `ENCRYPTION_KEY`
> is lost or rotated without re-encrypting, all encrypted fields become
> **unrecoverable** after a restore. Store `ENCRYPTION_KEY` in AWS Secrets Manager
> and include it in your backup verification checklist.
> If using AWS KMS for field-level encryption, ensure the KMS key is not scheduled
> for deletion. <!-- Phase 211: replaced Vault Transit with AWS KMS -->

### Manual Backup

```bash
kubectl create job --from=cronjob/backup manual-backup-$(date +%Y%m%d)
```

### Verify Backup

```bash
aws s3 ls s3://$BACKUP_S3_BUCKET/postgres/ --recursive | sort | tail -5
```

### Restore Procedure

1. **Scale down** API and worker services:
   ```bash
   kubectl scale deploy hub-api --replicas=0
   kubectl scale deploy hub-worker --replicas=0
   ```

2. **Restore** from latest backup:
   ```bash
   pg_restore --clean --if-exists -d hub < backup.dump
   ```

3. **Run migrations**:
   ```bash
   python manage.py migrate --run-syncdb
   ```

4. **Scale up** services:
   ```bash
   kubectl scale deploy hub-api --replicas=2
   kubectl scale deploy hub-worker --replicas=2
   ```

### Fuseki Backup / Restore

Fuseki stores the semantic ontology graph in TDB2 format.

**Backup** (via CronJob):

```bash
kubectl create job --from=cronjob/backup-fuseki manual-fuseki-backup-$(date +%Y%m%d)
```

**Restore** from TDB2 snapshot:

```bash
# Stop Fuseki
kubectl scale deploy fuseki --replicas=0
# Copy snapshot to Fuseki data volume
kubectl cp fuseki-backup.tar.gz fuseki-0:/fuseki/databases/hub/
kubectl exec fuseki-0 -- tar xzf /fuseki/databases/hub/fuseki-backup.tar.gz -C /fuseki/databases/hub/
# Restart
kubectl scale deploy fuseki --replicas=1
```

Alert: `FusekiBackupFailed` fires on CronJob failure (Phase 29).

### Backup Retention

30-day lifecycle rule configured in Terraform (`infrastructure/terraform/s3/main.tf`).
Prometheus alert `BackupJobFailed` fires on CronJob failure (Phase 52.3).

---

## Checking Service Health

### API Health

```bash
curl -f https://$DOMAIN/api/health/
```

### Prometheus Targets

```bash
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

All targets should show `health: "up"`.

### Log Aggregation (Loki)

Query errors in the last hour:

```
{job="hub-api"} |= "ERROR" | last 1h
```

### AWS Secrets Manager Health

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->
```bash
aws secretsmanager list-secrets --region <region> --max-results 1
```

Expected: returns a JSON list without errors.
Alert: `SecretsManagerUnavailable` fires if ExternalSecret sync fails for 5 minutes.

### Redis Health

```bash
redis-cli -u $REDIS_CACHE_URL ping    # PONG
redis-cli -u $REDIS_QUEUE_URL ping    # PONG
redis-cli -u $REDIS_CHANNELS_URL ping # PONG
```

Alert: `HubRedisDown` fires after 1 minute of downtime.

### Fuseki Health

```bash
curl -f http://fuseki:3030/$/ping
```

Expected: HTTP 200. Alert: `SemanticFusekiDown` fires after 15 minutes (Phase 29).

---

# Monitoring & Observability

Complete guide for monitoring and observability in the Data Interoperability Hub.

## Overview

The platform provides comprehensive monitoring and observability:

- **Metrics**: Prometheus metrics collection
- **Logging**: Structured logging with correlation IDs
- **Tracing**: Distributed tracing with Jaeger
- **Dashboards**: Grafana dashboards for visualization
- **Alerts**: Alertmanager for alerting

## Metrics

### Prometheus

Prometheus collects metrics from all services:

- **URL**: http://localhost:9090
- **Metrics Endpoint**: `/metrics` on each service

### Key Metrics

#### API Service Metrics

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration
- `http_requests_errors_total` - Error count
- `django_db_queries_total` - Database queries
- `django_cache_hits_total` - Cache hits

#### Worker Service Metrics

- `rq_jobs_total` - Total jobs processed
- `rq_jobs_duration_seconds` - Job duration
- `rq_jobs_failed_total` - Failed jobs
- `rq_queue_length` - Queue length

#### Database Metrics

- `postgres_connections` - Active connections
- `postgres_queries_total` - Query count
- `postgres_slow_queries_total` - Slow queries

### Accessing Metrics

```bash
# Prometheus UI
open http://localhost:9090

# Query metrics
curl http://localhost:9090/api/v1/query?query=http_requests_total

# Service metrics
curl http://localhost:8000/metrics
curl http://localhost:8080/metrics
```

## Logging

### Structured Logging

All services use structured logging with correlation IDs:

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    'Contract created',
    contract_id=contract.id,
    tenant_id=tenant.id,
    user_id=user.id,
    correlation_id=request.correlation_id
)
```

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical errors

### Viewing Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs api-service

# Follow logs
docker compose logs -f api-service

# Filter logs
docker compose logs api-service | grep ERROR
```

### Log Aggregation

Logs are aggregated and can be exported to:
- **ELK Stack** (optional)
- **Loki** (optional)
- **CloudWatch** (production)

## Tracing

### Jaeger

Distributed tracing with Jaeger:

- **UI**: http://localhost:16686
- **HTTP Collector**: http://localhost:14268
- **UDP Collector**: localhost:6831

### Tracing Requests

Tracing is automatically enabled for:
- HTTP requests
- Database queries
- External service calls
- Background jobs

### Viewing Traces

```bash
# Open Jaeger UI
open http://localhost:16686

# Search traces
# - Service: api-service
# - Operation: GET /api/v1/contracts/
# - Tags: error=true
```

### W3C Trace Context and service coverage

All request-handling services (api-service, API Gateway, FastAPI microservices) **SHOULD** use [W3C Trace Context](https://www.w3.org/TR/trace-context/) (`traceparent`, `tracestate` headers) and export spans to the same backend (Jaeger or OTLP) so that traces are continuous across the stack.

| Service | W3C trace context / export to same backend | Notes |
|--------|--------------------------------------------|-------|
| **api-service** (Django) | **Yes** | `TraceIDMiddleware` and `SpanMiddleware` extract/emit traceparent; OpenTelemetry via `hub.apps.observability.otel_config` (Django + HTTPX instrumentation). Exports to Jaeger or OTLP per `OPENTELEMETRY_EXPORTER`. |
| **API Gateway** (FastAPI) | **Yes** | `shared.tracing.setup_opentelemetry_fastapi`; FastAPI and HTTPX instrumentation; Jaeger exporter. Propagates W3C headers on forwarded requests. |
| **semantic-service** (FastAPI) | **Yes** | `shared.tracing.setup_opentelemetry_fastapi`; FastAPI and HTTPX instrumentation; Jaeger exporter. |
| **dq-service** (FastAPI) | **Not yet** | No OpenTelemetry instrumentation. To align: add `shared.tracing.setup_opentelemetry_fastapi` and instrument the app. |
| **compliance-service** (FastAPI) | **Not yet** | No OpenTelemetry instrumentation. To align: add `shared.tracing.setup_opentelemetry_fastapi` and instrument the app. |
| **webhook-service** (FastAPI) | **Not yet** | OpenTelemetry deps present but not wired in main. To align: add `shared.tracing.setup_opentelemetry_fastapi` and instrument the app. |

Gateway and api-service both use W3C trace context: Django uses `hub.apps.api.middleware.tracing` (traceparent) and `get_trace_headers()` for outbound calls; OpenTelemetry SDK uses W3C by default. For full propagation details, see `infrastructure/tracing/README.md`.

## Dashboards

### Grafana

Grafana provides visualization dashboards:

- **URL**: http://localhost:3000
- **Default Credentials**: admin/admin

### Available Dashboards

1. **API Service Dashboard**
   - Request rate
   - Error rate
   - Response time
   - Database queries

2. **Worker Service Dashboard**
   - Job processing rate
   - Job duration
   - Queue length
   - Failed jobs

3. **Database Dashboard**
   - Connection count
   - Query rate
   - Slow queries
   - Database size

4. **System Dashboard**
   - CPU usage
   - Memory usage
   - Disk usage
   - Network traffic

### Creating Custom Dashboards

1. Open Grafana UI
2. Create new dashboard
3. Add panels with Prometheus queries
4. Save dashboard

## Alerts

### Alertmanager

Alertmanager manages alerts:

- **URL**: http://localhost:9093
- **Configuration**: `monitoring/alertmanager/alertmanager.yml`

### Alert Rules

Alert rules are defined in `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High error rate detected"
```

### Common Alerts

- **High Error Rate**: API error rate > 10%
- **Slow Response Time**: P95 response time > 1s
- **Database Connection Pool Exhausted**: Connection pool > 80%
- **Queue Backlog**: Queue length > 1000
- **Service Down**: Service health check failed

### Alert Notifications

Alerts can be sent to:
- **Email**: SMTP configuration
- **Slack**: Webhook integration
- **PagerDuty**: API integration
- **Custom Webhooks**: HTTP endpoints

### Observability Stack Configuration (Phase 120D)

#### OpenTelemetry Collector

The OTel Collector receives telemetry from all services and exports to backends:

- **Receivers**: OTLP (gRPC :4317, HTTP :4318), Prometheus scrape
- **Processors**: Batch (200ms/5000 items), tail-based sampling (error=100%, success=10%), attributes (add `environment`, `service.version`)
- **Exporters**: Prometheus (metrics → :8889), OTLP/Tempo (traces), Loki (logs)

#### Tempo (Distributed Tracing)

- **Backend**: S3-compatible storage (MinIO in staging, S3 in production)
- **Retention**: 14 days
- **Search**: Tag-based search on `service.name`, `http.status_code`, `error`
- **Integration**: Grafana Tempo data source with TraceQL support

#### Loki (Log Aggregation)

- **Backend**: S3-compatible storage
- **Retention**: 30 days
- **Ingestion**: Promtail DaemonSet reading Docker socket (`/var/run/docker.sock`)
- **Parsing**: JSON structured logs with `tenant_id`, `request_id`, `user_id` labels

#### Promtail

- **Source**: Docker container logs via socket mount
- **Pipeline**: JSON parsing → label extraction (`level`, `logger`, `tenant_id`) → timestamp extraction
- **Filtering**: Drop health check logs (`GET /api/health/`)

#### Alert Rules

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `HighErrorRate` | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05` | critical | 5m |
| `HighP95Latency` | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2` | warning | 10m |
| `QueueDepthHigh` | `rq_jobs_total{status="queued"} > 500` | warning | 5m |
| `WorkerSlotsExhausted` | `rq_workers_total{state="busy"} / rq_workers_total > 0.95` | critical | 3m |
| `CircuitBreakerOpen` | `circuit_breaker_state{service_name="stripe-billing"} == 2` | critical | 1m |

## Health Checks

### Service Health Endpoints

All services expose health check endpoints:

```bash
# API Service
curl http://localhost:8000/health

# Worker Service
curl http://localhost:8080/healthz

# Workflow Engine
curl http://localhost:8088/healthz

# Microservices
curl http://localhost:8081/health  # Semantic
curl http://localhost:8082/health  # Compliance
curl http://localhost:8083/health  # DQ
```

### Health Check Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-15T10:30:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "minio": "healthy"
  }
}
```

## Observability Service

The Observability Service provides data observability:

- **URL**: http://localhost:8086
- **Metrics**: Data freshness, lineage, quality

### Features

- **Data Freshness**: Track data update frequency
- **Lineage Tracking**: Track data lineage
- **Quality Metrics**: Track data quality trends

## BaaS Platform Metrics

### API Gateway Metrics

The API Gateway (`services/api-gateway/`) exposes metrics for rate limiting and request routing:

- `api_gateway_requests_total` - Total API requests
- `api_gateway_request_duration_seconds` - Request duration
- `api_gateway_rate_limit_exceeded_total` - Rate limit violations
- `api_gateway_api_key_validations_total` - API key validations
- `api_gateway_tier_requests_total{ tier="FREE|PRO|ENTERPRISE" }` - Requests by tier

### Usage Tracking Metrics

The UsageTrackingService exposes metrics for API usage:

- `baas_usage_requests_total` - Total tracked requests
- `baas_usage_requests_by_endpoint_total{ endpoint="/api/v1/assets/" }` - Requests by endpoint
- `baas_usage_requests_by_tier_total{ tier="FREE|PRO|ENTERPRISE" }` - Requests by tier
- `baas_usage_quota_remaining{ tier="FREE|PRO|ENTERPRISE" }` - Remaining quota
- `baas_usage_response_time_seconds` - Response time histogram

### Grafana Dashboard

**BaaS Platform Dashboard** (`grafana/dashboards/baas-platform.json`):

- **API Gateway Overview**: Request rate, error rate, rate limit violations
- **Usage by Tier**: Requests, quota usage, quota remaining per tier
- **Usage by Endpoint**: Top endpoints by request count and response time
- **API Key Management**: API key creation, revocation, expiration

**Key Panels**:
- API Gateway Request Rate (requests/second)
- Rate Limit Violations by Tier
- Quota Usage Percentage by Tier
- Top 10 Endpoints by Request Count
- Average Response Time by Endpoint

### Alert Definitions

**BaaS Platform Alerts**:

```yaml
# Rate limit violations
- alert: BaaSRateLimitViolationsHigh
  expr: rate(api_gateway_rate_limit_exceeded_total[5m]) > 10
  for: 5m
  annotations:
    summary: "High rate limit violations detected"

# Quota exhaustion
- alert: BaaSQuotaExhausted
  expr: baas_usage_quota_remaining < 100
  for: 1m
  annotations:
    summary: "API quota nearly exhausted for tier"

# API key validation failures
- alert: BaaSAPIKeyValidationFailures
  expr: rate(api_gateway_api_key_validations_total{status="failed"}[5m]) > 5
  for: 5m
  annotations:
    summary: "High API key validation failure rate"
```

### Monitoring Best Practices

1. **Track Quota Usage**: Monitor quota remaining to prevent service disruption
2. **Monitor Rate Limits**: Track rate limit violations to identify abuse or scaling needs
3. **Endpoint Performance**: Monitor response times by endpoint to identify slow endpoints
4. **Tier Distribution**: Track request distribution across tiers for capacity planning

## ODH Integration Metrics

### Model Registry Metrics

The ModelRegistryBridgeService exposes metrics for model operations:

- `odh_models_total` - Total ML models
- `odh_models_by_status_total{ status="TRAINING|TRAINED|DEPLOYED|FAILED" }` - Models by status
- `odh_models_by_type_total{ type="CLASSIFICATION|REGRESSION|..." }` - Models by type
- `odh_model_operations_total{ operation="create|update|delete" }` - Model operations
- `odh_model_sync_duration_seconds` - Model sync duration

### Training Pipeline Metrics

The ModelTrainingWorkflow exposes metrics for training operations:

- `odh_training_jobs_total` - Total training jobs
- `odh_training_jobs_by_status_total{ status="RUNNING|COMPLETED|FAILED" }` - Jobs by status
- `odh_training_job_duration_seconds` - Training job duration
- `odh_training_job_failures_total` - Failed training jobs
- `odh_training_dataset_validation_duration_seconds` - Dataset validation duration

### Inference Service Metrics

The InferenceValidationService exposes metrics for inference operations:

- `odh_inference_predictions_total` - Total predictions
- `odh_inference_latency_seconds` - Inference latency histogram
- `odh_inference_errors_total` - Inference errors
- `odh_inference_validation_failures_total` - Input/output validation failures
- `odh_inference_data_drift_score` - Data drift score gauge

### Grafana Dashboard

**ODH Integration Dashboard** (`grafana/dashboards/odh-integration.json`):

- **Model Registry Overview**: Model count, status distribution, type distribution
- **Training Pipeline**: Training job status, duration, success rate
- **Inference Service**: Prediction rate, latency, error rate, data drift
- **ODH Service Health**: ODH service availability and response times

**Key Panels**:
- ML Models by Status
- Training Job Success Rate
- Inference Prediction Rate (predictions/second)
- Inference Latency (p50, p95, p99)
- Data Drift Score Trend
- ODH Service Response Time

### Alert Definitions

**ODH Integration Alerts**:

```yaml
# Training job failures
- alert: ODHTrainingJobFailuresHigh
  expr: rate(odh_training_job_failures_total[5m]) > 0.1
  for: 5m
  annotations:
    summary: "High training job failure rate"

# Inference latency high
- alert: ODHInferenceLatencyHigh
  expr: histogram_quantile(0.95, odh_inference_latency_seconds) > 0.5
  for: 5m
  annotations:
    summary: "High inference latency (p95 > 500ms)"

# Data drift detected
- alert: ODHDataDriftDetected
  expr: odh_inference_data_drift_score > 0.1
  for: 10m
  annotations:
    summary: "Data drift detected in inference inputs"

# ODH service unavailable
- alert: ODHServiceUnavailable
  expr: up{job="odh-service"} == 0
  for: 1m
  annotations:
    summary: "ODH service is unavailable"
```

### Monitoring Best Practices

1. **Model Lifecycle Tracking**: Monitor model status transitions (TRAINING → TRAINED → DEPLOYED)
2. **Training Performance**: Track training job duration and success rate
3. **Inference Quality**: Monitor inference latency, accuracy, and data drift
4. **ODH Service Health**: Monitor ODH service availability and response times
5. **Resource Usage**: Track resource consumption for training and inference

## Best Practices

### Metrics

1. **Use Histograms**: For latency measurements
2. **Use Counters**: For event counts
3. **Label Appropriately**: Use meaningful labels
4. **Avoid High Cardinality**: Limit label combinations

### Logging

1. **Use Structured Logging**: JSON format
2. **Include Correlation IDs**: For request tracing
3. **Log at Appropriate Levels**: Don't log everything as ERROR
4. **Avoid Sensitive Data**: Don't log passwords, tokens

### Tracing

1. **Trace Critical Paths**: Focus on important operations
2. **Keep Traces Small**: Limit trace size
3. **Use Sampling**: Sample traces in production

## Related Documentation

- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues
- [Runbooks](runbooks/README.md) - Operational procedures
- [Service Deployment Guide](SERVICE_DEPLOYMENT_GUIDE.md) - Service configuration


---

# Troubleshooting Guide

Common issues and solutions for the Data Interoperability Hub.

## Quick Diagnostics

### Check Service Health

```bash
# Check all services
docker compose ps

# Check specific service
docker compose logs api-service

# Check health endpoint
curl http://localhost:8000/health
```

### Check Database Connection

```bash
# Test PostgreSQL connection
docker compose exec postgres psql -U hub -d hub -c "SELECT 1;"

# Check database size
docker compose exec postgres psql -U hub -d hub -c "SELECT pg_size_pretty(pg_database_size('hub'));"
```

### Check Redis Connection

```bash
# Test Redis connection
docker compose exec redis redis-cli ping

# Check Redis info
docker compose exec redis redis-cli info
```

## Billing & Governance Troubleshooting (Phase 120D)

### B6: Stripe Circuit Breaker Open

**Symptoms**: All billing mutations fail with `CircuitBreakerError`. Stripe calls fast-fail without reaching the API.

**Diagnosis**:
```bash
# Check circuit breaker state via health endpoint
curl -s http://localhost:8000/api/health/ | jq '.circuit_breakers'

# Check Redis for circuit breaker state
docker compose exec redis-cache redis-cli GET "circuit_breaker:stripe-billing:state"
```

**Resolution**:
1. **Check Stripe status**: Visit [status.stripe.com](https://status.stripe.com)
2. **Wait for recovery**: Circuit auto-transitions to HALF_OPEN after 60s timeout, then CLOSED after 2 successful probes
3. **Manual reset** (if Stripe is healthy but circuit stuck):
   ```bash
   docker compose exec api python manage.py shell -c "
   from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
   reset_circuit_breaker_by_name('stripe-billing')
   "
   ```

### B5: Stripe Reconciliation

**Usage**: Detect and fix drift between local subscription status and Stripe:

```bash
# Dry run — report drift without changing DB
python manage.py reconcile_stripe --dry-run

# Fix drift — update local records to match Stripe
python manage.py reconcile_stripe

# Custom batch size for large deployments
python manage.py reconcile_stripe --batch-size 50
```

**Output**: Structured JSON to stdout with events: `reconcile_start`, `drift_detected`, `reconcile_complete`. Creates `RECONCILE_STATUS_FIX` audit events for each correction.

### G4: KYC Expiration Troubleshooting

**Symptoms**: Orders or entitlements fail with `KYC_VERIFICATION_REQUIRED` even though tenant was previously verified.

**Diagnosis**:
```bash
# Check tenant KYC status
docker compose exec api python manage.py shell -c "
from hub.apps.tenants.models import Tenant
t = Tenant.objects.get(slug='<tenant-slug>')
print(f'KYC: {t.kyc_status}, verified_at: {t.kyc_verified_at}, expires_at: {t.kyc_expires_at}')
"
```

**Resolution**:
1. If `kyc_expires_at` is in the past → KYC has expired. Tenant must re-verify.
2. Run `refresh_kyc_status` to update expired KYC statuses: `python manage.py refresh_kyc_status`
3. Platform admin can manually update: `PATCH /api/v1/platform/tenants/{id}/ {"kyc_status": "VERIFIED"}`

---

## Common Issues

### Services Won't Start

**Symptoms**: Services fail to start or crash immediately

**Solutions**:
```bash
# Check logs
docker compose logs <service-name>

# Check port conflicts
netstat -tulpn | grep -E '8000|5432|6379|9000'

# Restart services
docker compose restart <service-name>

# Rebuild services
docker compose build <service-name>
docker compose up -d <service-name>
```

### Database Connection Errors

**Symptoms**: `django.db.utils.OperationalError: could not connect to server`

**Solutions**:
```bash
# Ensure PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Restart PostgreSQL
docker compose restart postgres

# Check connection string
echo $DATABASE_URL
```

### Migration Errors

**Symptoms**: `django.db.migrations.exceptions.MigrationError`

**Solutions**:
```bash
# Show migration status
python manage.py showmigrations

# Fake migration (if needed)
python manage.py migrate --fake <app> <migration>

# Rollback migration
python manage.py migrate <app> <previous_migration>
```

### Redis Connection Errors

**Symptoms**: `redis.exceptions.ConnectionError`

**Solutions**:
```bash
# Ensure Redis is running
docker compose ps redis

# Check Redis logs
docker compose logs redis

# Restart Redis
docker compose restart redis

# Clear Redis cache
docker compose exec redis redis-cli FLUSHALL
```

### MinIO Connection Errors

**Symptoms**: `botocore.exceptions.ClientError: Unable to locate credentials`

**Solutions**:
```bash
# Ensure MinIO is running
docker compose ps minio

# Check MinIO logs
docker compose logs minio

# Verify credentials
echo $MINIO_ACCESS_KEY
echo $MINIO_SECRET_KEY

# Test MinIO connection
curl http://localhost:9000/minio/health/live
```

### Worker Not Processing Jobs

**Symptoms**: Jobs stuck in queue

**Solutions**:
```bash
# Check worker is running
docker compose ps worker-service

# Check worker logs
docker compose logs worker-service

# Restart worker
docker compose restart worker-service

# Check queue status
docker compose exec api-service python manage.py rqstats
```

### Workflow Engine Not Processing

**Symptoms**: Workflows stuck in DRAFT or RUNNING

**Solutions**:
```bash
# Check workflow engine is running
docker compose ps workflow-engine-service

# Check workflow engine logs
docker compose logs workflow-engine-service

# Restart workflow engine
docker compose restart workflow-engine-service

# Check workflow status
docker compose exec api-service python manage.py shell
>>> from hub.apps.orchestration.models import WorkflowInstance
>>> WorkflowInstance.objects.filter(status='RUNNING').count()
```

### API 500 Errors

**Symptoms**: Internal server errors

**Solutions**:
```bash
# Check API logs
docker compose logs api-service

# Check Django logs
docker compose exec api-service tail -f /var/log/django.log

# Enable debug mode (development only)
export DEBUG=True
docker compose restart api-service

# Check database integrity
python manage.py check --deploy
```

### Authentication Errors

**Symptoms**: `401 Unauthorized` or `403 Forbidden`

**Solutions**:
```bash
# Check JWT secret key
echo $SECRET_KEY

# Verify token
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/auth/me/

# Check user permissions
docker compose exec api-service python manage.py shell
>>> from hub.apps.users.models import User
>>> user = User.objects.get(email='user@example.com')
>>> user.is_active
>>> user.roles.all()
```

### CORS Errors

**Symptoms**: `Access-Control-Allow-Origin` errors in browser

**Solutions**:
```bash
# Check CORS settings
grep CORS_ALLOWED_ORIGINS hub/settings.py

# Add origin to CORS_ALLOWED_ORIGINS
export CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
docker compose restart api-service
```

### Performance Issues

**Symptoms**: Slow API responses, timeouts

**Solutions**:
```bash
# Check database queries
python manage.py shell
>>> from django.db import connection
>>> len(connection.queries)

# Check Redis cache hit rate
docker compose exec redis redis-cli info stats | grep keyspace

# Check service resource usage
docker stats

# Check database connections
docker compose exec postgres psql -U hub -d hub -c "SELECT count(*) FROM pg_stat_activity;"
```

## Log Analysis

### View Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs api-service

# Follow logs
docker compose logs -f api-service

# Last 100 lines
docker compose logs --tail=100 api-service

# Since timestamp
docker compose logs --since 2025-01-15T10:00:00 api-service
```

### Log Locations

- **Django**: `/var/log/django.log` (if configured)
- **Application**: `docker compose logs`
- **System**: `/var/log/syslog` (Linux)

### Common Log Patterns

```bash
# Errors
docker compose logs | grep -i error

# Warnings
docker compose logs | grep -i warning

# Database queries
docker compose logs api-service | grep "SELECT\|INSERT\|UPDATE\|DELETE"
```

## Database Issues

### Database Locked

```bash
# Check for locks
docker compose exec postgres psql -U hub -d hub -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Kill blocking queries
docker compose exec postgres psql -U hub -d hub -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';"
```

### Database Corruption

```bash
# Check database integrity
docker compose exec postgres psql -U hub -d hub -c "VACUUM ANALYZE;"

# Reindex database
docker compose exec postgres psql -U hub -d hub -c "REINDEX DATABASE hub;"
```

### Database Size

```bash
# Check database size
docker compose exec postgres psql -U hub -d hub -c "SELECT pg_size_pretty(pg_database_size('hub'));"

# Check table sizes
docker compose exec postgres psql -U hub -d hub -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## Network Issues

### Service Communication

```bash
# Test service connectivity
docker compose exec api-service curl http://semantic-service:8081/health
docker compose exec api-service curl http://dq-service:8083/health
docker compose exec api-service curl http://compliance-service:8082/health
```

### DNS Resolution

```bash
# Test DNS
docker compose exec api-service nslookup semantic-service
docker compose exec api-service nslookup postgres
```

## API Endpoint Troubleshooting

### Compliance Endpoints

**Symptoms**: Compliance run endpoints returning errors or not responding

**Solutions**:
```bash
# Check compliance service health
docker compose exec api-service curl http://compliance-service:8082/health

# Test compliance runs endpoint
curl -X GET http://localhost:8000/api/v1/compliance/runs/ \
  -H "Authorization: Bearer <token>"

# Check compliance run status
curl -X GET http://localhost:8000/api/v1/compliance/runs/{run-id}/ \
  -H "Authorization: Bearer <token>"

# Check compliance run results
curl -X GET http://localhost:8000/api/v1/compliance/runs/{run-id}/results/ \
  -H "Authorization: Bearer <token>"

# Check compliance service logs
docker compose logs compliance-service

# Verify compliance service connectivity
docker compose exec api-service curl -v http://compliance-service:8082/health
```

**Common Issues**:
- **404 Not Found**: Verify endpoint uses `/api/v1/compliance/runs/` (not `/compliance-runs/`)
- **500 Internal Server Error**: Check compliance service logs
- **Timeout**: Verify compliance service is running and accessible
- **401 Unauthorized**: Check authentication token

### Data Quality Endpoints

**Symptoms**: DQ run endpoints returning errors or not responding

**Solutions**:
```bash
# Check DQ service health
docker compose exec api-service curl http://dq-service:8083/health

# Test DQ runs endpoint
curl -X GET http://localhost:8000/api/v1/dq/runs/ \
  -H "Authorization: Bearer <token>"

# Check DQ run status
curl -X GET http://localhost:8000/api/v1/dq/runs/{run-id}/ \
  -H "Authorization: Bearer <token>"

# Check DQ run results
curl -X GET http://localhost:8000/api/v1/dq/runs/{run-id}/results/ \
  -H "Authorization: Bearer <token>"

# Check DQ service logs
docker compose logs dq-service

# Verify DQ service connectivity
docker compose exec api-service curl -v http://dq-service:8083/health
```

**Common Issues**:
- **404 Not Found**: Verify endpoint uses `/api/v1/dq/runs/` (not `/dq-runs/`)
- **500 Internal Server Error**: Check DQ service logs
- **Timeout**: Verify DQ service is running and accessible
- **401 Unauthorized**: Check authentication token

### Endpoint Pattern Verification

**Verify Standardized Endpoints**:
```bash
# Compliance endpoints (correct pattern)
curl http://localhost:8000/api/v1/compliance/runs/
curl http://localhost:8000/api/v1/compliance/runs/{id}/
curl http://localhost:8000/api/v1/compliance/runs/{id}/results/

# DQ endpoints (correct pattern)
curl http://localhost:8000/api/v1/dq/runs/
curl http://localhost:8000/api/v1/dq/runs/{id}/
curl http://localhost:8000/api/v1/dq/runs/{id}/results/
```

**Note**: Old endpoint patterns (e.g. paths containing `compliance-runs` or `dq-runs`) are deprecated and return `404 Not Found`. Always use the standardized patterns (`/runs/`).

---

## Resource Issues

### Memory Issues

```bash
# Check memory usage
docker stats

# Check system memory
free -h

# Restart services to free memory
docker compose restart
```

### Disk Space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up Docker
docker system prune -a
```

## Recovery Procedures

### Service Recovery

```bash
# Restart all services
docker compose restart

# Rebuild and restart
docker compose build
docker compose up -d
```

### Database Recovery

```bash
# Backup database
docker compose exec postgres pg_dump -U hub hub > backup.sql

# Restore database
docker compose exec -T postgres psql -U hub hub < backup.sql
```

### Data Recovery

```bash
# List backups
ls -lh backups/

# Restore from backup
./scripts/restore_backup.sh <backup-file>
```

## Getting Help

### Debug Information

When reporting issues, include:

1. **Service logs**: `docker compose logs <service>`
2. **Service status**: `docker compose ps`
3. **Environment**: `docker compose config`
4. **Error messages**: Full error traceback
5. **Steps to reproduce**: Detailed steps

### Support Channels

- **Documentation**: Check relevant documentation
- **Runbooks**: See [Runbooks](runbooks/README.md)
- **Issue Tracker**: Report bugs and issues

## Related Documentation

- [Runbooks](runbooks/README.md) - Operational runbooks
- [Monitoring Guide](MONITORING.md) - Monitoring and observability
- [Deployment Guide](DOCKER_COMPOSE_DEPLOYMENT.md) - Deployment procedures


---

# Release criteria and gate

**Last Updated**: 2026-03-22  
**Status**: Active  
**Source**: gapfix1 Phase 6.3.1; testreview1 Phase 16 / GAP_REMEDIATION_PLAN §11

---

## Release gate (mandatory)

**Do not release** (staging or production) until the following gate is satisfied:

1. **Green Phase 12A** — Full test suite run and all critical suites green.
2. **Test summary report** — Report generated from evidence and retained.
3. **Sign-off** — When gap remediation applies, product/tech lead sign-off obtained.

In short: **Green Phase 12A + test summary report + sign-off** is the gate before release.

---

## How to satisfy the gate

### 1. Green Phase 12A

Run the full Phase 12A suite (backend unit/integration/E2E, frontend unit/E2E, security, performance, concurrency, regression):

```bash
./scripts/run_phase_12a_full_suites.sh
```

- Use the same suite every time so release is consistent. See [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) and [RUNBOOKS.md — Full test suite (Phase 12A-style)](RUNBOOKS.md#full-test-suite-phase-12a-style).
- If any suite fails, fix at **root cause** (no mocks/stubs; no masking). Re-run until green.

### 2. Test summary report

Generate the report from the evidence collected by the Phase 12A run:

```bash
./scripts/generate_test_summary_report.sh YYYY-MM-DD
```

- Evidence lives under `test_reports_comprehensive/{date}/`. The report summarizes pass/fail, duration, coverage, and evidence links. See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md).

### 3. Sign-off

When **gap remediation** applies (e.g. [gapfix1](../openspec/changes/gapfix1/tasks.md), [testreview1](../openspec/changes/testreview1/tasks.md) Phase 16):

- Complete [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation).
- Product/tech lead confirms documentation and implementation; gap items resolved or deferred as planned; evidence and report location recorded.
- **Release MUST NOT proceed** until sign-off is obtained. See [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md).

---

## Related documentation

- [RUNBOOKS.md — Deployment and rollback](RUNBOOKS.md#deployment-and-rollback): Deploy only after green Phase 12A + sign-off.
- [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation): Steps and sign-off.
- [DOCKER_COMPOSE_DEPLOYMENT.md](DOCKER_COMPOSE_DEPLOYMENT.md): Release gate (Step 0), deployment steps, rollback.

---

# Docker Performance Optimization Guide

This guide provides recommendations and scripts for optimizing Docker performance, particularly for Prefect flow runs that use Docker workers.

## Quick Start

Run the optimization script regularly:

```bash
# Standard cleanup (safe, doesn't remove volumes)
./scripts/optimize-docker-performance.sh

# Aggressive cleanup (removes unused volumes - use with caution)
./scripts/optimize-docker-performance.sh --aggressive

# Dry run (preview what would be cleaned)
./scripts/optimize-docker-performance.sh --dry-run
```

## Common Performance Issues

### Issue: Prefect Flow Runs Timing Out

**Symptoms:**
- Prefect flow runs fail with `ReadTimeout` errors
- Docker container creation takes >60 seconds
- E2E tests timeout waiting for flow runs to complete

**Root Causes:**
1. Docker daemon is slow or overloaded
2. Too many concurrent Docker operations
3. Unused Docker resources consuming disk space
4. Docker socket timeout too low

**Solutions:**

1. **Run Docker cleanup:**
   ```bash
   ./scripts/optimize-docker-performance.sh
   ```

2. **Restart Docker daemon** (if you have sudo access):
   ```bash
   sudo systemctl restart docker
   ```

3. **Monitor Docker performance:**
   ```bash
   docker stats --no-stream
   docker system df
   ```

## Docker Daemon Configuration

### Optimize `/etc/docker/daemon.json`

Create or update `/etc/docker/daemon.json` with the following configuration:

```json
{
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10,
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "nofile": {
      "Hard": 64000,
      "Name": "nofile",
      "Soft": 64000
    }
  }
}
```

**Apply changes:**
```bash
sudo systemctl restart docker
```

**Note:** Requires sudo/root access. If you don't have access, ask your system administrator.

## Docker Compose Configuration

### Prefect Worker Docker Configuration

The `prefect-worker-docker` service in `docker-compose.yml` is configured with:

1. **Docker socket timeouts:**
   - `DOCKER_CLIENT_TIMEOUT`: 120 seconds (default)
   - `DOCKER_READ_TIMEOUT`: 120 seconds (default)

2. **Concurrent flow run limit:**
   - `PREFECT_WORKER_LIMIT`: 2 (default) - limits concurrent flow runs to reduce Docker daemon load

**Customize timeouts:**
```bash
# In .env.dev or docker-compose.yml
DOCKER_CLIENT_TIMEOUT=180
DOCKER_READ_TIMEOUT=180
PREFECT_WORKER_LIMIT=1  # Reduce to 1 for slower systems
```

## Regular Maintenance

### Daily/Weekly Cleanup

Run the optimization script regularly:

```bash
# Weekly standard cleanup
./scripts/optimize-docker-performance.sh

# Monthly aggressive cleanup (removes unused volumes)
./scripts/optimize-docker-performance.sh --aggressive
```

### Manual Cleanup Commands

If you prefer manual cleanup:

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -af

# Remove unused volumes (be careful!)
docker volume prune -f

# System-wide prune
docker system prune -af
```

## Monitoring Docker Performance

### Check Disk Usage

```bash
docker system df
```

**Output shows:**
- Images disk usage
- Containers disk usage
- Volumes disk usage
- Build cache disk usage

### Monitor Resource Usage

```bash
# Real-time stats
docker stats

# One-time snapshot
docker stats --no-stream
```

### Check Docker Daemon Health

```bash
docker info | grep -E "Server Version|Storage Driver|Logging Driver"
```

## E2E Test Timeouts

### Scheduled Export E2E Tests

The scheduled export E2E tests have been configured with increased timeouts to handle Docker daemon slowness:

- **Run completion timeout:** 3 minutes (was 2 minutes)
- **Test timeout:** 4 minutes (was 3 minutes)

**Location:** `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts`

If tests still timeout, consider:

1. Running Docker cleanup before tests
2. Reducing `PREFECT_WORKER_LIMIT` to 1
3. Increasing test timeouts further (if needed)

## Troubleshooting

### Docker Daemon Not Responding

**Symptoms:**
- `docker ps` hangs
- `docker info` times out
- Prefect flow runs fail immediately

**Solutions:**

1. **Check Docker daemon status:**
   ```bash
   sudo systemctl status docker
   ```

2. **Restart Docker daemon:**
   ```bash
   sudo systemctl restart docker
   ```

3. **Check Docker logs:**
   ```bash
   sudo journalctl -u docker.service -n 100
   ```

### Prefect Flow Runs Failing with Timeout

**Symptoms:**
- Flow runs fail with `ReadTimeout: UnixHTTPConnectionPool(...) Read timed out`
- Container creation takes >60 seconds

**Solutions:**

1. **Increase Docker socket timeouts** (already configured in docker-compose.yml)
2. **Reduce concurrent flow runs** by setting `PREFECT_WORKER_LIMIT=1`
3. **Run Docker cleanup** to free resources
4. **Restart Docker daemon** if it's unresponsive

### High Disk Usage

**Symptoms:**
- `docker system df` shows high disk usage
- System running out of disk space

**Solutions:**

1. **Run aggressive cleanup:**
   ```bash
   ./scripts/optimize-docker-performance.sh --aggressive
   ```

2. **Remove specific unused resources:**
   ```bash
   # Remove unused images
   docker image prune -af
   
   # Remove unused volumes (be careful!)
   docker volume prune -f
   ```

3. **Check what's using space:**
   ```bash
   docker system df -v
   ```

## Best Practices

1. **Regular Cleanup:** Run `./scripts/optimize-docker-performance.sh` weekly
2. **Monitor Performance:** Check `docker stats` and `docker system df` regularly
3. **Limit Concurrency:** Use `PREFECT_WORKER_LIMIT` to prevent Docker daemon overload
4. **Increase Timeouts:** Configure appropriate timeouts for slow Docker daemons
5. **Restart When Needed:** Restart Docker daemon if it becomes unresponsive

## Related Documentation

- [Docker Compose Deployment Guide](DOCKER_COMPOSE_DEPLOYMENT.md)
- [Prefect Integration Service README](../services/prefect-integration/README.md)
- [E2E Testing Guide](../frontend/e2e/README.md)

## Scripts

- `scripts/optimize-docker-performance.sh` - Docker performance optimization script
- `scripts/cleanup-docker-compose.sh` - Docker Compose cleanup script

---

# Deployment Order: Scheduled Ingestion (Prefect Worker)

This document describes the deployment order for migrating scheduled ingestion from django-rq to Prefect worker execution (Option C).

**Last Updated:** 2026-02-02
**Version:** 1.0

---

## Overview

The migration to Prefect worker execution requires a specific deployment order to ensure zero downtime and proper rollback capability. This document outlines the step-by-step deployment procedure.

**Key Principle:** Deploy hub API changes first (with optional feature flag), then deploy Prefect flow and worker, then switch to new flow, and finally disable django-rq path.

---

## Deployment Order

### Phase 1: Deploy Hub API (New Worker API Endpoints)

**Objective:** Deploy hub API with new internal Worker API endpoints while maintaining backward compatibility.

**Steps:**

1. **Deploy Hub API Service**
   ```bash
   # Docker Compose
   docker-compose pull api-service
   docker-compose up -d api-service

   # Kubernetes
   kubectl set image deployment/api-service api-service=hub-api:<version> -n default
   kubectl rollout status deployment/api-service -n default
   ```

2. **Verify Hub API Health**
   ```bash
   # Check health endpoint
   curl http://localhost:8000/health

   # Verify new internal endpoints exist (should return 401 without auth, not 404)
   curl -X POST http://localhost:8000/api/v1/scheduled-ingestions/internal/runs/ \
     -H "Content-Type: application/json" \
     -d '{"scheduled_ingestion_id": "test"}'
   # Expected: 401 Unauthorized (not 404 Not Found)
   ```

3. **Verify Backward Compatibility**
   - Existing scheduled ingestion APIs continue to work
   - Existing scheduled ingestion runs continue via django-rq (if still enabled)
   - No breaking changes to public APIs

**Rollback:** If issues occur, rollback hub API deployment:
```bash
kubectl rollout undo deployment/api-service -n default
```

**Duration:** ~5-10 minutes

---

### Phase 2: Deploy Prefect Flow and Worker (Optional Feature Flag)

**Objective:** Deploy Prefect flow code and worker with optional feature flag for gradual rollout.

**Steps:**

1. **Deploy Prefect Integration Service**
   ```bash
   # Docker Compose
   docker-compose pull prefect-integration-service
   docker-compose up -d prefect-integration-service

   # Kubernetes
   kubectl set image deployment/prefect-integration-service \
     prefect-integration-service=hub-prefect-integration:<version> -n prefect
   kubectl rollout status deployment/prefect-integration-service -n prefect
   ```

2. **Deploy Prefect Worker**
   ```bash
   # Docker Compose
   docker-compose pull prefect-worker
   docker-compose up -d prefect-worker

   # Kubernetes
   kubectl set image deployment/prefect-worker \
     prefect-worker=prefecthq/prefect:2-python3.12 -n prefect
   kubectl rollout status deployment/prefect-worker -n prefect
   ```

3. **Verify Prefect Worker Status**
   ```bash
   # Check worker logs
   docker-compose logs prefect-worker --tail=50
   # or
   kubectl logs -l app=prefect-worker -n prefect --tail=50

   # Verify worker connected to Prefect server
   docker-compose exec prefect-worker prefect worker status
   ```

4. **Verify Work Pool**
   ```bash
   # Check work pool exists and has active workers
   docker-compose exec prefect-worker prefect work-pool inspect default
   ```

5. **Sync Prefect Deployments (Optional)**
   ```bash
   # Sync deployments for existing scheduled ingestions
   # This can be done manually or via API
   curl -X POST http://prefect-integration-service:8084/deployments/sync \
     -H "Content-Type: application/json" \
     -d '{"scheduled_ingestion_id": "<id>", "tenant_id": "<tenant-id>"}'
   ```

**Feature Flag (Optional):**
If gradual rollout is desired, set feature flag:
```bash
# Environment variable (Docker Compose)
export USE_PREFECT_FOR_SCHEDULED_INGESTION=false  # Start with false

# Kubernetes ConfigMap
kubectl create configmap scheduled-ingestion-config \
  --from-literal=USE_PREFECT_FOR_SCHEDULED_INGESTION=false \
  -n default
```

**Rollback:** If issues occur:
```bash
kubectl rollout undo deployment/prefect-worker -n prefect
kubectl rollout undo deployment/prefect-integration-service -n prefect
```

**Duration:** ~10-15 minutes

---

### Phase 3: Switch Deployment to New Flow

**Objective:** Switch scheduled ingestion execution from django-rq to Prefect flow.

**Steps:**

1. **Verify Prefect Worker is Healthy**
   ```bash
   # Check worker status
   docker-compose ps prefect-worker
   # or
   kubectl get pods -l app=prefect-worker -n prefect

   # Check worker logs for errors
   docker-compose logs prefect-worker --tail=100 | grep -i error
   ```

2. **Sync All Scheduled Ingestion Deployments**
   ```bash
   # Via Prefect Integration Service API (for each scheduled ingestion)
   # Or via Django management command if available
   python manage.py sync_prefect_deployments
   ```

3. **Enable Feature Flag (if using gradual rollout)**
   ```bash
   # Set feature flag to true
   export USE_PREFECT_FOR_SCHEDULED_INGESTION=true

   # Restart hub API to pick up flag
   docker-compose restart api-service
   # or
   kubectl rollout restart deployment/api-service -n default
   ```

4. **Verify First Prefect Flow Run**
   - Wait for next scheduled run or trigger manually
   - Check Prefect UI for flow run status
   - Verify hub run is created via Worker API
   - Check run completes successfully

5. **Monitor Metrics**
   ```bash
   # Check Prometheus metrics
   curl http://localhost:8000/metrics | grep scheduled_ingestion

   # Verify no errors in alerts
   curl http://localhost:9090/api/v1/alerts | jq '.data[] | select(.labels.component == "scheduled-ingestion")'
   ```

**Rollback:** If issues occur:
```bash
# Disable feature flag
export USE_PREFECT_FOR_SCHEDULED_INGESTION=false
docker-compose restart api-service
```

**Duration:** ~15-30 minutes (including monitoring)

---

### Phase 4: Disable django-rq Path

**Objective:** Remove django-rq execution path for scheduled ingestion (after Prefect path is stable).

**Steps:**

1. **Verify Prefect Path is Stable**
   - Monitor for at least 24 hours (or agreed period)
   - Verify all scheduled runs complete successfully
   - Check error rates are within acceptable limits
   - Verify no stuck runs

2. **Remove django-rq Handler (Code Change)**
   - Update `hub/apps/jobs/tasks.py` to remove/disable SCHEDULED_INGESTION handler
   - Ensure no code path enqueues SCHEDULED_INGESTION to django-rq
   - Deploy code change

3. **Deploy Updated Hub API**
   ```bash
   # Deploy hub API with django-rq path removed
   docker-compose pull api-service
   docker-compose up -d api-service
   # or
   kubectl set image deployment/api-service api-service=hub-api:<version> -n default
   kubectl rollout status deployment/api-service -n default
   ```

4. **Verify django-rq Path is Disabled**
   ```bash
   # Check RQ queue (should not have SCHEDULED_INGESTION jobs)
   docker-compose exec redis redis-cli LLEN rq:queue:job_default

   # Trigger scheduled ingestion and verify no RQ job enqueued
   curl -X POST http://localhost:8000/api/v1/scheduled-ingestions/<id>/trigger/ \
     -H "Authorization: Bearer <token>"

   # Verify Prefect flow run started instead
   # Check Prefect UI for new flow run
   ```

5. **Remove Feature Flag (if used)**
   ```bash
   # Remove feature flag from environment/config
   # Code should always use Prefect path now
   ```

**Rollback:** If issues occur:
- Re-enable django-rq handler code
- Redeploy hub API
- Set feature flag back to false (if used)

**Duration:** ~10-15 minutes

---

## Complete Deployment Timeline

| Phase | Duration | Rollback Window |
|-------|----------|-----------------|
| Phase 1: Hub API | 5-10 min | Immediate |
| Phase 2: Prefect Flow/Worker | 10-15 min | Immediate |
| Phase 3: Switch to Prefect | 15-30 min | 24 hours |
| Phase 4: Disable django-rq | 10-15 min | 24 hours |
| **Total** | **40-70 min** | **48 hours** |

---

## Pre-Deployment Checklist

- [ ] All tests passing (unit, integration, E2E)
- [ ] Code review completed and approved
- [ ] Prefect server is healthy and accessible
- [ ] Hub API is healthy
- [ ] Database migrations applied (if any)
- [ ] Environment variables configured (`HUB_WORKER_API_KEY`, `PREFECT_API_URL`, etc.)
- [ ] Monitoring dashboards ready
- [ ] Rollback plan documented
- [ ] Team notified of deployment

---

## Post-Deployment Validation

### Immediate (First 10 minutes)

- [ ] Hub API health check passes
- [ ] Prefect worker connected and healthy
- [ ] Work pool active with workers
- [ ] No error spikes in metrics
- [ ] No alerts firing

### Short-term (First hour)

- [ ] At least one scheduled ingestion run completes successfully via Prefect
- [ ] Hub run created and updated correctly
- [ ] Prefect flow_run_id correlated with hub run_id
- [ ] Files processed successfully
- [ ] Metrics reporting correctly

### Long-term (24 hours)

- [ ] All scheduled runs complete successfully
- [ ] No stuck runs detected
- [ ] Error rates within acceptable limits
- [ ] Performance metrics stable
- [ ] No rollback needed

---

## Rollback Procedures

### Rollback Phase 4 (Disable django-rq)

If issues occur after disabling django-rq:

1. **Re-enable django-rq Handler**
   - Revert code change in `hub/apps/jobs/tasks.py`
   - Redeploy hub API

2. **Set Feature Flag (if used)**
   ```bash
   export USE_PREFECT_FOR_SCHEDULED_INGESTION=false
   docker-compose restart api-service
   ```

3. **Verify Rollback**
   - Check RQ queue for SCHEDULED_INGESTION jobs
   - Verify runs complete via django-rq
   - Monitor for stability

### Rollback Phase 3 (Switch to Prefect)

If issues occur after switching to Prefect:

1. **Disable Feature Flag**
   ```bash
   export USE_PREFECT_FOR_SCHEDULED_INGESTION=false
   docker-compose restart api-service
   ```

2. **Verify django-rq Path Active**
   - Check RQ queue for jobs
   - Verify runs complete via django-rq

### Rollback Phase 2 (Prefect Flow/Worker)

If issues occur with Prefect worker:

1. **Rollback Worker Deployment**
   ```bash
   kubectl rollout undo deployment/prefect-worker -n prefect
   ```

2. **Rollback Integration Service**
   ```bash
   kubectl rollout undo deployment/prefect-integration-service -n prefect
   ```

### Rollback Phase 1 (Hub API)

If issues occur with hub API:

1. **Rollback Hub API**
   ```bash
   kubectl rollout undo deployment/api-service -n default
   ```

---

## Feature Flag Configuration

### Environment Variable

**Docker Compose:**
```yaml
services:
  api-service:
    environment:
      USE_PREFECT_FOR_SCHEDULED_INGESTION: "false"  # Start with false
```

**Kubernetes ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: scheduled-ingestion-config
  namespace: default
data:
  USE_PREFECT_FOR_SCHEDULED_INGESTION: "false"  # Start with false
```

### Django Settings

```python
# hub/settings.py
USE_PREFECT_FOR_SCHEDULED_INGESTION = env.bool(
    "USE_PREFECT_FOR_SCHEDULED_INGESTION", default=False
)
```

### Code Usage

```python
# hub/apps/scheduled_ingestion/views.py
from django.conf import settings

if settings.USE_PREFECT_FOR_SCHEDULED_INGESTION:
    # Use Prefect flow
    trigger_prefect_flow(...)
else:
    # Use django-rq (legacy)
    enqueue_scheduled_ingestion_job(...)
```

---

## Monitoring During Deployment

### Key Metrics to Watch

1. **Hub API Metrics**
   - `http_requests_total` (should remain stable)
   - `http_errors_total` (should not spike)
   - `scheduled_ingestion_runs_total` (should continue)

2. **Prefect Metrics**
   - Worker connection status
   - Flow run success rate
   - Flow run duration

3. **Scheduled Ingestion Metrics**
   - `scheduled_ingestion_runs_running` (should not have stuck runs)
   - `scheduled_ingestion_runs_total{status="FAILED"}` (should remain low)
   - `scheduled_ingestion_files_processed_total` (should continue)

### Alerts to Monitor

- `ScheduledIngestionRunStuck` (should not fire)
- `ScheduledIngestionNoRunsStarted` (should not fire during deployment)
- `ServiceDown` (should not fire)

---

## Release Notes Template

```markdown
## Scheduled Ingestion Migration to Prefect Worker

### Summary
Migrated scheduled ingestion execution from django-rq to Prefect worker (Option C).

### Changes
- Added internal Worker API endpoints for run lifecycle and process-file
- Deployed Prefect flow (`scheduled_ingestion_full_flow`) for scheduled ingestion
- Prefect worker now executes scheduled ingestion runs
- Removed django-rq execution path for scheduled ingestion

### Deployment Order
1. Hub API (new Worker API endpoints)
2. Prefect flow and worker
3. Switch to Prefect execution
4. Disable django-rq path

### Breaking Changes
- None (backward compatible during migration)

### Rollback
- Feature flag `USE_PREFECT_FOR_SCHEDULED_INGESTION` available for gradual rollout
- django-rq path can be re-enabled if needed (Phase 4 rollback)

### Documentation
- See `docs/DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md` for deployment procedures
- See `runbooks/RB-SCHEDULED-INGESTION-001.md` for operational procedures
```

---

## Related Documentation

- `runbooks/RB-SCHEDULED-INGESTION-001.md`: Scheduled Ingestion Operations Runbook
- `runbooks/RB-DEPLOY-001.md`: Standard Deployment Procedure
- `docs/SCHEDULED_INGESTION_WORKER_API.md`: Worker API Documentation
- `docs/DOCKER_COMPOSE_DEPLOYMENT.md`: Docker Compose Deployment Guide
- `k8s/README.md`: Kubernetes Deployment Guide

---

# Operator External Setup Checklist

> Pre-flight checklist for deploying Meshant to a new environment.
> Updated: 2026-03-21 | Phase 112.K.1

## Prerequisites

- Kubernetes cluster (1.28+) with `kubectl` access
- Helm 3.15+
- External Secrets Operator installed (`external-secrets.io/v1beta1`)
- AWS Secrets Manager (Phase 211: replaced HashiCorp Vault)

---

## 1. Data Plane — PostgreSQL

| Item | Owner | Verification |
|------|-------|-------------|
| PostgreSQL 16 instance running | Platform/DBA | `pg_isready -h <host> -p 5432` |
| Database `hub` created | DBA | `psql -h <host> -c "SELECT 1" hub` |
| User with CREATEDB for migrations | DBA | `psql -c "\du hub"` |
| PgBouncer (optional, recommended) | Platform | `psql -h pgbouncer -p 5432 -c "SHOW POOLS"` |

Helm override: `postgresql.host`, `postgresql.port`, `postgresql.database`

## 2. Data Plane — Redis

Four separate Redis instances (or databases on one instance):

| Instance | Default Host | Purpose | Verification |
|----------|-------------|---------|-------------|
| Cache | `redis-cache:6379` | Response/contract caching | `redis-cli -h redis-cache ping` |
| Queue | `redis-queue:6379` | RQ job queues | `redis-cli -h redis-queue ping` |
| Events | `redis-events:6379` | Event bus Pub/Sub | `redis-cli -h redis-events ping` |
| Channels | `redis-channels:6379` | WebSocket (Django Channels) | `redis-cli -h redis-channels ping` |

Helm override: `redis.cache.host`, `redis.queue.host`, `redis.events.host`, `redis.channels.host`

## 3. Object Storage — MinIO / S3

| Item | Owner | Verification |
|------|-------|-------------|
| S3-compatible endpoint | Platform | `aws s3 ls --endpoint-url <url>` |
| Bucket `hub-files` created | Platform | `aws s3 ls s3://hub-files --endpoint-url <url>` |
| Access key + secret key in AWS Secrets Manager | Platform | `aws secretsmanager get-secret-value --secret-id hub/<env>/s3` |

Helm override: `s3.endpoint`, `s3.bucket`

## 4. Prefect Server + Worker

| Item | Owner | Verification |
|------|-------|-------------|
| Prefect Server deployed | Platform | `curl http://prefect-server:4200/api/health` |
| PostgreSQL for Prefect metadata | DBA | `pg_isready -h prefect-db -p 5432` |
| Work pool `kubernetes-pool` created | Platform | `prefect work-pool ls` |
| Prefect Integration Service deployed | Platform | `curl http://prefect-integration-service:8084/health` |
| `PREFECT_INTEGRATION_SERVICE_URL` in AWS Secrets Manager | Platform | `aws secretsmanager get-secret-value --secret-id hub/<env>/prefect` |

Helm override: `prefect.worker.enabled: true`, `prefectIntegration.enabled: true`

> **Note**: Prefect Server is NOT part of the Meshant Helm chart.
> Deploy separately: `helm install prefect-server prefecthq/prefect-server`

## 5. AWS Secrets Manager + External Secrets

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->

| Item | Owner | Verification |
|------|-------|-------------|
| AWS Secrets Manager accessible in target region | Security | `aws secretsmanager list-secrets --region <region> --max-results 1` |
| IRSA configured for in-cluster access | Security | `kubectl describe sa hub-api -n <ns> \| grep eks.amazonaws.com/role-arn` |
| GitHub OIDC→AWS STS configured for CI/CD | Security | Verify in AWS IAM Identity Providers |
| Secret paths `hub/<env>/` populated | Security | `aws secretsmanager list-secrets --filter Key=name,Values=hub/<env>` |
| ExternalSecrets operator running | Platform | `kubectl get pods -n external-secrets` |
| SecretStore created in namespace | Platform | `kubectl get secretstore -n <ns>` |
| ExternalSecret sync healthy | Platform | `kubectl get externalsecret -n <ns>` |

Required AWS Secrets Manager paths:
```
hub/<env>/django       → SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY
hub/<env>/postgres     → POSTGRES_PASSWORD
hub/<env>/pgbouncer    → PGBOUNCER_ADMIN_PASSWORD, userlist.txt
hub/<env>/redis        → REDIS_*_PASSWORD, REDIS_*_URL (×4)
hub/<env>/s3           → AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
hub/<env>/fuseki       → FUSEKI_ADMIN_PASSWORD
hub/<env>/workers      → HUB_WORKER_API_KEY
hub/<env>/stripe       → STRIPE_SECRET_KEY (optional)
```

## 6. Semantic Service + Fuseki

| Item | Owner | Verification |
|------|-------|-------------|
| Apache Fuseki running | Platform | `curl http://fuseki:3030/$$/ping` |
| Dataset `hub` created | Platform | `curl http://fuseki:3030/hub/sparql?query=ASK{}` |
| Semantic Service running | Platform | `curl http://semantic-service:8081/health` |

## 7. CI/CD — GitHub Deploy Secrets

| Secret | Purpose | Verification |
|--------|---------|-------------|
| `AWS_REGION` | AWS region for Secrets Manager | Set in repo Settings → Secrets |
| `AWS_SECRETS_PREFIX` | Secret name prefix (e.g. `hub`) | Set in repo Settings → Secrets |
| `AWS_KMS_KEY_ID` | KMS key for field-level encryption | Set in repo Settings → Secrets |
<!-- Phase 211: replaced VAULT_ADDR/VAULT_ROLE_ID/VAULT_SECRET_ID with AWS equivalents; CI/CD authenticates via GitHub OIDC→AWS STS -->
| `SMOKE_ADMIN_EMAIL` | Post-deploy smoke test user | Set in repo Settings → Secrets |
| `SMOKE_ADMIN_PASSWORD` | Post-deploy smoke test password | Set in repo Settings → Secrets |

## 8. Post-Deploy Verification

```bash
# Health check
kubectl exec -n <ns> deploy/hub-api -- curl -s localhost:8000/health

# Metrics endpoint (Prometheus scrape)
kubectl exec -n <ns> deploy/hub-api -- curl -s localhost:8000/metrics/ | head -5

# Database connectivity
kubectl exec -n <ns> deploy/hub-api -- python -c "
from django.db import connection; connection.ensure_connection(); print('DB OK')
"

# External secrets synced
kubectl get externalsecret -n <ns> -o jsonpath='{range .items[*]}{.metadata.name}: {.status.conditions[0].status}{"\n"}{end}'
```

---

# Capability Degradation Guide

> What happens when a dependency is unavailable, and how to recover.
> Updated: 2026-03-21 | Phase 112.K.2
> Linked from: `docs/OPERATIONS.md`

## Quick Reference

| Dependency | Impact When Down | User-Visible Behaviour | Auto-Recovery |
|-----------|-----------------|----------------------|---------------|
| PostgreSQL | **Total outage** | 503 on all API calls | No — manual intervention |
| Redis (Cache) | Degraded latency | Slower responses, no caching | Yes — requests bypass cache |
| Redis (Queue) | Jobs not processed | Async operations stall (DQ, compliance, emails) | Yes — jobs resume when Redis returns |
| Redis (Events) | Events not delivered | Webhooks delayed, event subscribers miss events | Yes — new events publish when Redis returns |
| MinIO / S3 | File ops fail | Upload/download errors | No — requires storage recovery |
| Fuseki | Semantic features fail | SPARQL queries return errors; ODPS semantic mapping unavailable | Yes — circuit breaker opens, requests fail fast |
| Compliance Service | Compliance scans fail | DQ/compliance runs error; compliance status stale | Yes — circuit breaker, jobs retry |
| DQ Service | Quality scoring fails | DQ runs error; quality scores stale | Yes — circuit breaker, jobs retry |
| Semantic Service | Mapping features fail | URI validation errors; ontology lookups fail | Yes — circuit breaker |
| Prefect Server | Scheduled jobs stop | No new scheduled ingestion/export runs trigger | Yes — runs resume when Prefect returns |
| Prefect Integration | Schedule sync fails | New/updated schedules not synced to Prefect | Yes — API retries on next request |

## Detailed Degradation Modes

### PostgreSQL Down

**Severity**: Critical — total service outage
**Symptoms**: All API requests return 503; workers crash-loop
**Runbook**: `docs/OPERATIONS.md` → Database backup/restore
**Recovery**: Restore PostgreSQL, verify `pg_isready`, pods auto-reconnect via PgBouncer

### Redis (any instance) Down

**Severity**: High (Queue/Events) / Medium (Cache/Channels)
**Symptoms**:
- Cache: responses slower, contract caching disabled (fail-open)
- Queue: async jobs (emails, DQ, compliance) not processed — queue builds up
- Events: webhook delivery stops, event bus silent
- Channels: WebSocket connections fail
**Recovery**: Redis restart; queued jobs auto-process; cache repopulates on demand

### Compliance / DQ / Semantic Service Down

**Severity**: Medium — feature-specific degradation
**Symptoms**: Respective features return errors; circuit breaker opens after 5 failures
**Circuit breaker**: `hub/apps/core/resilience/circuit_breaker.py`
- Threshold: 5 failures → OPEN (fail-fast for 60s)
- Half-open: 1 probe request after timeout
- Recovery: automatic when service returns
**Runbook**: `docs/RUNBOOKS.md` → service-specific sections

### Prefect Server / Integration Down

**Severity**: Medium — scheduled operations stop
**Symptoms**: No new scheduled ingestion/export runs; existing runs in Prefect continue
**Recovery**: Restart Prefect server; `prefect work-pool ls` to verify work pool
**Runbook**: `docs/ops/prefect-runbook.md`

### AWS Secrets Manager Unavailable (after initial sync)

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->
**Severity**: Low (short-term) — secrets already synced to K8s Secrets
**Symptoms**: ExternalSecret refresh fails; `kubectl get externalsecret` shows `SecretSyncedError`
**Impact**: Existing pods unaffected (secrets in K8s); new pods can start with cached secrets
**Recovery**: Check AWS service health dashboard; verify IRSA role trust policy; ExternalSecrets operator auto-retries
