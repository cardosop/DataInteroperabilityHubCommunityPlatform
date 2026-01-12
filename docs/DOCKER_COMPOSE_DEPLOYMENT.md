# Docker Compose Deployment Guide

Complete guide for deploying the Data Interoperability Hub using Docker Compose in development, staging, and production environments.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment Steps](#deployment-steps)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Troubleshooting](#troubleshooting)
7. [Rollback Procedures](#rollback-procedures)
8. [Maintenance](#maintenance)
9. [Best Practices](#best-practices)

---

## Overview

The Data Interoperability Hub is deployed using Docker Compose, which orchestrates all services including:

- **Infrastructure Services**: PostgreSQL, Redis, MinIO, Fuseki
- **Core Application Services**: API Service, Worker Service
- **Workflow Services**: Workflow Engine, Workflow Registry
- **Event Bus Services**: Event Bus Health, Event Schema Registry
- **Microservices**: Semantic, DQ, Compliance, DataContract, Search, Observability, Webhook
- **Monitoring Services**: Prometheus, Grafana, Jaeger, Alertmanager
- **API Gateway**: Traefik
- **Orchestration**: Prefect Server, Prefect Workers, Prefect Integration Service

**Deployment Environments:**
- **Development**: Local development with hot-reload (`docker-compose.dev.yml`)
- **Staging**: Pre-production testing (`docker-compose.staging.yml`)
- **Production**: Production deployment (`docker-compose.yml`)

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
# IMPORTANT: Use secrets manager for production (AWS Secrets Manager, HashiCorp Vault, etc.)
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
# Use AWS Secrets Manager, HashiCorp Vault, or similar
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
- **Use secrets managers in production**: AWS Secrets Manager, HashiCorp Vault, Azure Key Vault, GCP Secret Manager
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

#### Issue 3: Health Checks Failing

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

