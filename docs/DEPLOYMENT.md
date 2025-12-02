# Deployment Documentation

Complete guide for deploying the Interoperable Data Hub to staging and production environments.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Architecture](#deployment-architecture)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Procedures](#deployment-procedures)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Interoperable Data Hub is deployed using Docker containers orchestrated via Docker Compose (for staging) or Kubernetes (for production).

**Deployment Methods:**
- **Docker Compose**: Staging and local environments
- **Kubernetes**: Production environments
- **CI/CD**: Automated via GitHub Actions

**Environments:**
- **Local**: Developer machines (Docker Compose)
- **Staging**: Pre-production testing (Docker Compose or Kubernetes)
- **Production**: Tenant-facing environment (Kubernetes)

---

## Prerequisites

### Required Tools

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **kubectl** 1.24+ (for Kubernetes deployments)
- **PostgreSQL client** (for database operations)
- **Git** (for version control)

### Required Access

- Container registry access (GitHub Container Registry)
- Kubernetes cluster access (for production)
- Database access (for migrations)
- Secrets manager access (for configuration)

### Required Knowledge

- Docker and containerization
- Kubernetes basics (for production)
- Database migrations
- CI/CD pipelines

---

## Deployment Architecture

### Service Components

The hub consists of the following services:

1. **API Service** (Django) - Port 8000
2. **Worker Service** (Django RQ) - Background jobs
3. **DataContract Service** (FastAPI) - Port 8080
4. **Compliance Service** (FastAPI) - Port 8082
5. **DQ Service** (FastAPI) - Port 8083
6. **Semantic Service** (FastAPI) - Port 8081

### Infrastructure Components

1. **PostgreSQL** - Primary database
2. **Redis** - Job queue and caching
3. **MinIO/S3** - Object storage
4. **Apache Jena Fuseki** - RDF triple store

### Network Architecture

```
┌─────────────────┐
│   Load Balancer │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│  API  │ │Worker │
└───┬───┘ └───────┘
    │
    ├──► PostgreSQL
    ├──► Redis
    ├──► MinIO/S3
    ├──► DataContract Service
    ├──► Compliance Service
    ├──► DQ Service
    ├──► Semantic Service
    └──► Fuseki
```

---

## Environment Configuration

### Environment Variables

#### API Service

```bash
# Database
DATABASE_URL=postgresql://user:password@postgres:5432/hub

# Redis
REDIS_URL=redis://redis:6379/0

# Storage
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=hub-files
AWS_S3_ENDPOINT_URL=http://minio:9000

# Services
DATACONTRACT_SERVICE_URL=http://datacontract-service:8080
COMPLIANCE_SERVICE_URL=http://compliance-service:8082
DQ_SERVICE_URL=http://dq-service:8083
SEMANTIC_SERVICE_URL=http://semantic-service:8081

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=api.hub.example.com

# Django
DEBUG=False
DJANGO_SETTINGS_MODULE=hub.settings
```

#### Semantic Service

```bash
FUSEKI_URL=http://fuseki:3030
FUSEKI_DATASET=hub
HUB_DOMAIN=https://hub.example.com
```

### Secrets Management

**Staging:**
- Use environment files (`.env.staging`)
- Store in CI/CD secrets

**Production:**
- Use Kubernetes secrets
- Use external secrets manager (AWS Secrets Manager, HashiCorp Vault)

### Database Configuration

```bash
# PostgreSQL
POSTGRES_USER=hub
POSTGRES_PASSWORD=secure-password
POSTGRES_DB=hub
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

---

## Deployment Procedures

### Staging Deployment (Docker Compose)

#### 1. Prepare Environment

```bash
# Clone repository
git clone https://github.com/your-org/datainteroperabilityhub.git
cd datainteroperabilityhub

# Checkout staging branch
git checkout staging

# Copy environment file
cp .env.staging .env
```

#### 2. Pull Latest Images

```bash
# Pull latest images from registry
docker compose pull
```

#### 3. Run Database Migrations

```bash
# Run migrations
docker compose run --rm api-service python manage.py migrate
```

#### 4. Deploy Services

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f
```

#### 5. Verify Deployment

```bash
# Check health endpoints
curl http://localhost:8000/health/
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8083/health
```

### Production Deployment (Kubernetes)

#### 1. Prepare Kubernetes Manifests

```bash
# Update image tags in manifests
kubectl set image deployment/api-service \
  api-service=ghcr.io/your-org/datainteroperabilityhub-api-service:v1.0.0
```

#### 2. Apply Database Migrations

```bash
# Run migrations job
kubectl apply -f k8s/migrations/job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/migrations --timeout=300s
```

#### 3. Deploy Services

```bash
# Apply all manifests
kubectl apply -f k8s/

# Wait for rollout
kubectl rollout status deployment/api-service
kubectl rollout status deployment/worker-service
```

#### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods

# Check service endpoints
kubectl get svc

# Test health endpoints
kubectl port-forward svc/api-service 8000:8000
curl http://localhost:8000/health/
```

### CI/CD Deployment

Deployment is automated via GitHub Actions:

**Staging:**
- Automatic on push to `main` branch
- Workflow: `.github/workflows/deploy.yml`

**Production:**
- Triggered on version tags (`v*`)
- Requires manual approval
- Workflow: `.github/workflows/deploy.yml`

---

## Post-Deployment Verification

### Health Checks

```bash
# API Service
curl http://api.hub.example.com/health/

# Microservices
curl http://api.hub.example.com/api/v1/health/semantic/
curl http://api.hub.example.com/api/v1/health/datacontract/
curl http://api.hub.example.com/api/v1/health/compliance/
curl http://api.hub.example.com/api/v1/health/dq/
```

### Smoke Tests

```bash
# Run smoke tests
pytest tests/smoke/ -v

# Or use dedicated smoke test script
./scripts/smoke-tests.sh
```

### Functional Tests

```bash
# Run E2E tests against deployed environment
pytest tests/e2e/ -v \
  --base-url=https://api-staging.hub.example.com
```

### Monitoring

Check monitoring dashboards:

- **Grafana**: http://grafana.hub.example.com
- **Prometheus**: http://prometheus.hub.example.com
- **Application Logs**: `kubectl logs -f deployment/api-service`

---

## Rollback Procedures

### Docker Compose Rollback

```bash
# Stop current services
docker compose down

# Checkout previous version
git checkout <previous-commit>

# Restart services
docker compose up -d
```

### Kubernetes Rollback

```bash
# Rollback deployment
kubectl rollout undo deployment/api-service

# Check rollout status
kubectl rollout status deployment/api-service

# Rollback to specific revision
kubectl rollout undo deployment/api-service --to-revision=2
```

### Database Rollback

**⚠️ Warning**: Database rollbacks are complex and should be avoided. Always test migrations in staging first.

```bash
# List migration history
python manage.py showmigrations

# Rollback specific migration
python manage.py migrate app_name migration_name
```

---

## Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check logs
docker compose logs api-service
kubectl logs deployment/api-service

# Check resource usage
docker stats
kubectl top pods
```

#### Database Connection Issues

```bash
# Test database connection
psql -h postgres -U hub -d hub -c "SELECT 1;"

# Check database status
docker compose ps postgres
kubectl get pods -l app=postgres
```

#### Service Health Check Failures

```bash
# Check service endpoints
curl -v http://localhost:8000/health/

# Check service dependencies
docker compose exec api-service env | grep SERVICE_URL
```

#### High Memory Usage

```bash
# Check memory usage
docker stats
kubectl top pods

# Restart services if needed
docker compose restart api-service
kubectl rollout restart deployment/api-service
```

### Debugging

#### Enable Debug Mode (Staging Only)

```bash
# Set DEBUG=True in .env
DEBUG=True

# Restart services
docker compose restart api-service
```

#### View Detailed Logs

```bash
# Docker Compose
docker compose logs -f --tail=100 api-service

# Kubernetes
kubectl logs -f deployment/api-service --tail=100
```

#### Access Service Shell

```bash
# Docker Compose
docker compose exec api-service bash

# Kubernetes
kubectl exec -it deployment/api-service -- bash
```

---

## Runbooks

For detailed operational procedures, see:

- **RB-DEPLOY-001**: Standard Deployment Procedure
- **RB-DEPLOY-002**: Emergency Hotfix Deployment
- **RB-DEPLOY-003**: Rollback Procedure
- **RB-DB-001**: Database Migration Procedure
- **RB-SVC-001**: Service Health Check Procedure

Located in: `runbooks/`

---

## Support

For deployment support:

- **Documentation**: https://docs.hub.example.com/deployment
- **Issues**: https://github.com/your-org/datainteroperabilityhub/issues
- **Email**: devops@hub.example.com

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

