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

**Production Recommendation**: Use External Secrets Operator or HashiCorp Vault.

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
- External Secrets Operator
- HashiCorp Vault
- Cloud provider secrets manager (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)

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

