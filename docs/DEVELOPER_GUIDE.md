# Developer Guide

> Onboarding, development workflow, code quality, and local setup
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

# Developer Onboarding Guide

Complete guide for new developers to get started with the Data Interoperability Hub project (product brand: **Meshant** by default, configurable via `APP_NAME` / `VITE_APP_NAME`).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Development Environment](#development-environment)
4. [Docker Compose Setup](#docker-compose-setup)
5. [Local Development Environment](#local-development-environment)
6. [IDE Configuration](#ide-configuration)
7. [Running Services](#running-services)
8. [Service Debugging](#service-debugging)
9. [Service Testing](#service-testing)
10. [Code Quality](#code-quality)
11. [Common Tasks](#common-tasks)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python** 3.12+ - Programming language
- **Docker** 20.10+ - Container runtime
- **Docker Compose** 2.0+ - Container orchestration
- **Git** - Version control
- **Make** - Build automation (optional but recommended)

### Recommended Software

- **VS Code** - IDE with recommended extensions
- **PyCharm** - Alternative IDE
- **kubectl** - Kubernetes CLI (for K8s deployments)
- **pre-commit** - Git hooks for code quality

### Required Knowledge

- Python programming
- Django framework basics
- FastAPI basics
- Docker and containerization
- REST API concepts
- Git workflow

---

## Initial Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd DataInteroperabilityHub
```

### 2. Run Setup Script

```bash
# Automated setup (recommended)
./scripts/dev_setup.sh

# Or manual setup
make setup
```

The setup script will:
- Create Python virtual environment
- Install all dependencies
- Install pre-commit hooks
- Set up database (if PostgreSQL is running)

### 3. Configure Docker Compose for Development

The project uses `docker-compose.dev.yml` for local development with hot-reload and debug mode enabled.

```bash
# Set environment variable to use development compose file
export COMPOSE_FILE=docker-compose.dev.yml
export ENVIRONMENT=development

# Or create an alias in your shell profile (~/.bashrc or ~/.zshrc)
alias docker-compose-dev='COMPOSE_FILE=docker-compose.dev.yml docker compose'
```

### 4. Start Infrastructure Services

```bash
# Using development compose file
docker compose -f docker-compose.dev.yml up -d postgres redis minio fuseki

# Or use the alias (if configured)
docker-compose-dev up -d postgres redis minio fuseki

# Or use Makefile
make docker-up
```

### 5. Run Database Migrations

```bash
# Activate virtual environment
source venv/bin/activate

# Run migrations using Docker Compose
docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate

# Or run locally (if Django is installed)
python hub/manage.py migrate

# Or use Makefile
make migrate
```

### 6. Create Superuser (Optional)

```bash
# Using Docker Compose
docker compose -f docker-compose.dev.yml exec api-service python manage.py createsuperuser

# Or run locally
python hub/manage.py createsuperuser
```

---

## Development Environment

### Virtual Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Deactivate when done
deactivate
```

### Environment Variables

Create `.env.dev` file for local development:

```bash
# Database
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub
POSTGRES_DB=hub

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Services
DATACONTRACT_SERVICE_URL=http://localhost:8080
COMPLIANCE_SERVICE_URL=http://localhost:8082
DQ_SERVICE_URL=http://localhost:8083
SEMANTIC_SERVICE_URL=http://localhost:8081

# Prefect
PREFECT_API_URL=http://localhost:4200/api
PREFECT_API_KEY=your-api-key-here
PREFECT_DB_PASSWORD=prefect

# Logging
LOG_LEVEL=DEBUG
```

---

## Docker Compose Setup

### Understanding Docker Compose Files

The project provides three Docker Compose configurations:

1. **`docker-compose.dev.yml`** - Development environment (hot-reload, debug mode)
2. **`docker-compose.staging.yml`** - Staging environment (production-like)
3. **`docker-compose.yml`** - Production environment

For local development, always use `docker-compose.dev.yml`.

### Development Compose File Features

The development compose file (`docker-compose.dev.yml`) includes:

- **Hot-Reload**: Code changes are immediately reflected without rebuilding containers
- **Debug Mode**: Full debugging capabilities enabled (`DEBUG=True`)
- **Verbose Logging**: DEBUG level logging for detailed troubleshooting
- **Code Volumes**: Source code mounted for live editing
- **No Resource Limits**: Flexible resource usage for development
- **Separate Volumes**: Isolated development data (`pgdata-dev`, `redis-data-dev`, etc.)

### Starting Development Environment

```bash
# Start all services with development configuration
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Check service status
docker compose -f docker-compose.dev.yml ps

# Stop all services
docker compose -f docker-compose.dev.yml down

# Stop and remove volumes (WARNING: deletes all data)
docker compose -f docker-compose.dev.yml down -v
```

### Service Health Checks

```bash
# Run comprehensive health checks
./scripts/health-checks/health-check-all.sh

# Check specific service groups
./scripts/health-checks/health-check-workflow.sh
./scripts/health-checks/health-check-event-bus.sh
./scripts/health-checks/health-check-service-layer.sh

# Set environment for health checks
ENVIRONMENT=development ./scripts/health-checks/health-check-all.sh
```

### Development Network

All services run on the `hub-net-dev` network:

```bash
# Inspect network
docker network inspect hub-net-dev

# List containers on network
docker network inspect hub-net-dev --format '{{range .Containers}}{{.Name}} {{end}}'
```

### Development Volumes

Development uses separate volumes (prefixed with `-dev`):

- `pgdata-dev` - PostgreSQL data
- `redis-data-dev` - Redis data
- `minio-data-dev` - MinIO object storage
- `fuseki-data-dev` - Fuseki triple store
- `prometheus-data-dev` - Prometheus metrics
- `grafana-data-dev` - Grafana dashboards

```bash
# List development volumes
docker volume ls | grep -E "dev|hub"

# Inspect volume
docker volume inspect hub-pgdata-dev

# Backup volume
docker run --rm \
  -v hub-pgdata-dev:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/pgdata-dev-backup.tar.gz /data
```

### Infrastructure Services in Docker Compose

The development compose includes these infrastructure services:

#### PgBouncer (`pgbouncer`)
- **Purpose**: PostgreSQL connection pooling
- **Mode**: Transaction-mode (`pool_mode=transaction`)
- **Config**: `max_client_conn=200`, `default_pool_size=20`
- **Access**: Applications connect to PgBouncer (port 6432) instead of PostgreSQL directly
- **Why needed**: Prevents connection exhaustion from Django + RQ workers

#### AWS Secrets Manager (via LocalStack in dev)

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->
- **Purpose**: Secrets management, field-level encryption (AWS KMS)
- **Dev mode**: LocalStack provides a local AWS Secrets Manager emulator
- **Env vars**: `AWS_SECRETS_ENABLED=true`, `AWS_REGION=us-east-1`, `AWS_ENDPOINT_URL=http://localhost:4566`
- **Secrets path**: `hub/dev/` prefix

```bash
# Verify secrets are accessible (LocalStack)
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets --region us-east-1

# Read a secret (dev mode)
aws --endpoint-url=http://localhost:4566 secretsmanager get-secret-value --secret-id hub/dev/django --region us-east-1
```

#### OpenTelemetry Collector (`otel-collector`)
- **Purpose**: Collects traces, metrics, and logs from all services
- **Config**: `otel-collector-config.yaml`
- **Receivers**: OTLP (gRPC :4317, HTTP :4318)
- **Exporters**: Grafana Tempo (traces), Loki (logs), Prometheus (metrics)
- **Sampling**: Tail-based in production; always-on in development

#### Grafana Stack
- **Grafana** (port 3000): Dashboards for metrics, traces, logs
- **Tempo**: Distributed tracing backend (S3 storage in production)
- **Loki**: Log aggregation (S3 storage in production)
- **Prometheus**: Metrics collection and alerting

### AWS Secrets Manager Setup Instructions

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->
For local development, LocalStack emulates AWS Secrets Manager. For staging/production:

```bash
# Create a secret (first time only)
aws secretsmanager create-secret --name hub/<env>/django \
  --secret-string '{"SECRET_KEY":"<key>","JWT_SECRET_KEY":"<jwt-key>"}' \
  --region <region>

# Store database credentials
aws secretsmanager create-secret --name hub/<env>/postgres \
  --secret-string '{"host":"postgres","port":"5432","name":"hub","user":"hub","password":"<password>"}' \
  --region <region>

# Configure IRSA for in-cluster access (see AWS docs for IAM role setup)
# Configure GitHub OIDC→AWS STS for CI/CD access
```

### Helm Deployment (Kubernetes)

```bash
# Install/upgrade the Meshant Helm chart
helm upgrade --install meshant ./helm \
  --namespace meshant \
  --create-namespace \
  -f helm/values.yaml \
  -f helm/values.staging.yaml  # or values.production.yaml

# Verify deployment
kubectl get pods -n meshant
kubectl get hpa -n meshant

# Check PDB status
kubectl get pdb -n meshant

# View logs
kubectl logs -n meshant deployment/api -f
```

The Helm chart deploys 23+ resources including deployments, HPAs, PDBs, NetworkPolicies, ServiceAccounts, and ExternalSecrets.

---

## Local Development Environment

### Complete Development Setup

#### Step 1: Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd DataInteroperabilityHub

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

#### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.dev.example .env.dev

# Edit .env.dev with your local settings
# At minimum, set:
# - SECRET_KEY (generate a random key)
# - Database credentials
# - Service URLs
```

#### Step 3: Start Docker Compose Services

```bash
# Start all services with development configuration
docker compose -f docker-compose.dev.yml up -d

# Wait for services to be healthy (about 30-60 seconds)
sleep 30

# Verify services are running
docker compose -f docker-compose.dev.yml ps

# Run health checks
./scripts/health-checks/health-check-all.sh
```

#### Step 4: Initialize Database

```bash
# Run migrations
docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate

# Create superuser
docker compose -f docker-compose.dev.yml exec api-service python manage.py createsuperuser

# Load development fixtures (if available)
docker compose -f docker-compose.dev.yml exec api-service python manage.py loaddata fixtures/dev_data.json
```

#### Step 5: Verify Setup

```bash
# Test API endpoint
curl http://localhost:8000/health

# Test worker health
curl http://localhost:8080/healthz

# Access Django admin (if superuser created)
open http://localhost:8000/admin

# Access API documentation
open http://localhost:8000/api/docs
```

### Hot-Reload Development

With `docker-compose.dev.yml`, code changes are automatically reflected:

```bash
# 1. Edit code in your local editor
vim hub/apps/contracts/views.py

# 2. Django development server automatically reloads
# Check logs to see reload:
docker compose -f docker-compose.dev.yml logs -f api-service

# 3. Test your changes
curl http://localhost:8000/api/contracts/
```

**Services with Hot-Reload:**
- `api-service` (Django runserver)
- `worker-service` (if using auto-reload)
- `workflow-engine-service` (if using auto-reload)
- All FastAPI microservices with code volumes mounted

### Development Workflow

#### Daily Development

```bash
# 1. Start environment
docker compose -f docker-compose.dev.yml up -d

# 2. Make code changes (hot-reload enabled)

# 3. Run tests
pytest

# 4. Check logs
docker compose -f docker-compose.dev.yml logs -f api-service

# 5. Stop environment (when done)
docker compose -f docker-compose.dev.yml down
```

#### Making Code Changes

```bash
# Edit code locally
# Changes are automatically reflected (hot-reload)

# If hot-reload doesn't work, restart service
docker compose -f docker-compose.dev.yml restart api-service

# Or rebuild service (if Dockerfile changed)
docker compose -f docker-compose.dev.yml up -d --build api-service
```

### Accessing Services

| Service | URL | Description |
|---------|-----|-------------|
| API Service | http://localhost:8000 | Django API |
| API Docs | http://localhost:8000/api/docs | Swagger UI |
| Django Admin | http://localhost:8000/admin | Admin interface |
| Worker Health | http://localhost:8080/healthz | Worker health check |
| Workflow Engine | http://localhost:8088/healthz | Workflow engine health |
| Grafana | http://localhost:3000 | Monitoring dashboards |
| Jaeger UI | http://localhost:16686 | Distributed tracing |
| Prometheus | http://localhost:9090 | Metrics |
| MinIO Console | http://localhost:9001 | Object storage console |
| Prefect UI | http://localhost:4201 | Workflow orchestration UI |

### Environment Variables

Development environment variables are set in `docker-compose.dev.yml`:

- `ENVIRONMENT=development`
- `DEBUG=True`
- `LOG_LEVEL=DEBUG`

These can be overridden via `.env.dev` file or environment variables.

---

## IDE Configuration

### VS Code

**Recommended Extensions:**
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)
- Ruff (charliermarsh.ruff)
- Docker (ms-azuretools.vscode-docker)
- YAML (redhat.vscode-yaml)

**Configuration:**
- Settings are in `.vscode/settings.json`
- Launch configurations in `.vscode/launch.json`
- Recommended extensions in `.vscode/extensions.json`

**Usage:**
1. Open project in VS Code
2. Install recommended extensions (prompt will appear)
3. Select Python interpreter: `venv/bin/python`
4. Use F5 to start debugging

### PyCharm

**Configuration:**
1. Open project in PyCharm
2. Configure Python interpreter: `venv/bin/python`
3. Mark `hub/` as Sources Root
4. Configure Django: Settings → Languages & Frameworks → Django
   - Django project root: `hub/`
   - Settings: `hub.settings`
   - Manage script: `hub/manage.py`

### Dev Containers

**VS Code Dev Containers:**
1. Install "Dev Containers" extension
2. Open Command Palette (Ctrl+Shift+P)
3. Select "Dev Containers: Reopen in Container"
4. Wait for container to build and start

**Configuration:** `.devcontainer/devcontainer.json`

---

## Running Services

### All Services (Docker Compose)

```bash
# Start all services with development configuration
docker compose -f docker-compose.dev.yml up -d

# View logs (all services)
docker compose -f docker-compose.dev.yml logs -f

# View logs for specific service
docker compose -f docker-compose.dev.yml logs -f api-service

# Stop all services
docker compose -f docker-compose.dev.yml down

# Stop and remove volumes (WARNING: deletes all data)
docker compose -f docker-compose.dev.yml down -v
```

### Starting Services in Order

For proper startup order:

```bash
# 1. Start infrastructure
docker compose -f docker-compose.dev.yml up -d postgres redis minio fuseki

# 2. Wait for infrastructure to be healthy
sleep 10

# 3. Start core services
docker compose -f docker-compose.dev.yml up -d api-service worker-service

# 4. Start workflow services
docker compose -f docker-compose.dev.yml up -d workflow-engine-service workflow-registry-service

# 5. Start event bus services
docker compose -f docker-compose.dev.yml up -d event-bus-health-service event-schema-registry-service

# 6. Start microservices
docker compose -f docker-compose.dev.yml up -d \
  semantic-service dq-service compliance-service datacontract-service \
  search-service observability-service webhook-service prefect-integration-service

# 7. Start monitoring
docker compose -f docker-compose.dev.yml up -d prometheus grafana jaeger alertmanager

# 8. Start API gateway
docker compose -f docker-compose.dev.yml up -d traefik
```

### Individual Services (Development)

```bash
# Run API service
./scripts/dev_run.sh api

# Run specific FastAPI service
./scripts/dev_run.sh prefect-integration --reload

# Available services:
# - api
# - worker
# - datacontract
# - compliance
# - dq
# - semantic
# - prefect-integration
# - search
# - observability
# - webhook
```

### Using Makefile

```bash
# Start infrastructure only
make docker-up

# Start all services
make docker-up-all

# Run Django server
make runserver

# View Docker logs
make docker-logs
```

---

## Service Debugging

### Debugging Django Services (API, Worker)

#### Using VS Code Debugger

1. **Set Breakpoints**: Click in the gutter next to line numbers
2. **Start Debugging**: Press F5 or use Debug → Start Debugging
3. **Attach to Running Container**:
   ```json
   {
     "name": "Python: Attach to Container",
     "type": "python",
     "request": "attach",
     "connect": {
       "host": "localhost",
       "port": 5678
     },
     "pathMappings": [
       {
         "localRoot": "${workspaceFolder}",
         "remoteRoot": "/app"
       }
     ]
   }
   ```

#### Using Python Debugger (pdb)

```bash
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use breakpoint() (Python 3.7+)
breakpoint()

# Access container shell
docker compose -f docker-compose.dev.yml exec api-service bash

# Run Django shell with debugger
docker compose -f docker-compose.dev.yml exec api-service python -m pdb manage.py shell
```

#### Debugging Django Views

```bash
# Run Django shell
docker compose -f docker-compose.dev.yml exec api-service python manage.py shell

# Import and test views
from hub.apps.contracts.views import ContractListView
from django.test import RequestFactory

factory = RequestFactory()
request = factory.get('/api/contracts/')
response = ContractListView.as_view()(request)
```

#### Debugging Worker Jobs

```bash
# Check worker logs
docker compose -f docker-compose.dev.yml logs -f worker-service

# Access worker container
docker compose -f docker-compose.dev.yml exec worker-service bash

# Check job queue status
docker compose -f docker-compose.dev.yml exec worker-service python -c "from django_rq import get_worker; print(get_worker().queues)"
```

### Debugging FastAPI Services

#### Using VS Code Debugger

1. **Configure Launch**: Add to `.vscode/launch.json`:
   ```json
   {
     "name": "Python: FastAPI",
     "type": "python",
     "request": "launch",
     "module": "uvicorn",
     "args": [
       "services.semantic-service.main:app",
       "--reload",
       "--host", "0.0.0.0",
       "--port", "8081"
     ],
     "jinja": true,
     "justMyCode": false
   }
   ```

#### Using Python Debugger

```bash
# Add breakpoint in FastAPI code
import pdb; pdb.set_trace()

# Or use breakpoint()
breakpoint()

# Access container shell
docker compose -f docker-compose.dev.yml exec semantic-service bash

# Run with debugger
docker compose -f docker-compose.dev.yml exec semantic-service python -m pdb -m uvicorn main:app --host 0.0.0.0 --port 8081
```

#### Debugging API Endpoints

```bash
# Test endpoint with curl
curl -v http://localhost:8081/health

# Test with request body
curl -X POST http://localhost:8081/api/endpoint \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# Check service logs
docker compose -f docker-compose.dev.yml logs -f semantic-service
```

### Debugging Workflow Engine

#### Viewing Workflow Execution

```bash
# Check workflow engine logs
docker compose -f docker-compose.dev.yml logs -f workflow-engine-service

# Access workflow engine container
docker compose -f docker-compose.dev.yml exec workflow-engine-service bash

# Check workflow state in database
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub -c "SELECT * FROM workflow_instances ORDER BY created_at DESC LIMIT 10;"
```

#### Debugging Workflow Steps

```bash
# Check workflow step logs
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub -c "SELECT * FROM workflow_steps WHERE status = 'FAILED' ORDER BY created_at DESC LIMIT 10;"

# View workflow execution details
docker compose -f docker-compose.dev.yml exec api-service python manage.py shell
```

```python
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStep

# Get failed workflow
workflow = WorkflowInstance.objects.filter(status='FAILED').first()
print(workflow.error_message)

# Get failed steps
steps = WorkflowStep.objects.filter(workflow_instance=workflow, status='FAILED')
for step in steps:
    print(f"Step: {step.name}, Error: {step.error_message}")
```

### Debugging Event Bus

#### Checking Event Bus Health

```bash
# Check event bus health service
curl http://localhost:8090/healthz

# Check event schema registry
curl http://localhost:8091/health

# View event bus logs
docker compose -f docker-compose.dev.yml logs -f event-bus-health-service
```

#### Debugging Event Publishing

```bash
# Check Redis for events
docker compose -f docker-compose.dev.yml exec redis redis-cli

# In Redis CLI:
KEYS event:*
GET event:<event-id>
MONITOR  # Watch all commands
```

#### Debugging Event Consumption

```bash
# Check event bus logs
docker compose -f docker-compose.dev.yml logs -f event-bus-health-service

# Check for failed events
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub -c "SELECT * FROM event_log WHERE status = 'FAILED' ORDER BY created_at DESC LIMIT 10;"
```

### Debugging Database Issues

#### Checking Database Connection

```bash
# Test PostgreSQL connection
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U hub

# Connect to database
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub

# Check active connections
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub -c "SELECT * FROM pg_stat_activity;"
```

#### Debugging Queries

```bash
# Enable query logging in Django
# In settings.py or .env.dev:
# LOGGING['loggers']['django.db.backends'] = {'level': 'DEBUG'}

# Check slow queries
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

#### Debugging Migrations

```bash
# Check migration status
docker compose -f docker-compose.dev.yml exec api-service python manage.py showmigrations

# Check for unapplied migrations
docker compose -f docker-compose.dev.yml exec api-service python manage.py showmigrations --plan

# Debug migration issues
docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate --verbosity=2
```

### Debugging Network Issues

#### Checking Service Communication

```bash
# Test connectivity between services
docker compose -f docker-compose.dev.yml exec api-service ping postgres
docker compose -f docker-compose.dev.yml exec api-service ping redis

# Test HTTP connectivity
docker compose -f docker-compose.dev.yml exec api-service curl http://semantic-service:8081/health
docker compose -f docker-compose.dev.yml exec api-service curl http://worker-service:8080/healthz
```

#### Checking DNS Resolution

```bash
# Test DNS resolution
docker compose -f docker-compose.dev.yml exec api-service nslookup postgres
docker compose -f docker-compose.dev.yml exec api-service nslookup redis

# Check /etc/hosts
docker compose -f docker-compose.dev.yml exec api-service cat /etc/hosts
```

### Debugging Performance Issues

#### Monitoring Resource Usage

```bash
# Check container resource usage
docker stats

# Check specific container
docker stats hub-dev-api

# Check disk usage
docker system df
docker system df -v
```

#### Profiling Python Code

```bash
# Use cProfile for profiling
docker compose -f docker-compose.dev.yml exec api-service python -m cProfile -o profile.stats manage.py shell

# Analyze profile
docker compose -f docker-compose.dev.yml exec api-service python -m pstats profile.stats
```

### Debugging Tools

#### Using Docker Inspect

```bash
# Inspect container
docker inspect hub-dev-api

# Check container configuration
docker inspect hub-dev-api --format '{{.Config.Env}}'

# Check network configuration
docker inspect hub-dev-api --format '{{.NetworkSettings.Networks}}'
```

#### Using Docker Exec

```bash
# Access container shell
docker compose -f docker-compose.dev.yml exec api-service bash

# Run commands in container
docker compose -f docker-compose.dev.yml exec api-service python manage.py shell
docker compose -f docker-compose.dev.yml exec api-service env
docker compose -f docker-compose.dev.yml exec api-service ps aux
```

---

## Service Testing

### Running Tests in Docker Compose Environment

#### Running All Tests

```bash
# Run all tests in Docker Compose environment
docker compose -f docker-compose.dev.yml exec api-service pytest

# Run with coverage
docker compose -f docker-compose.dev.yml exec api-service pytest --cov=hub --cov-report=html

# Run specific test file
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/test_docker_compose_dev.py
```

#### Running Unit Tests

```bash
# Run unit tests only
docker compose -f docker-compose.dev.yml exec api-service pytest tests/unit/

# Run specific unit test
docker compose -f docker-compose.dev.yml exec api-service pytest tests/unit/test_contracts.py::TestContractService
```

#### Running Integration Tests

```bash
# Run integration tests
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/

# Run Docker Compose integration tests
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/test_docker_compose_dev.py -v

# Run workflow integration tests
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/test_workflow.py -v
```

### Testing Individual Services

#### Testing API Service

```bash
# Run API service tests
docker compose -f docker-compose.dev.yml exec api-service pytest hub/apps/contracts/tests/

# Test specific endpoint
docker compose -f docker-compose.dev.yml exec api-service pytest hub/apps/contracts/tests/test_views.py::TestContractListView

# Test with coverage
docker compose -f docker-compose.dev.yml exec api-service pytest --cov=hub.apps.contracts hub/apps/contracts/tests/
```

#### Testing Worker Service

```bash
# Run worker tests
docker compose -f docker-compose.dev.yml exec worker-service pytest services/worker/tests/

# Test job execution
docker compose -f docker-compose.dev.yml exec worker-service pytest services/worker/tests/test_jobs.py
```

#### Testing Workflow Engine

```bash
# Run workflow engine tests
docker compose -f docker-compose.dev.yml exec workflow-engine-service pytest services/workflow-engine/tests/

# Test workflow execution
docker compose -f docker-compose.dev.yml exec workflow-engine-service pytest services/workflow-engine/tests/test_execution.py
```

#### Testing Microservices

```bash
# Test semantic service
docker compose -f docker-compose.dev.yml exec semantic-service pytest services/semantic-service/tests/

# Test DQ service
docker compose -f docker-compose.dev.yml exec dq-service pytest services/dq-service/tests/

# Test compliance service
docker compose -f docker-compose.dev.yml exec compliance-service pytest services/compliance-service/tests/
```

### Testing Service Integration

#### Testing Service-to-Service Communication

```bash
# Test API → Semantic Service
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/test_semantic_integration.py

# Test API → DQ Service
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/test_dq_integration.py

# Test Workflow → Services
docker compose -f docker-compose.dev.yml exec workflow-engine-service pytest tests/integration/test_workflow_integration.py
```

#### Testing Event Bus Integration

```bash
# Test event publishing
docker compose -f docker-compose.dev.yml exec api-service pytest tests/integration/test_event_bus.py::TestEventPublishing

# Test event consumption
docker compose -f docker-compose.dev.yml exec worker-service pytest tests/integration/test_event_bus.py::TestEventConsumption
```

### Testing with Test Data

#### Loading Test Fixtures

```bash
# Load test fixtures
docker compose -f docker-compose.dev.yml exec api-service python manage.py loaddata fixtures/test_data.json

# Load specific fixture
docker compose -f docker-compose.dev.yml exec api-service python manage.py loaddata fixtures/test_contracts.json
```

#### Creating Test Data

```bash
# Use Django shell to create test data
docker compose -f docker-compose.dev.yml exec api-service python manage.py shell
```

```python
from hub.apps.contracts.models import Contract
from hub.apps.assets.models import Asset

# Create test contract
contract = Contract.objects.create(
    name="Test Contract",
    version="1.0.0",
    # ... other fields
)

# Create test asset
asset = Asset.objects.create(
    name="Test Asset",
    contract=contract,
    # ... other fields
)
```

### Testing Health Checks

#### Testing Service Health Endpoints

```bash
# Test API health
curl http://localhost:8000/health

# Test worker health
curl http://localhost:8080/healthz

# Test workflow engine health
curl http://localhost:8088/healthz

# Test all services
./scripts/health-checks/health-check-all.sh
```

#### Testing Health Check Scripts

```bash
# Run health check script tests
pytest tests/scripts/test_health_check_scripts.py -v

# Test specific health check script
./scripts/health-checks/health-check-all.sh
./scripts/health-checks/health-check-workflow.sh
./scripts/health-checks/health-check-event-bus.sh
./scripts/health-checks/health-check-service-layer.sh
```

### Testing Database Operations

#### Testing Migrations

```bash
# Test migration creation
docker compose -f docker-compose.dev.yml exec api-service python manage.py makemigrations --dry-run

# Test migration application
docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate --plan

# Test migration rollback
docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate <app_name> <previous_migration>
```

#### Testing Database Queries

```bash
# Run database query tests
docker compose -f docker-compose.dev.yml exec api-service pytest hub/apps/contracts/tests/test_models.py

# Test with database transactions
docker compose -f docker-compose.dev.yml exec api-service pytest --db-transactions hub/apps/contracts/tests/
```

### Testing Performance

#### Load Testing

```bash
# Use Locust for load testing (if installed)
docker compose -f docker-compose.dev.yml exec api-service locust -f tests/load/locustfile.py

# Or use Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/contracts/
```

#### Performance Testing

```bash
# Run performance tests
docker compose -f docker-compose.dev.yml exec api-service pytest tests/performance/ -v

# Profile test execution
docker compose -f docker-compose.dev.yml exec api-service pytest --profile tests/performance/
```

### Test Coverage

#### Generating Coverage Reports

```bash
# Generate coverage report
docker compose -f docker-compose.dev.yml exec api-service pytest --cov=hub --cov=services --cov-report=html

# View coverage report
open htmlcov/index.html

# Generate coverage XML (for CI/CD)
docker compose -f docker-compose.dev.yml exec api-service pytest --cov=hub --cov=services --cov-report=xml
```

#### Coverage Targets

- **Unit Tests**: 100% coverage target
- **Integration Tests**: 95%+ coverage target
- **E2E Tests**: 100% journey coverage target

### Continuous Testing

#### Running Tests on Code Changes

```bash
# Use pytest-watch for auto-testing
docker compose -f docker-compose.dev.yml exec api-service ptw --runner "pytest -v"

# Or use entr for file watching
find . -name "*.py" | entr docker compose -f docker-compose.dev.yml exec api-service pytest
```

#### Pre-commit Test Hooks

Tests run automatically on commit via pre-commit hooks:

```bash
# Run tests before commit
pre-commit run --hook-stage pre-commit

# Or configure git hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
docker compose -f docker-compose.dev.yml exec api-service pytest
EOF
chmod +x .git/hooks/pre-commit
```

---

## Testing (Legacy - See Service Testing Section)

> **Note**: For comprehensive testing procedures, see the [Service Testing](#service-testing) section above.

### Quick Test Commands

```bash
# Run all tests locally
pytest

# Run with coverage
pytest --cov=hub --cov=services --cov-report=html

# Run in Docker Compose environment
docker compose -f docker-compose.dev.yml exec api-service pytest

# Use test scripts
./scripts/dev_test.sh --coverage
```

---

## Code Quality

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:

```bash
# Install hooks (done during setup)
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run
```

**Hooks include:**
- Trailing whitespace removal
- End of file fixer
- YAML/JSON/TOML validation
- Black code formatting
- Ruff linting
- MyPy type checking

### Code Formatting

```bash
# Format code with Black
black .

# Check formatting
black --check .

# Or use Makefile
make format
```

### Linting

```bash
# Run Ruff
ruff check .

# Auto-fix issues
ruff check --fix .

# Or use Makefile
make lint
```

### Type Checking

```bash
# Run MyPy
mypy hub/ services/

# Or use Makefile
make type-check
```

---

## Common Tasks

### Database Operations

```bash
# Create migrations
python hub/manage.py makemigrations

# Apply migrations
python hub/manage.py migrate

# Show migration status
python hub/manage.py showmigrations
```

### Service Management

```bash
# Start specific service
docker compose up -d api-service

# Restart service
docker compose restart api-service

# View service logs
docker compose logs -f api-service

# Check service health
curl http://localhost:8000/health
```

### Dependency Management

```bash
# Update requirements
pip freeze > requirements.txt

# Install new package
pip install package-name
pip freeze > requirements.txt

# Update all dependencies (via Dependabot)
# Dependabot creates PRs automatically
```

---

## Troubleshooting

### Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check connection
docker compose exec postgres psql -U hub -d hub -c "SELECT 1"

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d postgres
python hub/manage.py migrate
```

### Port Conflicts

```bash
# Check what's using a port
lsof -i :8000

# Change port in docker-compose.yml or .env.dev
# Example: API_PORT=8001
```

### Pre-commit Hook Failures

```bash
# Skip hooks for this commit (not recommended)
git commit --no-verify

# Fix issues and commit again
pre-commit run --all-files
git add .
git commit
```

### Service Won't Start

```bash
# Check logs
docker compose logs <service-name>

# Check health
docker compose ps

# Restart service
docker compose restart <service-name>
```

---

## Next Steps

1. ✅ Environment set up
2. ✅ Services running
3. ⏳ Read architecture documentation
4. ⏳ Review codebase structure
5. ⏳ Pick a first task/issue
6. ⏳ Set up branch and start coding

---

## Resources

### Documentation

- **Architecture**: `docs/SERVICES_ARCHITECTURE.md`
- **API Documentation**: `docs/API_DOCUMENTATION.md`
- **Testing Guide**: `docs/TEST_INFRASTRUCTURE.md`
- **Deployment Guide**: `docs/DOCKER_COMPOSE_DEPLOYMENT.md`
- **Development Deployment**: `docs/DEVELOPMENT_DEPLOYMENT.md`
- **Staging Deployment**: `docs/STAGING_DEPLOYMENT.md`
- **Docker Compose Structure**: `docs/DOCKER_COMPOSE_STRUCTURE.md`
- **Health Check Scripts**: `docs/HEALTH_CHECK_SCRIPTS.md`

### Scripts

- **Health Checks**: `scripts/health-checks/`
- **Deployment**: `scripts/deploy-docker-compose.sh`
- **Development**: `scripts/dev_setup.sh`, `scripts/dev_run.sh`, `scripts/dev_test.sh`

### Docker Compose Files

- **Development**: `docker-compose.dev.yml`
- **Staging**: `docker-compose.staging.yml`
- **Production**: `docker-compose.yml`

---

## Getting Help

- **Issues**: Create an issue on GitHub
- **Questions**: Ask in team chat or create discussion
- **Code Review**: Submit PR for review

---

**Last Updated:** 2025-01-15

---

## Quick Reference

### Essential Commands

```bash
# Start development environment
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f api-service

# Run tests
docker compose -f docker-compose.dev.yml exec api-service pytest

# Run health checks
./scripts/health-checks/health-check-all.sh

# Stop environment
docker compose -f docker-compose.dev.yml down
```

### Common Debugging Commands

```bash
# Access container shell
docker compose -f docker-compose.dev.yml exec api-service bash

# Check service logs
docker compose -f docker-compose.dev.yml logs -f <service-name>

# Check service health
curl http://localhost:<port>/health

# Check database
docker compose -f docker-compose.dev.yml exec postgres psql -U hub -d hub
```

### Common Testing Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hub --cov-report=html

# Run specific test
pytest tests/integration/test_docker_compose_dev.py::TestDockerComposeDev::test_dev_compose_file_exists

# Run in Docker
docker compose -f docker-compose.dev.yml exec api-service pytest
```

---

# Development Guide

Complete guide for developing the Data Interoperability Hub.

## Development Environment Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Git
- Make (optional)

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd DataInteroperabilityHub

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Option A: Run all services via Docker Compose (recommended)
docker compose -f docker-compose.dev.yml up -d

# Option B: Run only infrastructure (postgres, Redis instances, MinIO, Fuseki)
docker compose -f docker-compose.dev.yml up -d postgres redis-cache redis-queue redis-events redis-channels minio fuseki

# Run migrations (if not using full stack, or after first bring-up)
cd hub && python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

**Run all services (production-style compose):**

```bash
# Full stack: API, workers, frontend, gateways, Prefect, monitoring, etc.
docker compose up -d
```

See `docs/DOCKER_COMPOSE_DEPLOYMENT.md` for full deployment steps and service list.

### Production and staging security

For **production and staging**:

- **MUST set** `SECRET_KEY` and `JWT_SECRET_KEY` via environment (or a secret manager). Never use the development default values. Django fails startup with `ENVIRONMENT=production` if these are unset or equal the dev defaults.
- **Never commit** production or staging secrets; use a secret manager or env in CI/CD.
- **CORS**: Use explicit allowed origins only (not `*`). See `docs/SECURITY.md` for Django `CORS_ALLOWED_ORIGINS` and Traefik CORS.

Full requirements and validation: **`docs/SECURITY.md`**.

## Development Workflow

### Code Structure

```
hub/
├── apps/              # Django apps
│   ├── contracts/    # Contract management
│   ├── assets/        # Asset catalog
│   ├── datasets/      # Dataset management
│   └── ...
├── core/              # Core functionality
│   ├── services/      # Service layer
│   ├── events/        # Event system
│   └── ...
└── settings.py        # Django settings
```

### Creating New Features

1. **Create Django App** (if needed)
   ```bash
   python manage.py startapp myapp
   ```

2. **Create Models**
   ```python
   # hub/apps/myapp/models.py
   from django.db import models
   from hub.apps.core.models import BaseModel

   class MyModel(BaseModel):
       name = models.CharField(max_length=255)
   ```

3. **Create Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Create Service Layer**
   ```python
   # hub/apps/myapp/services.py
   from hub.apps.core.services import BaseService

   class MyService(BaseService):
       def create_item(self, tenant_id, data):
           # Business logic here
           pass
   ```

5. **Create API Views**
   ```python
   # hub/apps/myapp/views.py
   from rest_framework import viewsets
   from hub.apps.myapp.serializers import MySerializer

   class MyViewSet(viewsets.ModelViewSet):
       serializer_class = MySerializer
       # View logic here
   ```

6. **Create Tests**
   ```python
   # hub/apps/myapp/tests.py
   import pytest

   @pytest.mark.django_db
   def test_create_item():
       # Test logic here
       pass
   ```

## Coding Standards

### Python Style

Follow PEP 8 and use:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type check
mypy .
```

### Django Best Practices

1. **Use Service Layer**: Business logic in services, not views
2. **Use Serializers**: Data validation in serializers
3. **Use Permissions**: Implement proper permissions
4. **Use Signals Sparingly**: Prefer explicit calls
5. **Use Migrations**: Never edit migrations manually

### Code Organization

```
app/
├── models.py          # Database models
├── serializers.py    # API serializers
├── services.py       # Business logic
├── views.py          # API views
├── urls.py           # URL routing
├── permissions.py    # Custom permissions
└── tests/            # Tests
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

## Service Layer Pattern

All business logic should be in service classes:

```python
from hub.apps.core.services import BaseService
from hub.apps.core.exceptions import ValidationError

class ContractService(BaseService):
    def create_contract(self, tenant_id, user_id, contract_data):
        # Validate tenant
        tenant = self.get_tenant_or_raise(tenant_id)

        # Validate data
        if not contract_data.get('name'):
            raise ValidationError('Contract name is required')

        # Create contract
        contract = Contract.objects.create(
            tenant=tenant,
            created_by_id=user_id,
            **contract_data
        )

        # Emit event
        self.emit_event('contract.created', contract.id)

        return contract
```

### Service Layer Consistency (Phase 24.7)

**CRITICAL**: All create/update/delete operations for domain resources MUST go through a service layer. Views use serializers for request validation only.

**Rule**: No direct `serializer.save()` in views for writes. All mutations go through service layer methods that:
- Apply business rules validation
- Emit audit events once per mutation
- Handle transaction boundaries
- Publish domain events

**Pattern**:
```python
# ✅ CORRECT: Use service layer
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    service = MyService(tenant_id=tenant_id, user_id=str(request.user.id))
    resource = service.create_resource(
        tenant_id=tenant_id,
        user_id=str(request.user.id),
        **serializer.validated_data,
    )
    return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)

# ❌ WRONG: Direct serializer.save() bypasses business rules and audit
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    resource = serializer.save()  # ❌ Bypasses service layer
    return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)
```

**Examples**:
- `ScheduledIngestionViewSet`: Uses `IngestionService.create_scheduled_ingestion()`, `IngestionService.update_scheduled_ingestion()`, and `IngestionService.delete_scheduled_ingestion()`
- `UserViewSet`: Uses `UserService.create_user()`, `UserService.update_user()`, and `UserService.delete_user()`
- `APIKeyViewSet`: Uses `APIKeyService.create_api_key()` and `APIKeyService.delete_api_key()`

**Note**: Serializers are still used for request validation and response serialization. The service layer handles the actual database mutations.

See `docs/BUSINESS_LOGIC_INTEGRATION.md` for complete service layer patterns and examples.

## Event-Driven Development

### Emitting Events

```python
from hub.apps.core.events import emit_event

emit_event('contract.created', contract_id=contract.id, data={...})
```

### Handling Events

```python
from hub.apps.core.events import event_handler

@event_handler('contract.created')
def handle_contract_created(event):
    contract_id = event.data['contract_id']
    # Handle event
    pass
```

## Testing

### Testing Principles

**CRITICAL: No Mocks/Stubs for Core Behavior**

This project follows a strict principle: **no mocks or stubs for core platform behavior**. Tests MUST use real implementations to ensure reliability and catch real issues.

#### Core Behavior That MUST NOT Be Mocked

The following core platform behaviors MUST use real implementations in tests:

1. **Tenant Resolution**
   - ✅ **MUST use**: `get_request_tenant_id()` and `get_request_tenant()` from `hub.apps.tenants.request_tenant`
   - ❌ **MUST NOT mock**: Tenant resolution logic, `request.tenant_id`, `user.tenant`, or tenant lookup
   - **Rationale**: Tenant isolation is critical for security; mocking can hide real isolation bugs

2. **Business Rules**
   - ✅ **MUST use**: Real `BusinessRules` classes (e.g., `AssetBusinessRules`, `ContractBusinessRules`)
   - ❌ **MUST NOT mock**: Business rule validation, permission checks, or business logic
   - **Rationale**: Business rules enforce critical constraints; mocking can allow invalid states

3. **Service Layer**
   - ✅ **MUST use**: Real service classes (e.g., `AssetService`, `ContractService`, `DatasetService`)
   - ❌ **MUST NOT mock**: Service layer methods, CRUD operations, or service-to-service communication within the platform
   - **Rationale**: Service layer contains core business logic; mocking can hide integration issues

4. **Database Operations**
   - ✅ **MUST use**: Real Django models, real database (via `@pytest.mark.django_db` or `TestCase`)
   - ❌ **MUST NOT mock**: Model methods, querysets, database queries, or ORM operations
   - **Rationale**: Database constraints and relationships must be tested; mocking can hide data integrity issues

5. **Authentication & Authorization**
   - ✅ **MUST use**: Real authentication (via `APIClient.force_authenticate()` or real tokens)
   - ❌ **MUST NOT mock**: User authentication, permission checks, or authorization logic
   - **Rationale**: Security is critical; mocking can hide authorization bugs

#### When Mocking Is Acceptable

Mocking is ONLY acceptable at **external process boundaries**:

1. **External HTTP Services** (when not running in test environment)
   - External DQ service HTTP calls (if service not available in test env)
   - External Compliance service HTTP calls (if service not available in test env)
   - External Semantic service HTTP calls (if service not available in test env)
   - **Note**: If services ARE available (via Docker Compose), use real services

2. **External Third-Party APIs**
   - Payment gateways
   - Email services
   - SMS services
   - External OAuth providers

3. **Time-Dependent Operations** (when testing time-sensitive logic)
   - `time.time()`, `datetime.now()` for testing expiration, scheduling
   - **Note**: Prefer using Django's `timezone.now()` with test fixtures when possible

4. **File System Operations** (when testing file handling)
   - External file storage (S3, GCS) if not available in test env
   - **Note**: Use MinIO or local file storage in test environment when possible

#### Example: Correct Test Pattern

```python
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from hub.apps.tenants.request_tenant import get_request_tenant_id
from hub.apps.assets.services import AssetService
from hub.apps.assets.models import Asset

@pytest.mark.django_db(transaction=True)
class AssetViewSetTest(TestCase):
    """Test AssetViewSet with real services (no mocks)."""

    def setUp(self):
        """Set up test fixtures with real DB."""
        self.client = APIClient()
        self.tenant1 = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
        )
        self.user1 = User.objects.create_user(
            email="user1@test.com",
            password="testpass123",
            tenant=self.tenant1,
        )
        self.client.force_authenticate(user=self.user1)

    def test_asset_list_follows_tenant_isolation(self):
        """Test that asset list respects tenant isolation."""
        # Create asset in tenant1 (real DB operation)
        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="test-asset",
            name="Test Asset",
            domain="test",
        )

        # Create asset in tenant2 (real DB operation)
        tenant2 = Tenant.objects.create(name="Tenant 2", slug="tenant-2")
        asset2 = Asset.objects.create(
            tenant=tenant2,
            key="test-asset-2",
            name="Test Asset 2",
            domain="test",
        )

        # Make API request (real request, real view, real service)
        response = self.client.get("/api/v1/assets/")

        # Verify tenant isolation (real queryset filtering)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in response.data.get("results", response.data)]
        self.assertIn(str(asset1.id), ids)
        self.assertNotIn(str(asset2.id), ids)

    def test_asset_create_uses_real_service(self):
        """Test asset creation uses real service layer."""
        # Make API request (real service will be called)
        response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "new-asset",
                "name": "New Asset",
                "domain": "test",
            },
            format="json",
        )

        # Verify creation (real DB query)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        asset = Asset.objects.get(key="new-asset")
        self.assertEqual(asset.tenant_id, self.tenant1.id)

        # Verify tenant resolution used real helper (not mocked)
        # This is implicit - if mocked, tenant isolation would fail
```

#### Example: Incorrect Test Pattern (DO NOT DO THIS)

```python
# ❌ WRONG: Mocking tenant resolution
from unittest.mock import patch, Mock

@patch('hub.apps.tenants.request_tenant.get_request_tenant_id')
def test_asset_list(mock_get_tenant_id):
    mock_get_tenant_id.return_value = "fake-tenant-id"
    # This hides real tenant isolation bugs!

# ❌ WRONG: Mocking service layer
@patch('hub.apps.assets.services.AssetService.create_asset')
def test_asset_create(mock_create):
    mock_create.return_value = Mock(id="fake-id")
    # This hides real service logic bugs!

# ❌ WRONG: Mocking business rules
@patch('hub.apps.assets.business_rules.AssetBusinessRules.validate')
def test_asset_validation(mock_validate):
    mock_validate.return_value = True
    # This allows invalid data to pass!
```

#### Migration Strategy

For existing tests that use mocks:

1. **Identify mocked core behavior**: Find tests mocking tenant resolution, business rules, or services
2. **Replace with real implementations**: Use real DB, real services, real business rules
3. **Fix root causes**: If tests fail after removing mocks, fix the underlying issues (don't add more mocks)
4. **Verify isolation**: Ensure tests are properly isolated using Django's test framework

**Reference Implementations**:
- ✅ **Scheduled Ingestion Tests** (`hub/apps/scheduled_ingestion/tests/`): Already follow no-mock principle (Phase 3-4, 7)
- ✅ **Tenant Isolation Tests** (`tests/integration/test_tenant_isolation.py`): Use real DB and real tenant resolution
- ✅ **Phase 10 Tests**: All use real `get_request_tenant_id()` helper without mocks

### Exception Handling (Phase 24.1)

**CRITICAL: Specific Exception Types, Structured Logging, No Bare Except/Pass**

All exception handling MUST follow these rules:

1. **Use Specific Exception Types**
   - ✅ **CORRECT**: `except ValueError as e:`, `except ConnectionError as e:`, `except ValidationError as e:`
   - ❌ **WRONG**: `except Exception as e:` (too broad, hides specific failure modes)
   - ❌ **WRONG**: `except:` (bare except, catches everything including SystemExit/KeyboardInterrupt)
   - **Rationale**: Specific exceptions allow proper error handling and root cause identification

2. **Structured Logging**
   - ✅ **CORRECT**: Log with context using `logger.warning()` or `logger.exception()` with `extra={}` dict
   - ✅ **CORRECT**: Include `error_type`, `error`, and relevant context in `extra` dict
   - ❌ **WRONG**: `logger.warning(f"Error: {e}")` (string formatting loses context)
   - ❌ **WRONG**: No logging for unexpected errors

3. **Error Response or Re-raise**
   - ✅ **CORRECT**: Return structured error response using `api_error_response()` helper
   - ✅ **CORRECT**: Re-raise exceptions that should propagate (e.g., `ValidationError`)
   - ❌ **WRONG**: `except ...: pass` (hides failures silently)
   - ❌ **WRONG**: Generic error responses without context

4. **Non-Critical Operations**
   - For cache invalidation, metrics, optional features: Catch specific exceptions (`ConnectionError`, `TimeoutError`, `RuntimeError`) and log with context
   - Never use bare `except:` or `except Exception: pass` - always log with context

#### Example: Correct Exception Handling

```python
# ✅ CORRECT: Specific exception types, structured logging
try:
    invalidate_cache()
except (ConnectionError, TimeoutError, RuntimeError) as e:
    logger.warning(
        "Failed to invalidate cache",
        extra={"error": str(e), "error_type": type(e).__name__},
        exc_info=True,
    )
except Exception as e:
    # Unexpected error - log with full context
    logger.exception(
        "Unexpected error invalidating cache",
        extra={"error_type": type(e).__name__},
    )

# ✅ CORRECT: Service layer exception handling
try:
    result = service.create_resource(...)
except ValidationError as e:
    return handle_service_exception(e)  # Uses api_error_response internally
except NotFoundError as e:
    return handle_service_exception(e)
except Exception as e:
    logger.exception(
        "Unexpected error creating resource",
        extra={"error_type": type(e).__name__},
    )
    return api_error_response(
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
    )
```

#### Example: Incorrect Exception Handling (DO NOT DO THIS)

```python
# ❌ WRONG: Bare except or too broad
try:
    process_data()
except:  # Catches SystemExit, KeyboardInterrupt, everything
    pass

# ❌ WRONG: Generic Exception without logging
try:
    invalidate_cache()
except Exception:
    pass  # Hides failures silently

# ❌ WRONG: No structured logging
try:
    result = service.create_resource(...)
except Exception as e:
    logger.warning(f"Error: {e}")  # No context, no error_type
    return Response({"error": str(e)}, status=500)  # Inconsistent format
```

### Audit Event Rule (Phase 12.4)

**CRITICAL: Exactly One Audit Event Per Mutation**

Every create/update/delete operation on a domain resource MUST emit exactly one audit event. This ensures audit trail completeness and prevents duplicate logging.

#### Audit Event Requirements

1. **Service Layer Preference**
   - ✅ **PREFERRED**: Emit audit events in the service layer (`create_*`, `update_*`, `delete_*` methods)
   - ❌ **AVOID**: Emitting audit events in views when service layer already emits them
   - **Rationale**: Service layer is the single source of truth for business logic; audit events belong with the mutation

2. **One Event Per Mutation**
   - ✅ **CORRECT**: Service method emits exactly one audit event after successful persistence
   - ❌ **WRONG**: Both view and service emit audit events for the same mutation
   - ❌ **WRONG**: Multiple audit events for a single create/update/delete operation

3. **Audit Event Location**
   - **Service Layer**: All `create_*`, `update_*`, `delete_*` methods in services MUST emit audit events
   - **View Layer**: Views should NOT emit audit events if the service layer already does
   - **Exception**: `destroy()` operations may emit audit events in views if no service method exists (legacy pattern)

#### Example: Correct Audit Pattern

```python
# ✅ CORRECT: Service emits audit event
class RetentionService(BaseService):
    @transaction.atomic
    def create_retention_policy(self, tenant_id: str, user_id: str, *args, **kwargs):
        # ... validation and business rules ...

        # Create policy
        policy = RetentionPolicy.objects.create(**kwargs)

        # Emit exactly one audit event (Phase 12.4.1)
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(policy.id),
            details={...},
        )

        return policy

# ✅ CORRECT: View calls service (no audit event in view)
class RetentionPolicyViewSet(viewsets.ModelViewSet):
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Service handles validation, persistence, and audit
        service = GovernanceService(...)
        policy = service.create_retention_policy(...)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

#### Example: Incorrect Audit Pattern (DO NOT DO THIS)

```python
# ❌ WRONG: Both view and service emit audit events
class RetentionPolicyViewSet(viewsets.ModelViewSet):
    def create(self, request):
        # ... validation ...

        policy = serializer.save(...)

        # ❌ DUPLICATE: Service will also emit audit event
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            tenant_id=request.tenant_id,
            resource_id=str(policy.id),
        )

        return Response(serializer.data)

# Service also emits audit event (duplicate!)
class RetentionService(BaseService):
    def create_retention_policy(self, *args, **kwargs):
        policy = RetentionPolicy.objects.create(**kwargs)
        create_audit_event(resource_type="RETENTION_POLICY", action="CREATED", **kwargs)  # ❌ DUPLICATE
        return policy
```

#### Migration Strategy

For existing code with duplicate audit events:

1. **Identify duplicates**: Search for `create_audit_event` calls in both views and services for the same resource type
2. **Remove view-layer audit**: Remove audit event calls from views when service layer already emits them
3. **Verify service-layer audit**: Ensure service layer methods emit audit events for all mutations
4. **Test**: Verify exactly one audit event is created per mutation

#### Verified Implementations (Phase 12)

- ✅ **Retention Policies** (`hub/apps/governance/services.py`): `create_retention_policy()`, `update_retention_policy()` emit audit events; views do not
- ✅ **Webhooks** (`hub/apps/webhooks/webhook_service.py`): `create_webhook()`, `update_webhook()` emit audit events; views do not
- ✅ **Social Features** (`hub/apps/social/services.py`): `create_review()`, `create_comment()`, `create_community_member()` emit audit events; views do not

#### Contracts and Assets (Phase 12.5)

**Primary Mutations**:
- ✅ **Contracts**: `ContractService.create_contract()` and `ODPSService.create_odps()` emit audit events in service layer
- ✅ **Assets**: `AssetService.create_asset()` and `AssetService.update_asset()` are used by views; views emit audit events for primary create/update operations

**Intentional Direct Saves** (Side Effects):
- **Contract Validation Status Updates** (`hub/apps/contracts/views.py`): Direct `.save()` calls for validation status updates are intentional side effects; these emit separate audit events for validation operations
- **Asset Relationship Updates** (`hub/apps/assets/views.py`): Direct `.save()` calls for attaching contracts to assets, updating dataset versions, etc. are intentional relationship updates; these emit separate audit events for relationship operations

**Note**: These direct saves are acceptable as they represent side effects (validation status, relationships) rather than primary mutations. Primary mutations (create/update/delete) go through services with audit events.

### Running Tests

Test environment variables (e.g. `PYTEST_DOCKER_COMPOSE_RUNTIME`, `DATE`, `COMPOSE_FILE`, `API_SERVICE_NAME`) and coverage paths are documented in [TEST_EXECUTION_PLAN.md — Environment Configuration](TEST_EXECUTION_PLAN.md#environment-configuration).

```bash
# All tests
pytest

# Specific app
pytest hub/apps/contracts/tests/

# With coverage
pytest --cov=hub --cov-report=html

# Integration tests (use real services)
pytest tests/integration/ -v

# E2E tests (use real Docker Compose services)
pytest tests/e2e/ -v
```

### Running Tests with Visible Output

For local development and debugging, use verbose output and detailed tracebacks:

```bash
# Verbose output with short traceback (recommended for local development)
pytest -v --tb=short

# Verbose output with all test outcomes (shows passed, failed, skipped, etc.)
pytest -v --tb=short -rA

# Run specific test file with verbose output
pytest -v --tb=short tests/integration/test_scheduled_export_apis_comprehensive.py

# Run with markers for filtered execution
pytest -v -m e2e                    # Run only E2E tests
pytest -v -m integration           # Run only integration tests
pytest -v -m regression             # Run only regression tests
pytest -v -m security               # Run only security tests
pytest -v -m performance            # Run only performance tests
pytest -v -m scheduled_export       # Run only scheduled export tests
pytest -v -m saas_platform          # Run only SaaS platform tests
pytest -v -m cli_sdk                # Run only CLI/SDK tests
```

**Available Markers** (defined in `pytest.ini`):
- `e2e`: End-to-end tests
- `integration`: Integration tests (require services to be running)
- `regression`: Regression tests
- `security`: Security-related tests
- `performance`: Performance tests (can be skipped for faster runs)
- `scheduled_export`: Scheduled export feature tests
- `saas_platform`: SaaS platform feature tests
- `cli_sdk`: CLI and SDK tests
- `unit`: Unit tests
- `slow`: Slow running tests

**Note**: CI continues to use default output (`--tb=short`) and parallel execution where appropriate. Verbose output is for local follow-along only.

### Writing Tests

```python
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.models import Contract

@pytest.mark.django_db(transaction=True)
class ContractServiceTest(TestCase):
    """Test ContractService with real DB and real services."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test", slug="test")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant
        )
        self.service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_create_contract(self):
        """Test contract creation with real service."""
        contract = self.service.create_contract({
            'name': 'Test Contract',
            'original_format': 'JSON',
            'original_spec_type': 'ODCS',
            'original_spec_version': '1.0',
            'original_raw': '{}'
        })
        assert contract.name == 'Test Contract'
        assert contract.tenant_id == self.tenant.id

        # Verify in real DB
        db_contract = Contract.objects.get(id=contract.id)
        assert db_contract.name == 'Test Contract'
```

## Database Migrations

### Creating Migrations

```bash
# Create migration
python manage.py makemigrations

# Apply migration
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

### Migration Best Practices

1. **Never edit existing migrations**: Create new ones
2. **Test migrations**: Test both forward and backward
3. **Use data migrations**: For data transformations
4. **Keep migrations small**: One logical change per migration

## API Development

### Creating API Endpoints

```python
from rest_framework import viewsets
from rest_framework.decorators import action
from hub.apps.api.standards import StandardResponseMixin

class ContractViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        contract = self.get_object()
        result = validate_contract(contract)
        return self.standard_response(data=result)
```

### API Standards

Follow API standards:
- [API Standards](API_STANDARDS.md) - Response formats, pagination, etc.
- [API Error Codes](API_ERROR_CODES.md) - Error handling

## Rate Limiting (Phase 13)

### Single Rate Limiting Implementation

**CRITICAL**: The platform uses a **single rate limiting implementation** via `hub.apps.rate_limiting.middleware.RateLimitMiddleware`. This middleware is configured in `hub/settings.py` MIDDLEWARE and applies globally to all `/api/v1/` endpoints.

**Deprecated Middleware**: `hub.apps.api.middleware.RateLimitMiddleware` is deprecated and should not be used. It is not included in MIDDLEWARE settings and will be removed in a future version.

### Platform Rate Limiting

**Middleware**: `hub.apps.rate_limiting.middleware.RateLimitMiddleware`
- Applied globally to all `/api/v1/` endpoints
- Uses sliding window algorithm with Redis
- Supports multiple time windows (BURST, SUSTAINED, DAILY)
- Enforces limits at tenant, user, and API key levels
- Automatically adds rate limit headers to responses

**Service Layer**: `hub.apps.rate_limiting.service.check_rate_limit()`
- Used for in-view rate limit checks (stricter per-action limits)
- Used by mesh, virtualization, and integrations views for additional rate limiting
- Returns `(allowed: bool, results: List[RateLimitResult])`
- Headers can be retrieved via `get_rate_limit_headers(request, results)`

**Example: In-View Rate Limit Check**:
```python
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from rest_framework.exceptions import Throttled

@action(detail=True, methods=["post"])
def expensive_operation(self, request, id=None):
    # Check rate limit before expensive operation
    allowed, rate_limit_results = check_rate_limit(request)
    if not allowed:
        headers = get_rate_limit_headers(request, rate_limit_results)
        raise Throttled(headers=headers)

    # Perform expensive operation
    result = perform_expensive_operation()

    # Get rate limit headers for response
    _, rate_limit_results = check_rate_limit(request)
    headers = get_rate_limit_headers(request, rate_limit_results)

    return Response(result, headers=headers)
```

**When to Use In-View Checks**:
- **Stricter per-action limits**: When an endpoint needs stricter limits than the middleware provides (e.g., expensive operations like query execution, compliance checks)
- **Per-resource limits**: When rate limiting needs to be per-resource (e.g., per virtual dataset, per domain)
- **Custom rate limit categories**: When an endpoint needs a different category than auto-detected

**When NOT to Use In-View Checks**:
- **General API endpoints**: Middleware handles these automatically
- **Standard CRUD operations**: Middleware provides sufficient protection
- **Read-only endpoints**: Middleware limits are typically sufficient

**Current Usage**:
- **Mesh** (`hub/apps/mesh/views.py`): Uses in-view checks for compliance checks and topology operations (stricter limits for expensive operations)
- **Virtualization** (`hub/apps/virtualization/views.py`): Uses in-view checks for query execution and topology operations (stricter limits for expensive operations)
- **Integrations** (`hub/apps/integrations/views.py`): Uses in-view checks for marketplace sync operations (stricter limits for expensive operations)

### ODPS Ref-Resolver Rate Limiting

**Separate Implementation**: ODPS $ref resolution uses a **separate rate limiting system** (`hub.apps.contracts.odps_rate_limiting`) with specialized limits:

- **Per-tenant**: 100 requests per hour
- **Per-user**: 50 requests per hour
- **Global**: 1000 requests per hour

**Rationale for Separation**:
1. **Different use case**: ODPS $ref resolution involves external HTTP requests and caching, requiring different limits than general API endpoints
2. **Specialized limits**: Lower limits (100/tenant/hour vs 600/tenant/minute for general API) to prevent abuse of external resource fetching
3. **Different error handling**: Uses `ODPSRefResolutionError` with specialized retry-after logic
4. **Separate metrics**: Tracks `odps_rate_limit_violations_total` separately from platform rate limiting metrics

**Usage**: ODPS ref-resolver (`hub/apps/contracts/ref_resolver.py`) calls `check_rate_limit()` from `odps_rate_limiting` module before resolving external $refs.

**Documentation**: See `hub/apps/contracts/docs/ODPS_RATE_LIMITING_DESIGN.md` for detailed design rationale and `hub/apps/contracts/odps_rate_limiting.py` for implementation details.

## Debugging

### Django Debug Toolbar

```python
# settings.py (development only)
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info('Contract created', contract_id=contract.id, tenant_id=tenant.id)
```

### Debugging in Docker

```bash
# View logs
docker compose logs -f api-service

# Access shell
docker compose exec api-service python manage.py shell

# Access database
docker compose exec postgres psql -U hub -d hub
```

## Code Quality

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Error handling implemented
- [ ] Logging added where appropriate
- [ ] Security considerations addressed

## Git Workflow

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

### Commit Messages

```
feat: Add contract validation endpoint

- Implement contract validation logic
- Add validation tests
- Update API documentation
```

### Pull Request Process

1. Create feature branch
2. Make changes
3. Write tests
4. Update documentation
5. Create pull request
6. Address review comments
7. Merge after approval

## BaaS Platform Development

### Development Setup

The BaaS Platform is integrated into the main Django application (`hub/apps/baas/`).

**Key Components**:
- `hub/apps/baas/models.py` - APIKey, APIUsage, APITier models
- `hub/apps/baas/services.py` - UsageTrackingService
- `hub/apps/baas/developer_portal.py` - APIKeyViewSet, DeveloperDocumentationViewSet
- `hub/apps/baas/business_rules.py` - BaaSBusinessRules
- `services/api-gateway/` - API Gateway service for rate limiting

**Setup Steps**:
```bash
# BaaS models are included in main migrations
python manage.py migrate

# Create test API keys
python manage.py shell
>>> from hub.apps.baas.models import APIKey, APITier
>>> tier = APITier.objects.get(name='FREE')
>>> api_key = APIKey.objects.create(name='Test Key', tier=tier, tenant_id='...')
```

### Testing Patterns

**Unit Tests**:
```python
# hub/apps/baas/tests/test_services.py
from hub.apps.baas.services import UsageTrackingService

def test_track_request():
    service = UsageTrackingService()
    usage = service.track_request(
        api_key_id='...',
        endpoint='/api/v1/assets/',
        method='GET',
        status_code=200,
        response_time_ms=100
    )
    assert usage.total_requests == 1
```

**Integration Tests**:
```python
# hub/apps/baas/tests/test_views.py
def test_create_api_key(client):
    response = client.post('/api/v1/baas/api-keys/', {
        'name': 'Test Key',
        'tier': 'FREE'
    })
    assert response.status_code == 201
    assert 'api_key' in response.json()
```

### Debugging Tips

**API Gateway Issues**:
- Check rate limiting logs: `docker logs api-gateway`
- Verify tier configuration: `APITier.objects.all()`
- Check usage tracking: `APIUsage.objects.filter(api_key_id='...')`

**Usage Tracking Issues**:
- Verify UsageTrackingService is called on each request
- Check Redis cache for usage counters
- Review PostgreSQL APIUsage table for historical data

### Code Examples

**Creating API Key Programmatically**:
```python
from hub.apps.baas.models import APIKey, APITier
from hub.apps.baas.services import UsageTrackingService

tier = APITier.objects.get(name='FREE')
api_key = APIKey.objects.create(
    name='My API Key',
    tier=tier,
    tenant_id=tenant_id
)
# API key value is generated and hashed
```

**Tracking API Usage**:
```python
from hub.apps.baas.services import UsageTrackingService

service = UsageTrackingService(tenant_id=tenant_id)
usage = service.track_request(
    api_key_id=api_key.id,
    endpoint='/api/v1/assets/',
    method='GET',
    status_code=200,
    response_time_ms=150
)
```

**Integration Patterns**:
- Use `BaaSBusinessRules` for tier validation
- Implement `BaaSEventPublisher` for event-driven coordination
- Use `UsageTrackingService` for all API request tracking

## ODH Integration Development

### Development Setup

The ODH Integration is integrated into the main Django application (`hub/apps/ml/`).

**Key Components**:
- `hub/apps/ml/models.py` - MLModel, TrainingJob, InferenceDeployment models
- `hub/apps/ml/services.py` - ModelRegistryBridgeService
- `hub/apps/ml/inference_service.py` - InferenceValidationService
- `hub/apps/ml/business_rules.py` - ODHIntegrationBusinessRules
- `services/odh-integration/` - ODH client services

**Setup Steps**:
```bash
# ML models are included in main migrations
python manage.py migrate

# ODH integration clients (optional, for local testing)
cd services/odh-integration
pip install -r requirements.txt
```

### Testing Patterns

**Unit Tests**:
```python
# hub/apps/ml/tests/test_services.py
from hub.apps.ml.services import ModelRegistryBridgeService

def test_link_model_to_asset():
    service = ModelRegistryBridgeService()
    model = service.link_model_to_asset(
        odh_model_id='my-model-123',
        odh_model_version='1.0.0',
        asset_id='...',
        model_type='CLASSIFICATION'
    )
    assert model.odh_model_id == 'my-model-123'
```

**Integration Tests**:
```python
# hub/apps/ml/tests/test_views.py
def test_create_model(client):
    response = client.post('/api/v1/ml/models/', {
        'odh_model_id': 'my-model-123',
        'odh_model_version': '1.0.0',
        'model_type': 'CLASSIFICATION',
        'asset_id': '...'
    })
    assert response.status_code == 201
```

**ODH Client Mocking**:
```python
# For testing without ODH services
from unittest.mock import Mock, patch

@patch('hub.apps.ml.services.ODHModelRegistryClient')
def test_model_sync(mock_client):
    mock_client.return_value.get_model.return_value = {
        'id': 'my-model-123',
        'version': '1.0.0'
    }
    # Test model sync logic
```

### Debugging Tips

**ODH Connection Issues**:
- Check ODH service availability: `curl http://odh-service:8080/health`
- Verify ODH client configuration: `ODH_CLIENT_URL` environment variable
- Review ODH client logs: `services/odh-integration/logs/`

**Training Job Issues**:
- Check training job status: `TrainingJob.objects.get(id='...')`
- Review ODH Training Operator logs
- Verify dataset accessibility before training

**Inference Issues**:
- Check inference deployment status: `InferenceDeployment.objects.get(id='...')`
- Verify input/output contract validation
- Review inference metrics: `GET /api/v1/ml/inference/deployments/{id}/metrics/`

### Code Examples

**Creating ML Model**:
```python
from hub.apps.ml.models import MLModel, ModelType, ModelStatus

model = MLModel.objects.create(
    odh_model_id='my-model-123',
    odh_model_version='1.0.0',
    model_type=ModelType.CLASSIFICATION,
    status=ModelStatus.TRAINING,
    asset_id=asset_id,
    tenant_id=tenant_id
)
```

**Submitting Training Job**:
```python
from hub.apps.ml.services import ModelRegistryBridgeService
from hub.apps.orchestration.workflows.model_training import ModelTrainingWorkflow

service = ModelRegistryBridgeService()
workflow = ModelTrainingWorkflow()
job = workflow.execute(
    model_id=model.id,
    dataset_id=dataset_id,
    config={'epochs': 100, 'batch_size': 32}
)
```

**Running Inference**:
```python
from hub.apps.ml.inference_service import InferenceValidationService

service = InferenceValidationService()
prediction = service.predict(
    model_id=model.id,
    input_data={'feature1': 0.5, 'feature2': 0.8}
)
```

**Integration Patterns**:
- Use `ODHIntegrationBusinessRules` for validation
- Implement `MLEventPublisher` for event-driven coordination
- Use `ModelTrainingWorkflow` for orchestrated training
- Use `InferenceValidationService` for contract validation

## Related Documentation

- [Developer Onboarding](DEVELOPER_ONBOARDING.md) - Complete onboarding guide
- [Testing Guide](TESTING_GUIDE.md) - Testing strategies
- [Code Quality Standards](CODE_QUALITY_STANDARDS.md) - Quality guidelines
- [API Standards](API_STANDARDS.md) - API development standards
- [BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md) - BaaS CLI commands
- [BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md) - BaaS SDK APIs
- [ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md) - ODH CLI commands
- [ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md) - ODH SDK APIs


---

# Code Quality Standards

Comprehensive guide for maintaining code quality in the Data Interoperability Hub project.

## Table of Contents

1. [Overview](#overview)
2. [Linting (Ruff)](#linting-ruff)
3. [Code Formatting (Black)](#code-formatting-black)
4. [Type Checking (MyPy)](#type-checking-mypy)
5. [Security Scanning](#security-scanning)
6. [Dependency Scanning](#dependency-scanning)
7. [Pre-commit Hooks](#pre-commit-hooks)
8. [CI/CD Integration](#cicd-integration)
9. [Quality Gates](#quality-gates)
10. [Best Practices](#best-practices)

---

## Overview

The Data Interoperability Hub project uses a comprehensive set of code quality tools to ensure high standards, maintainability, and security:

- **Ruff**: Fast Python linter and formatter
- **Black**: Uncompromising code formatter
- **MyPy**: Static type checker
- **Bandit**: Security linter for Python code
- **Safety**: Dependency vulnerability scanner
- **pip-audit**: Python dependency vulnerability scanner
- **Trivy**: Container security scanner
- **CodeQL**: Security analysis

### Quality Thresholds

- **Code Quality Score**: Minimum 80/100
- **Test Coverage**: Minimum 90%
- **Linting Errors**: Zero critical errors
- **Security Issues**: Zero high/critical severity issues
- **Type Coverage**: Gradual improvement (not enforced yet)

---

## Linting (Ruff)

### Configuration

Ruff is configured in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "PIE", # flake8-pie
    "PL",  # Pylint
    "TRY", # tryceratops
    "RUF", # Ruff-specific rules
]
```

### Usage

**Check for issues:**
```bash
ruff check .
```

**Fix auto-fixable issues:**
```bash
ruff check . --fix
```

**Format code:**
```bash
ruff format .
```

**Check formatting:**
```bash
ruff format --check .
```

### Common Rules

- **E501**: Line too long (handled by Black)
- **F401**: Unused imports
- **B008**: Function calls in argument defaults
- **PLR0913**: Too many arguments (allowed in some cases)

### Ignoring Rules

```python
# Ignore specific rule for a line
result = process()  # noqa: PLR2004

# Ignore multiple rules
data = get_data()  # noqa: F401, B008

# Ignore for entire file (at top)
# ruff: noqa
```

---

## Code Formatting (Black)

### Configuration

Black is configured in `pyproject.toml`:

```toml
[tool.black]
line-length = 100
target-version = ['py312']
```

### Usage

**Format code:**
```bash
black .
```

**Check formatting:**
```bash
black --check .
```

**Show diff:**
```bash
black --diff .
```

### Black Rules

- **Line length**: 100 characters
- **String quotes**: Prefer double quotes
- **Trailing commas**: Always use when possible
- **Line breaks**: Automatic based on complexity

### Exclusions

Black automatically excludes:
- Migrations (`migrations/`)
- Virtual environments (`venv/`, `.venv/`)
- Build directories (`build/`, `dist/`)

---

## Type Checking (MyPy)

### Configuration

MyPy is configured in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
disallow_incomplete_defs = false
check_untyped_defs = true
no_implicit_optional = true
strict_equality = true
show_error_codes = true
```

### Usage

**Type check code:**
```bash
mypy .
```

**Type check specific module:**
```bash
mypy hub/apps/contracts/
```

**Generate JSON report:**
```bash
mypy . --json-report .mypy-report
```

### Type Hints

**Function annotations:**
```python
def process_data(data: dict[str, Any]) -> list[str]:
    """Process data and return list of strings."""
    return [str(item) for item in data.values()]
```

**Variable annotations:**
```python
from typing import Optional

user_id: Optional[str] = None
count: int = 0
```

**Class annotations:**
```python
class User:
    def __init__(self, name: str, email: str) -> None:
        self.name: str = name
        self.email: str = email
```

### Ignoring Type Errors

```python
# Ignore specific line
result = get_data()  # type: ignore

# Ignore specific error code
value = process()  # type: ignore[assignment]

# Ignore for entire file (at top)
# mypy: ignore-errors
```

### Django Stubs

Django-specific type stubs are provided by `django-stubs`:

```python
from django.db import models

class Contract(models.Model):
    name = models.CharField(max_length=255)  # Properly typed
    status = models.CharField(max_length=50)  # Properly typed
```

---

## Security Scanning

### Bandit

**Configuration**: `.bandit` or `.bandit.yaml`

**Usage:**
```bash
# Scan code
bandit -r hub/ services/ -c .bandit

# JSON output
bandit -r hub/ services/ -f json -o bandit-report.json

# Text output
bandit -r hub/ services/ -f txt -o bandit-report.txt

# Specific severity
bandit -r hub/ services/ --severity-level high
```

**Common Issues:**
- **B101**: `assert` used (allowed in tests)
- **B601**: Shell injection in subprocess (review case-by-case)
- **B506**: Use of `yaml.load()` (use `yaml.safe_load()`)

**Fixing Issues:**
```python
# BAD: Using yaml.load()
import yaml
data = yaml.load(file_content)  # noqa: B506

# GOOD: Using yaml.safe_load()
import yaml
data = yaml.safe_load(file_content)
```

### Trivy (Container Scanning)

**Usage:**
```bash
# Scan Docker image
trivy image hub/api-service:latest

# Scan with severity filter
trivy image --severity HIGH,CRITICAL hub/api-service:latest

# JSON output
trivy image --format json --output trivy-report.json hub/api-service:latest

# Exit on vulnerabilities
trivy image --exit-code 1 --severity HIGH,CRITICAL hub/api-service:latest
```

---

## Dependency Scanning

### Safety

**Usage:**
```bash
# Check dependencies
safety check

# JSON output
safety check --json

# Full report
safety check --full-report
```

**Output:**
```
+==============================================================================+
| REPORT                                                                       |
+==============================================================================+
| Safety found 2 known security vulnerabilities.
| Vulnerability ID: 12345
| Affected package: requests
| Installed version: 2.28.0
| Vulnerability: CVE-2023-12345
| More info: https://pyup.io/vulnerabilities/CVE-2023-12345/
+==============================================================================+
```

### pip-audit

**Usage:**
```bash
# Audit dependencies
pip-audit

# JSON output
pip-audit --format json --output pip-audit-report.json

# Desc format
pip-audit --desc
```

**Output:**
```
Found 3 known vulnerabilities in 2 packages
Package: requests
  Vulnerability ID: CVE-2023-12345
  Severity: HIGH
  Description: Security vulnerability in requests
  Fix: Upgrade to requests>=2.31.0
```

### Fixing Vulnerabilities

1. **Identify vulnerable package:**
   ```bash
   pip-audit
   ```

2. **Check available versions:**
   ```bash
   pip index versions package-name
   ```

3. **Update requirements.txt:**
   ```txt
   # OLD
   requests>=2.28.0
   
   # NEW
   requests>=2.31.0
   ```

4. **Test and verify:**
   ```bash
   pip install -r requirements.txt
   pip-audit  # Verify no vulnerabilities
   ```

---

## Pre-commit Hooks

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Install hooks for all environments
pre-commit install --hook-type pre-push --hook-type commit-msg
```

### Configuration

Pre-commit hooks are configured in `.pre-commit-config.yaml`:

- **Trailing whitespace**: Removed automatically
- **End of file**: Newline added automatically
- **YAML/JSON/TOML**: Syntax checked
- **Large files**: Prevented from committing
- **Merge conflicts**: Detected
- **Debug statements**: Detected
- **Black**: Code formatted
- **Ruff**: Linting and formatting
- **MyPy**: Type checking
- **Bandit**: Security scanning

### Usage

**Run on all files:**
```bash
pre-commit run --all-files
```

**Run specific hook:**
```bash
pre-commit run ruff --all-files
pre-commit run black --all-files
```

**Skip hooks (not recommended):**
```bash
git commit --no-verify -m "message"
```

### Bypassing Hooks

Only bypass hooks in emergencies. Always fix issues properly:

```bash
# Skip pre-commit hooks (use with caution)
SKIP=ruff,black git commit -m "message"
```

---

## CI/CD Integration

### GitHub Actions Workflows

**1. CI Workflow** (`.github/workflows/ci.yml`):
- Runs Ruff linting
- Checks Black formatting
- Runs MyPy type checking
- Runs tests with coverage

**2. Security Scan Workflow** (`.github/workflows/security-scan.yml`):
- Dependency scanning (Safety, pip-audit)
- Code security scanning (Bandit)
- Container scanning (Trivy)

**3. Code Quality Workflow** (`.github/workflows/code-quality.yml`):
- Comprehensive quality analysis
- Quality score calculation
- CodeQL security analysis
- PR comments with metrics

### Quality Gates

Quality gates are enforced in CI:

1. **Linting**: Must pass Ruff checks
2. **Formatting**: Must pass Black checks
3. **Security**: No high/critical Bandit issues
4. **Dependencies**: No known vulnerabilities
5. **Quality Score**: Minimum 80/100

### Local Testing

Test CI checks locally:

```bash
# Run all checks
ruff check .
black --check .
mypy .
bandit -r hub/ services/ -c .bandit
safety check
pip-audit

# Or use pre-commit
pre-commit run --all-files
```

---

## Quality Gates

### Quality Score Calculation

Quality score is calculated based on:

- **Ruff Errors**: -2 points each
- **Ruff Warnings**: -0.5 points each
- **MyPy Errors**: -1 point each
- **Bandit Issues**: -1 point each

**Formula:**
```
Quality Score = max(0, 100 - (ruff_errors * 2 + ruff_warnings * 0.5 + mypy_errors * 1 + bandit_issues * 1))
```

### Thresholds

- **Minimum Quality Score**: 80/100
- **Test Coverage**: 90%
- **Security Issues**: Zero high/critical
- **Dependency Vulnerabilities**: Zero high/critical

### Failing Quality Gates

If quality gates fail:

1. **Review the report**: Check CI artifacts
2. **Fix issues**: Address all errors
3. **Re-run checks**: Verify locally
4. **Re-push**: Trigger CI again

---

## Best Practices

### 1. Code Style

- **Follow PEP 8**: Use Ruff/Black to enforce
- **Type hints**: Add type hints to all functions
- **Docstrings**: Document all public functions/classes
- **Naming**: Use descriptive names, follow conventions

### 2. Security

- **Never commit secrets**: Use environment variables
- **Sanitize input**: Always validate and sanitize user input
- **Use parameterized queries**: Prevent SQL injection
- **Review security scans**: Address all high/critical issues

### 3. Dependencies

- **Pin versions**: Use `>=` for minimum versions
- **Regular updates**: Update dependencies regularly
- **Audit regularly**: Run `pip-audit` weekly
- **Review vulnerabilities**: Address security issues promptly

### 4. Testing

- **Write tests**: Test all new code
- **Maintain coverage**: Keep coverage above 90%
- **Test edge cases**: Test error scenarios
- **Integration tests**: Test service interactions

### 5. Documentation

- **Docstrings**: Document all public APIs
- **Type hints**: Use type hints for clarity
- **Comments**: Explain complex logic
- **README**: Keep README updated

### 6. Git Workflow

- **Pre-commit hooks**: Always run before committing
- **Small commits**: Make focused, atomic commits
- **Clear messages**: Write descriptive commit messages
- **Review PRs**: Review code before merging

---

## Troubleshooting

### Common Issues

**1. Ruff/Black conflicts:**
```bash
# Run Black first, then Ruff
black .
ruff check . --fix
```

**2. MyPy import errors:**
```python
# Add to pyproject.toml
[[tool.mypy.overrides]]
module = "problematic.module"
ignore_missing_imports = true
```

**3. Bandit false positives:**
```python
# Add to .bandit
skips = ["B601"]  # Shell injection false positive
```

**4. Pre-commit hooks failing:**
```bash
# Update hooks
pre-commit autoupdate

# Clear cache
pre-commit clean
```

### Getting Help

- **Ruff**: https://docs.astral.sh/ruff/
- **Black**: https://black.readthedocs.io/
- **MyPy**: https://mypy.readthedocs.io/
- **Bandit**: https://bandit.readthedocs.io/
- **Safety**: https://pyup.io/safety/
- **pip-audit**: https://pypi.org/project/pip-audit/

---

## Additional Resources

- **Python Style Guide**: PEP 8 (https://pep8.org/)
- **Type Hints**: PEP 484 (https://peps.python.org/pep-0484/)
- **Security Best Practices**: OWASP Top 10 (https://owasp.org/www-project-top-ten/)
- **Dependency Management**: pip-tools (https://github.com/jazzband/pip-tools)

---

## Summary

Maintaining code quality requires:

1. ✅ **Automated tools**: Ruff, Black, MyPy, Bandit
2. ✅ **Pre-commit hooks**: Catch issues before commit
3. ✅ **CI/CD integration**: Enforce quality gates
4. ✅ **Regular scanning**: Security and dependency audits
5. ✅ **Documentation**: Clear standards and practices
6. ✅ **Team discipline**: Follow best practices consistently

By following these standards, we ensure:
- **High code quality**: Consistent, maintainable code
- **Security**: Reduced vulnerability surface
- **Reliability**: Fewer bugs and issues
- **Developer experience**: Faster development and debugging


---

# Bug Prevention Patterns

Comprehensive guide for bug prevention patterns including input/output validation, transaction management, idempotency keys, and request deduplication.

## Table of Contents

1. [Overview](#overview)
2. [Input Validation](#input-validation)
3. [Output Validation](#output-validation)
4. [Transaction Management](#transaction-management)
5. [Idempotency Keys](#idempotency-keys)
6. [Request Deduplication](#request-deduplication)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

---

## Overview

The bug prevention module provides comprehensive tools to prevent common bugs and ensure data consistency:

- **Input Validation**: Validate all incoming data using Pydantic models
- **Output Validation**: Validate all outgoing data before sending to clients
- **Transaction Management**: Ensure atomic operations and data consistency
- **Idempotency Keys**: Prevent duplicate operations from retries
- **Request Deduplication**: Detect and prevent duplicate requests

### Module Location

All bug prevention functionality is in `hub.apps.core.bug_prevention`:

- `models.py`: Database models for idempotency and deduplication
- `validators.py`: Input/output validation utilities
- `services.py`: Services for idempotency and deduplication
- `transaction_utils.py`: Transaction management utilities

---

## Input Validation

### Overview

Input validation ensures all incoming data conforms to expected schemas before processing. This prevents:
- Invalid data causing errors
- Security vulnerabilities from malformed input
- Data corruption from unexpected formats

### Usage

**Basic Validation:**

```python
from hub.apps.core.bug_prevention.validators import InputValidator
from pydantic import BaseModel, Field

class CreateContractRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

# Validate input
result = InputValidator.validate(CreateContractRequest, request.data)
if not result.is_valid:
    return Response({"errors": result.errors}, status=400)

# Use validated data
contract_data = result.data
```

**Validation with Exception:**

```python
from hub.apps.core.bug_prevention.validators import InputValidator

# Raises DRFValidationError if invalid
validated_data = InputValidator.validate_and_raise(
    CreateContractRequest,
    request.data
)
```

**In DRF Views:**

```python
from rest_framework.views import APIView
from hub.apps.core.bug_prevention.validators import InputValidator

class ContractViewSet(APIView):
    def create(self, request):
        # Validate input
        validated_data = InputValidator.validate_and_raise(
            CreateContractRequest,
            request.data
        )
        
        # Use validated data
        contract = ContractService.create_contract(
            tenant_id=request.user.tenant_id,
            data=validated_data
        )
        
        return Response(contract, status=201)
```

### Validation Models

Create Pydantic models for all input schemas:

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class CreateAssetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    asset_type: str = Field(..., pattern="^(DATASET|API|FILE)$")
    domain: Optional[str] = None
    tags: List[str] = Field(default_factory=list, max_items=10)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return value.strip()
```

---

## Output Validation

### Overview

Output validation ensures all outgoing data conforms to expected schemas before sending to clients. This prevents:
- Inconsistent API responses
- Data leaks from unexpected fields
- Type mismatches in responses

### Usage

**Basic Validation:**

```python
from hub.apps.core.bug_prevention.validators import OutputValidator

class ContractResponse(BaseModel):
    id: str
    name: str
    status: str

# Validate output
result = OutputValidator.validate(ContractResponse, contract_data)
if not result.is_valid:
    logger.error("Output validation failed", errors=result.errors)
    # Handle error appropriately

# Use validated data
return Response(result.data, status=200)
```

**Validation and Serialization:**

```python
# Validates and returns serialized dict
serialized_data = OutputValidator.validate_and_serialize(
    ContractResponse,
    contract_data
)

return Response(serialized_data, status=200)
```

**In DRF Views:**

```python
class ContractViewSet(APIView):
    def retrieve(self, request, pk):
        contract = ContractService.get_contract(
            tenant_id=request.user.tenant_id,
            contract_id=pk
        )
        
        # Validate output
        serialized = OutputValidator.validate_and_serialize(
            ContractResponse,
            contract
        )
        
        return Response(serialized, status=200)
```

---

## Transaction Management

### Overview

Transaction management ensures atomic operations and data consistency. This prevents:
- Partial updates causing inconsistent state
- Race conditions in concurrent operations
- Data corruption from interrupted operations

### Usage

**Context Manager:**

```python
from hub.apps.core.bug_prevention.transaction_utils import transaction_atomic

def create_contract_with_assets(contract_data, assets_data):
    with transaction_atomic():
        # All operations succeed or all fail
        contract = Contract.objects.create(**contract_data)
        for asset_data in assets_data:
            Asset.objects.create(contract=contract, **asset_data)
        return contract
```

**Decorator:**

```python
from hub.apps.core.bug_prevention.transaction_utils import with_transaction

@with_transaction()
def create_contract_with_assets(contract_data, assets_data):
    contract = Contract.objects.create(**contract_data)
    for asset_data in assets_data:
        Asset.objects.create(contract=contract, **asset_data)
    return contract
```

**Transaction Manager (Complex Operations):**

```python
from hub.apps.core.bug_prevention.transaction_utils import TransactionManager

def complex_operation():
    manager = TransactionManager()
    
    with transaction.atomic():
        # Step 1: Create contract
        contract = Contract.objects.create(...)
        
        # Step 2: Create assets (can rollback independently)
        with manager.savepoint():
            assets = []
            for asset_data in assets_data:
                assets.append(Asset.objects.create(contract=contract, **asset_data))
        
        # Step 3: Create datasets (can rollback independently)
        with manager.savepoint():
            datasets = []
            for dataset_data in datasets_data:
                datasets.append(Dataset.objects.create(contract=contract, **dataset_data))
        
        return contract, assets, datasets
```

**Retry on Deadlock:**

```python
from hub.apps.core.bug_prevention.transaction_utils import retry_on_deadlock

@retry_on_deadlock(max_retries=3)
def update_contract_status(contract_id, new_status):
    # This will retry up to 3 times on deadlock
    contract = Contract.objects.get(id=contract_id)
    contract.status = new_status
    contract.save()
```

---

## Idempotency Keys

### Overview

Idempotency keys prevent duplicate operations from retries. This ensures:
- Safe retries on network failures
- No duplicate resource creation
- Consistent responses for same requests

### Usage

**In DRF Views:**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from hub.apps.core.bug_prevention.services import (
    IdempotencyService,
    IdempotencyConflictError
)

class DQRunViewSet(APIView):
    def create(self, request):
        # Get idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")
        
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header required"},
                status=400
            )
        
        tenant_id = str(request.user.tenant_id)
        method = request.method
        path = request.path
        body = request.data
        
        # Check idempotency
        try:
            record, cached_response = IdempotencyService.check_idempotency(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=method,
                path=path,
                body=body
            )
            
            # If cached response exists, return it
            if cached_response:
                return Response(
                    cached_response["data"],
                    status=cached_response["status_code"]
                )
            
            # Execute operation
            dq_run = DQService.create_run(
                tenant_id=tenant_id,
                dataset_id=body["dataset_id"]
            )
            
            # Store idempotency key
            IdempotencyService.store_idempotency(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=method,
                path=path,
                body=body,
                response_status=201,
                response_body={"id": str(dq_run.id), "status": dq_run.status}
            )
            
            return Response({"id": str(dq_run.id), "status": dq_run.status}, status=201)
            
        except IdempotencyConflictError as e:
            return Response(
                {"error": str(e.detail)},
                status=409
            )
```

**Idempotency Key Format:**

- Length: 8-256 characters
- Characters: Alphanumeric, hyphens, underscores, forward slashes
- Pattern: `^[a-zA-Z0-9\-_/]{8,256}$`

**Example Keys:**

```
dq-run-2025-01-15-abc123
contract/create/user-123
job-550e8400-e29b-41d4-a716-446655440000
```

**Cleanup:**

```python
# Clean up expired idempotency keys (run as background job)
deleted_count = IdempotencyService.cleanup_expired(older_than_hours=24)
```

---

## Request Deduplication

### Overview

Request deduplication detects and prevents duplicate requests within a time window. This prevents:
- Accidental duplicate submissions
- Race conditions from concurrent requests
- Unnecessary processing of duplicate requests

### Usage

**In DRF Views:**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from hub.apps.core.bug_prevention.services import RequestDeduplicationService

class ContractViewSet(APIView):
    def create(self, request):
        tenant_id = str(request.user.tenant_id)
        method = request.method
        path = request.path
        body = request.data
        headers = {
            "Content-Type": request.headers.get("Content-Type", ""),
            "Accept": request.headers.get("Accept", "")
        }
        
        # Check for duplicate
        is_duplicate, record = RequestDeduplicationService.check_duplicate(
            tenant_id=tenant_id,
            method=method,
            path=path,
            body=body,
            headers=headers
        )
        
        if is_duplicate:
            return Response(
                {"error": "Duplicate request detected"},
                status=429  # Too Many Requests
            )
        
        # Store request fingerprint
        RequestDeduplicationService.store_request(
            tenant_id=tenant_id,
            method=method,
            path=path,
            body=body,
            headers=headers
        )
        
        # Process request
        contract = ContractService.create_contract(
            tenant_id=tenant_id,
            data=body
        )
        
        return Response({"id": str(contract.id)}, status=201)
```

**Deduplication Window:**

- Default: 5 minutes
- Configurable per request type
- Automatic cleanup of expired records

**Cleanup:**

```python
# Clean up expired deduplication records (run as background job)
deleted_count = RequestDeduplicationService.cleanup_expired(older_than_minutes=5)
```

---

## Best Practices

### 1. Input Validation

- **Validate all inputs**: Never trust user input
- **Use Pydantic models**: Create models for all input schemas
- **Validate early**: Validate as soon as data enters the system
- **Provide clear errors**: Return detailed validation error messages

### 2. Output Validation

- **Validate all outputs**: Ensure responses match schemas
- **Use Pydantic models**: Create models for all output schemas
- **Log validation failures**: Monitor for unexpected data issues
- **Fail safe**: Return error if output validation fails

### 3. Transaction Management

- **Use transactions for multi-step operations**: Ensure atomicity
- **Keep transactions short**: Don't hold locks for long periods
- **Handle deadlocks**: Use retry logic for deadlock scenarios
- **Use savepoints**: For complex operations with partial rollback

### 4. Idempotency Keys

- **Require for create operations**: All POST endpoints should support idempotency
- **Validate key format**: Ensure keys meet format requirements
- **Store responses**: Cache responses for idempotency key lookups
- **Clean up expired keys**: Run cleanup job regularly

### 5. Request Deduplication

- **Use for non-idempotent operations**: Prevent accidental duplicates
- **Set appropriate windows**: Balance between protection and usability
- **Clean up expired records**: Run cleanup job regularly
- **Monitor deduplication rate**: Track how often duplicates are detected

### 6. Error Handling

- **Handle validation errors gracefully**: Return clear error messages
- **Log all errors**: Monitor for patterns and issues
- **Don't expose internals**: Keep error messages user-friendly
- **Use appropriate status codes**: 400 for validation, 409 for conflicts

---

## Examples

### Complete Example: Create Contract with Validation and Idempotency

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from hub.apps.core.bug_prevention.validators import InputValidator, OutputValidator
from hub.apps.core.bug_prevention.services import IdempotencyService, IdempotencyConflictError
from hub.apps.core.bug_prevention.transaction_utils import transaction_atomic
from pydantic import BaseModel, Field

class CreateContractRequest(BaseModel):
    original_raw: str = Field(..., min_length=1)
    original_format: str = Field(..., pattern="^(JSON|YAML)$")

class ContractResponse(BaseModel):
    id: str
    status: str
    normalization_status: str

class ContractViewSet(APIView):
    def create(self, request):
        # Get idempotency key
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header required"},
                status=400
            )
        
        tenant_id = str(request.user.tenant_id)
        
        # Check idempotency
        try:
            record, cached_response = IdempotencyService.check_idempotency(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=request.method,
                path=request.path,
                body=request.data
            )
            
            if cached_response:
                return Response(
                    cached_response["data"],
                    status=cached_response["status_code"]
                )
        except IdempotencyConflictError as e:
            return Response(
                {"error": str(e.detail)},
                status=409
            )
        
        # Validate input
        try:
            validated_data = InputValidator.validate_and_raise(
                CreateContractRequest,
                request.data
            )
        except ValidationError as e:
            return Response(
                {"errors": e.detail},
                status=400
            )
        
        # Create contract in transaction
        try:
            with transaction_atomic():
                contract = ContractService.create_contract(
                    tenant_id=tenant_id,
                    data=validated_data
                )
                
                # Validate output
                serialized = OutputValidator.validate_and_serialize(
                    ContractResponse,
                    {
                        "id": str(contract.id),
                        "status": contract.status,
                        "normalization_status": contract.normalization_status
                    }
                )
                
                # Store idempotency key
                IdempotencyService.store_idempotency(
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    method=request.method,
                    path=request.path,
                    body=request.data,
                    response_status=201,
                    response_body=serialized
                )
                
                return Response(serialized, status=201)
                
        except Exception as e:
            logger.error("Contract creation failed", error=str(e))
            return Response(
                {"error": "Contract creation failed"},
                status=500
            )
```

---

## Summary

Bug prevention patterns ensure:

1. ✅ **Input Validation**: All incoming data is validated
2. ✅ **Output Validation**: All outgoing data is validated
3. ✅ **Transaction Management**: Operations are atomic and consistent
4. ✅ **Idempotency Keys**: Duplicate operations are prevented
5. ✅ **Request Deduplication**: Duplicate requests are detected

By following these patterns, we ensure:
- **Data Integrity**: Consistent and valid data
- **Reliability**: Operations are safe to retry
- **Security**: Invalid input is rejected
- **Performance**: Duplicate processing is avoided


---

# Mypy Ratchet Strategy

> Progressive type-checking enforcement without blocking existing development.
> Updated: 2026-03-21 | Phase 112.L.2

## Current State

- **mypy runs in CI** (`.github/workflows/ci.yml` lint job)
- **Non-blocking**: `mypy . --show-error-codes --no-error-summary || true` with `continue-on-error: true`
- **Configuration**: `pyproject.toml [tool.mypy]` — `check_untyped_defs=true`, `warn_return_any=true`, `strict_equality=true`
- **Migrations excluded**: `hub.apps.*.migrations.*` → `ignore_errors=true`

## Ratchet Strategy

### Phase 1 — Baseline (current)

Mypy runs for visibility but does not block CI. Developers see type errors
in CI logs and IDE integrations but are not required to fix them.

### Phase 2 — Per-package strict (deferred)

**Owner**: Engineering lead
**Target date**: 2026-Q3 (after staging stabilization)

Enable `disallow_untyped_defs = true` per-package starting with the
smallest, most stable packages:

```toml
# pyproject.toml — add when ready
[[tool.mypy.overrides]]
module = "hub.apps.core.events.*"
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "hub.apps.core.resilience.*"
disallow_untyped_defs = true
```

Order of adoption (smallest → largest):
1. `hub.apps.core.events` — event bus, already well-typed
2. `hub.apps.core.resilience` — circuit breaker, small surface
3. `hub.apps.api.standards` — pagination, filtering, sorting
4. `hub.apps.webhooks` — webhook service, models, validators
5. `hub.apps.auth` — authentication, JWT, permissions

### Phase 3 — Error count ratchet (deferred)

**Owner**: Engineering lead
**Target date**: 2026-Q4

Capture baseline error count and fail CI if new errors exceed it:

```yaml
# ci.yml — add when ready
- name: Mypy ratchet check
  run: |
    count=$(mypy . --show-error-codes --no-error-summary 2>&1 | grep -c "^hub/" || true)
    baseline=$(cat .mypy-baseline-count 2>/dev/null || echo 9999)
    if [ "$count" -gt "$baseline" ]; then
      echo "::error::Mypy errors increased: $count > $baseline"
      exit 1
    fi
    echo "$count" > .mypy-baseline-count
```

### Phase 4 — Strict mode (long-term)

Enable `disallow_untyped_defs = true` globally. All new code must be
typed. Existing untyped code grandfathered via `type: ignore` comments
with issue references.

---

# E2E & Backend Test Skip Registry

> **Single source of truth** for all skipped tests.
> Updated: 2026-03-21 | Phase 112.I.1

## Policy

| When | Action |
|------|--------|
| Feature not implemented | `test.describe.skip()` with UC/JOURNEY ID |
| Optional service unavailable | Runtime `test.skip(condition, reason)` |
| Infra precondition not met | Runtime `test.skip(condition, reason)` or `pytest.skip()` |
| Flaky / timing | **Do NOT skip** — use `test.setTimeout()` + Playwright retries (CI: 2x) |
| Broken test | Fix immediately — do not skip |

Canonical refs: `frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md`, `docs/E2E_TEST_SEMANTICS.md`

---

## E2E Skips (Playwright)

### DEFERRED — Transformation Pipeline (UC-TRANS-001)

| Journey | File | Owner | Status | Notes |
|---------|------|-------|--------|-------|
| JOURNEY-DE-007 | `e2e/journeys/de/JOURNEY-DE-007.spec.ts` | backend | `describe.skip` | Backend not implemented |
| JOURNEY-DC-007 | `e2e/journeys/dc/JOURNEY-DC-007.spec.ts` | backend | `describe.skip` | Backend not implemented |
| JOURNEY-DEV-006 | `e2e/journeys/dev/JOURNEY-DEV-006.spec.ts` | backend | `describe.skip` | API integration pending |
| JOURNEY-AUD-005 | `e2e/journeys/aud/JOURNEY-AUD-005.spec.ts` | backend | `describe.skip` | Audit for pipelines pending |
| JOURNEY-DPO-008 | `e2e/journeys/dpo/JOURNEY-DPO-008.spec.ts` | backend | active (gated) | Capability-gated, partial |
| JOURNEY-DA-001 | `e2e/journeys/da/JOURNEY-DA-001.spec.ts` | backend | active (gated) | Placeholder API, partial |

### INFRA — Runtime Conditional Skips

| Test | File | Service | Category | Root Cause |
|------|------|---------|----------|------------|
| DQ run + rerun journey | `phase3-quality-gates.spec.ts:487` | DQ worker | INFRA | Worker not running / poll timeout 60s |
| Password reset email | `auth-visitor-journeys.spec.ts:41` | MailHog | INFRA | MailHog SMTP not deployed |
| Virtual dataset edit UX | `phase6-mesh-virtualization.spec.ts:333` | API | INFRA | No dataset row + API create unavailable |
| Query execution UX (3 skips) | `phase6-mesh-virtualization.spec.ts:389,402,425` | Query engine | INFRA | Backend query execution unavailable |
| ODBC virtual dataset (2 skips) | `phase6-mesh-virtualization.spec.ts:439,444` | ODBC driver | INFRA | Network/auth failure to ODBC endpoint |

---

## Backend Skips (pytest)

### INFRA — Service Unavailable

| Module | Count | Service | Skip Pattern |
|--------|-------|---------|-------------|
| `semantic/tests/` | 15 | Fuseki/SemanticService | `skipTest()` / `@skipif` |
| `virtualization/tests/` | 8 | ODBC driver / Fuseki / Compliance | `skipTest()` / `@skipif` |
| `datasets/tests/` | 2 | S3/MinIO | `skipTest()` |
| `jobs/tests/` | 3 | Prefect workflow engine | `skipTest()` |
| `tests/dr/` | 2 | pg_dump / showmigrations | `skipTest()` |
| `tests/test_fts_search.py` | 1 | PostgreSQL vendor | `skipTest()` |
| `tests/test_auth_security.py` | 2 | Refresh cookie | `skipTest()` |

### Summary

| Category | E2E | Backend | Total |
|----------|-----|---------|-------|
| DEFERRED | 4 describe.skip + 2 active-gated | 0 | 6 |
| INFRA | 8 runtime skips | ~33 | ~41 |
| FLAKY | 0 | 0 | 0 |
| REAL (broken) | 0 | 0 | 0 |

**No infrastructure issues are masked as skips** — all INFRA skips correctly
identify the missing service and degrade gracefully.

---

# Technical Debt Triage Report

**Last Updated**: 2026-03-22
**Phase**: 24.8.1

## Overview

This document tracks TODO/FIXME/XXX/HACK references in `hub/apps` and their status.

## Summary

- **19 TODOs**: Legitimate future work items
- **0 FIXMEs**: None found
- **1 HACK**: Test data (not a real hack)
- **0 XXXs**: None found

## TODO References

### High Priority (Missing Features)

1. **auth/views.py:622** - Track last_login_at in User model or separate LoginHistory model
   - **Status**: Future enhancement
   - **Priority**: Medium
   - **Owner**: TBD

2. **scheduled_ingestion/views.py:967** - Add last_tested_at and last_test_result fields to ScheduledIngestion model
   - **Status**: Future enhancement
   - **Priority**: Medium
   - **Owner**: TBD

### Medium Priority (Integration Work)

3. **orchestration/workflows/version_creation.py:797** - Implement actual lineage reference updates when lineage system is ready
   - **Status**: Blocked on lineage system
   - **Priority**: Medium
   - **Owner**: TBD

4. **orchestration/workflows/version_creation.py:899** - Implement actual notification sending when notification system is ready
   - **Status**: Blocked on notification system
   - **Priority**: Medium
   - **Owner**: TBD

5. **orchestration/workflows/marketplace_publication.py:715** - Implement actual notification sending when notification system is ready
   - **Status**: Blocked on notification system
   - **Priority**: Medium
   - **Owner**: TBD

6. **tenants/views.py:294,307** - Implement email notification when notification service is ready
   - **Status**: Blocked on notification service
   - **Priority**: Medium
   - **Owner**: TBD

7. **dq/alerting.py:167,182,197,212** - Integrate with email service, Slack API, HTTP POST, PagerDuty API
   - **Status**: Future integration work
   - **Priority**: Medium
   - **Owner**: TBD

### Low Priority (Enhancements)

8. **mesh/views.py:628-629** - Calculate health score and health status from topology business rules
   - **Status**: Future enhancement
   - **Priority**: Low
   - **Owner**: TBD

9. **files/views.py:392** - Make this strict in production
   - **Status**: Production hardening
   - **Priority**: Low
   - **Owner**: TBD

10. **files/views.py:537** - Add for_browser parameter to generate_presigned_part_url
    - **Status**: Future enhancement
    - **Priority**: Low
    - **Owner**: TBD

11. **audit/management/commands/archive_old_audit_events.py:68** - Implement actual archiving (move to cold storage, mark as archived, etc.)
    - **Status**: Future enhancement
    - **Priority**: Low
    - **Owner**: TBD

### Test-Related (Documentation)

12. **users/tests/test_views.py:147** - Update this test when resource checking is implemented
    - **Status**: Test update needed when feature is implemented
    - **Priority**: Low
    - **Owner**: TBD

13. **users/tests/test_user_deletion.py:73** - When resources are implemented (assets, datasets, etc.)
    - **Status**: Test update needed when feature is implemented
    - **Priority**: Low
    - **Owner**: TBD

## HACK References

1. **ml/tests/test_e2e.py:434** - "odh_model_id": "model-hack"
   - **Status**: Test data only, not a real hack
   - **Action**: No action needed

## Resolved

1. **auth/views.py:426** - ~~TODO: Implement audit logging~~ ✅ RESOLVED
   - **Status**: Audit logging is already implemented via middleware and signal handlers
   - **Resolution**: Updated comment to reflect current implementation

## Recommendations

1. **Create tickets** for high-priority TODOs (items 1-2)
2. **Track dependencies** for medium-priority TODOs (items 3-7) - these are blocked on other systems
3. **Document in backlog** for low-priority TODOs (items 8-11)
4. **Update tests** when related features are implemented (items 12-13)

## Notes

- All TODOs are legitimate future work items, not ambiguous tech-debt markers
- No TODOs are left without clear context or purpose
- The single HACK reference is test data and not a code quality issue

---

# Docker Compose Structure Documentation

Complete documentation for the main `docker-compose.yml` file structure, services, dependencies, and configuration.

## Overview

The `docker-compose.yml` file defines all services required for the Data Interoperability Hub platform, including:

- **Infrastructure Services**: PostgreSQL, Redis, MinIO, Fuseki
- **Application Services**: API, Worker, Workflow Engine, Workflow Registry, Event Bus, Event Schema Registry
- **Microservices**: Semantic Service, DQ Service, Compliance Service, DataContract Service, Search Service, Observability Service, Webhook Service
- **Monitoring Services**: Prometheus, Grafana, Jaeger, Alertmanager
- **API Gateway**: Traefik
- **Orchestration**: Prefect Server, Prefect Workers, Prefect Integration Service

## Service Structure

### Infrastructure Services

#### PostgreSQL (`postgres`)
- **Image**: `postgres:16-alpine`
- **Port**: `5432` (configurable via `POSTGRES_PORT`)
- **Volumes**: `pgdata:/var/lib/postgresql/data`
- **Health Check**: `pg_isready -U hub`
- **Environment Variables**:
  - `POSTGRES_USER` (default: `hub`)
  - `POSTGRES_PASSWORD` (default: `hub`)
  - `POSTGRES_DB` (default: `hub`)

#### Redis (`redis`)
- **Image**: `redis:7-alpine`
- **Port**: `6379` (configurable via `REDIS_PORT`)
- **Volumes**: `redis-data:/data`
- **Health Check**: `redis-cli ping`
- **Configuration**: AOF persistence, memory limits, LRU eviction policy

#### MinIO (`minio`)
- **Image**: `minio/minio:latest`
- **Ports**: `9000` (API), `9001` (Console)
- **Volumes**: `minio-data:/data`
- **Health Check**: `curl -f http://localhost:9000/minio/health/live`
- **Environment Variables**:
  - `MINIO_ROOT_USER` (default: `minio`)
  - `MINIO_ROOT_PASSWORD` (default: `minio123`)

#### Apache Jena Fuseki (`fuseki`)
- **Image**: `stain/jena-fuseki:latest`
- **Port**: `3030` (configurable via `FUSEKI_PORT`)
- **Volumes**: `fuseki-data:/fuseki`
- **Health Check**: `curl -f http://localhost:3030/$/ping`
- **Environment Variables**:
  - `FUSEKI_DATASET` (default: `hub`)
  - `ADMIN_PASSWORD` (default: `admin`)

### Application Services

#### API Service (`api-service`)
- **Build**: `services/api/Dockerfile`
- **Port**: `8000` (configurable via `API_PORT`)
- **Command**: `python manage.py runserver 0.0.0.0:8000`
- **Dependencies**: `postgres`, `redis`, `minio`, `jaeger`
- **Health Check**: `curl -f http://localhost:8000/health`
- **Environment Variables**:
  - Database: `DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, etc.
  - Redis: `REDIS_URL`
  - OpenTelemetry: `OPENTELEMETRY_ENABLED`, `JAEGER_AGENT_HOST`, `JAEGER_AGENT_PORT`
  - Email: `EMAIL_BACKEND`, `SMTP_HOST`, `SENDGRID_API_KEY`, etc.

#### Worker Service (`worker-service`)
- **Build**: `services/worker/Dockerfile`
- **Port**: `8080` (health check, configurable via `WORKER_HEALTH_PORT`)
- **Command**: `python services/worker/main.py job_critical job_default job_low`
- **Dependencies**: `postgres`, `redis`, `jaeger`
- **Health Check**: `curl -f http://localhost:8080/healthz`
- **Environment Variables**:
  - Worker: `WORKER_HEALTH_PORT`, `WORKER_MAX_CONCURRENCY`, `WORKER_RESERVED_SLOTS_RATIO`
  - OpenTelemetry: `OPENTELEMETRY_ENABLED`, `JAEGER_AGENT_HOST`, `JAEGER_AGENT_PORT`

#### Workflow Engine Service (`workflow-engine-service`)
- **Build**: `services/workflow-engine/Dockerfile`
- **Port**: `8088` (health check, configurable via `WORKFLOW_ENGINE_HEALTH_PORT`)
- **Command**: `python services/workflow-engine/main.py --poll-interval 5 --batch-size 10`
- **Dependencies**: `postgres`, `redis`, `jaeger`
- **Health Check**: `curl -f http://localhost:8088/healthz`
- **Endpoints**: `/healthz`, `/ready`, `/metrics`
- **Environment Variables**:
  - Workflow Engine: `WORKFLOW_ENGINE_HEALTH_PORT`, `WORKFLOW_ENGINE_POLL_INTERVAL`, `WORKFLOW_ENGINE_BATCH_SIZE`
  - OpenTelemetry: `OPENTELEMETRY_ENABLED`, `OPENTELEMETRY_METRICS_ENABLED`, `JAEGER_AGENT_HOST`, `JAEGER_AGENT_PORT`

#### Workflow Registry Service (`workflow-registry-service`)
- **Build**: `services/workflow-registry/Dockerfile`
- **Port**: `8089` (configurable via `WORKFLOW_REGISTRY_PORT`)
- **Command**: `uvicorn services.workflow-registry.main:app --host 0.0.0.0 --port 8089`
- **Dependencies**: `postgres`, `jaeger`
- **Health Check**: `curl -f http://localhost:8089/health`
- **Environment Variables**:
  - Service: `WORKFLOW_REGISTRY_PORT`, `LOG_LEVEL`, `ENVIRONMENT`
  - OpenTelemetry: `OPENTELEMETRY_ENABLED`, `JAEGER_AGENT_HOST`, `JAEGER_AGENT_PORT`

#### Event Bus Health Service (`event-bus-health-service`)
- **Build**: `services/event-bus/Dockerfile`
- **Port**: `8090` (configurable via `EVENT_BUS_HEALTH_PORT`)
- **Command**: `uvicorn services.event-bus.health:app --host 0.0.0.0 --port 8090`
- **Dependencies**: `postgres`, `redis`, `jaeger`
- **Health Check**: `curl -f http://localhost:8090/healthz`
- **Environment Variables**:
  - Event Bus: `EVENT_BUS_REDIS_POOL_SIZE`, `EVENT_BUS_REDIS_MAX_CONNECTIONS`, `EVENT_BUS_ENABLE_PERSISTENCE`
  - OpenTelemetry: `OPENTELEMETRY_ENABLED`, `JAEGER_AGENT_HOST`, `JAEGER_AGENT_PORT`

#### Event Schema Registry Service (`event-schema-registry-service`)
- **Build**: `services/event-schema-registry/Dockerfile`
- **Port**: `8091` (configurable via `EVENT_SCHEMA_REGISTRY_PORT`)
- **Command**: `uvicorn services.event-schema-registry.main:app --host 0.0.0.0 --port 8091`
- **Dependencies**: `postgres`, `jaeger`
- **Health Check**: `curl -f http://localhost:8091/health`
- **Environment Variables**:
  - Service: `EVENT_SCHEMA_REGISTRY_PORT`, `LOG_LEVEL`, `ENVIRONMENT`
  - OpenTelemetry: `OPENTELEMETRY_ENABLED`, `JAEGER_AGENT_HOST`, `JAEGER_AGENT_PORT`

### Microservices

#### Semantic Service (`semantic-service`)
- **Build**: `services/semantic-service/Dockerfile`
- **Port**: `8081` (configurable via `SEMANTIC_PORT`)
- **Dependencies**: `fuseki`
- **Health Check**: `curl -f http://localhost:8081/health`
- **Environment Variables**:
  - `FUSEKI_URL`, `FUSEKI_DATASET`, `FUSEKI_ADMIN_PASSWORD`, `HUB_DOMAIN`

#### DQ Service (`dq-service`)
- **Build**: `services/dq-service/Dockerfile`
- **Port**: `8083` (configurable via `DQ_PORT`)
- **Health Check**: `curl -f http://localhost:8083/health`

#### Compliance Service (`compliance-service`)
- **Build**: `services/compliance-service/Dockerfile`
- **Port**: `8082` (configurable via `COMPLIANCE_PORT`)
- **Health Check**: `curl -f http://localhost:8082/health`

#### DataContract Service (`datacontract-service`)
- **Build**: `services/datacontract-service/Dockerfile`
- **Port**: `8080` (configurable via `DATACONTRACT_PORT`)
- **Health Check**: `curl -f http://localhost:8080/health`

#### Search Service (`search-service`)
- **Build**: `services/search-service/Dockerfile`
- **Port**: `8085` (configurable via `SEARCH_PORT`)
- **Dependencies**: `postgres`
- **Health Check**: `curl -f http://localhost:8085/health`
- **Environment Variables**:
  - `DATABASE_URL`, `SEARCH_INDEX_UPDATE_INTERVAL_SECONDS`, `SEARCH_RESULT_LIMIT`

#### Observability Service (`observability-service`)
- **Build**: `services/observability-service/Dockerfile`
- **Port**: `8086` (configurable via `OBSERVABILITY_PORT`)
- **Dependencies**: `postgres`, `prometheus`
- **Health Check**: `curl -f http://localhost:8086/health`
- **Environment Variables**:
  - `DATABASE_URL`, `PROMETHEUS_URL`, `METRICS_UPDATE_INTERVAL_SECONDS`, `FRESHNESS_CHECK_INTERVAL_SECONDS`

#### Webhook Service (`webhook-service`)
- **Build**: `services/webhook-service/Dockerfile`
- **Port**: `8087` (configurable via `WEBHOOK_PORT`)
- **Dependencies**: `postgres`
- **Health Check**: `curl -f http://localhost:8087/health`
- **Environment Variables**:
  - `DATABASE_URL`, `WEBHOOK_RETRY_MAX_ATTEMPTS`, `WEBHOOK_RETRY_BACKOFF_SECONDS`, `WEBHOOK_TIMEOUT_SECONDS`

### Monitoring Services

#### Prometheus (`prometheus`)
- **Image**: `prom/prometheus:latest`
- **Port**: `9090` (configurable via `PROMETHEUS_PORT`)
- **Volumes**:
  - `./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro`
  - `./monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro`
  - `./monitoring/prometheus/alerts:/etc/prometheus/alerts:ro`
  - `prometheus-data:/prometheus`
- **Health Check**: `wget --quiet --tries=1 --spider http://localhost:9090/-/healthy`
- **Dependencies**: All application services (for scraping metrics)

#### Grafana (`grafana`)
- **Image**: `grafana/grafana:latest`
- **Port**: `3000` (configurable via `GRAFANA_PORT`)
- **Volumes**:
  - `grafana-data:/var/lib/grafana`
  - `./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro`
  - `./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro`
- **Health Check**: `wget --quiet --tries=1 --spider http://localhost:3000/api/health`
- **Dependencies**: `prometheus`
- **Environment Variables**:
  - `GRAFANA_ADMIN_USER` (default: `admin`)
  - `GRAFANA_ADMIN_PASSWORD` (default: `admin`)

#### Jaeger (`jaeger`)
- **Image**: `jaegertracing/all-in-one:latest`
- **Ports**:
  - `16686` (UI, configurable via `JAEGER_UI_PORT`)
  - `14268` (HTTP collector, configurable via `JAEGER_HTTP_PORT`)
  - `6831/udp` (UDP collector, configurable via `JAEGER_UDP_PORT`)
- **Health Check**: `wget --quiet --tries=1 --spider http://localhost:16686/`
- **Environment Variables**:
  - `COLLECTOR_OTLP_ENABLED=true`
  - `COLLECTOR_ZIPKIN_HOST_PORT=:9411`

#### Alertmanager (`alertmanager`)
- **Image**: `prom/alertmanager:latest`
- **Port**: `9093` (configurable via `ALERTMANAGER_PORT`)
- **Volumes**:
  - `./monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro`
  - `alertmanager-data:/alertmanager`
- **Health Check**: `wget --quiet --tries=1 --spider http://localhost:9093/-/healthy`
- **Dependencies**: `prometheus`

### API Gateway

#### Traefik (`traefik`)
- **Image**: `traefik:v3.0`
- **Ports**: `80`, `443`, `8080` (dashboard)
- **Volumes**:
  - `/var/run/docker.sock:/var/run/docker.sock:ro`
  - `./infrastructure/traefik/traefik.yml:/etc/traefik/traefik.yml:ro`
  - `./infrastructure/traefik/dynamic:/etc/traefik/dynamic:ro`
  - `traefik-letsencrypt:/letsencrypt`
- **Health Check**: `wget --quiet --tries=1 --spider http://localhost:8080/ping`
- **Dependencies**: `jaeger`
- **Configuration**: Docker provider, file provider, Let's Encrypt, Jaeger tracing

### Prefect Services

#### Prefect Server (`prefect-server`)
- **Image**: `prefecthq/prefect:2-python3.12`
- **Ports**: `4200` (API), `4201` (UI)
- **Dependencies**: `prefect-db`
- **Health Check**: `curl -f http://localhost:4200/health`
- **Environment Variables**:
  - `PREFECT_API_URL`, `PREFECT_API_DATABASE_CONNECTION_URL`, `PREFECT_LOGGING_LEVEL`

#### Prefect Database (`prefect-db`)
- **Image**: `postgres:16-alpine`
- **Port**: `5433` (configurable via `PREFECT_DB_PORT`)
- **Volumes**: `prefect-db-data:/var/lib/postgresql/data`
- **Health Check**: `pg_isready -U prefect`
- **Environment Variables**:
  - `POSTGRES_USER=prefect`
  - `POSTGRES_PASSWORD` (configurable via `PREFECT_DB_PASSWORD`)
  - `POSTGRES_DB=prefect`

#### Prefect Worker (`prefect-worker`)
- **Image**: `prefecthq/prefect:2-python3.12`
- **Command**: `prefect worker start --pool default --type process`
- **Dependencies**: `prefect-server`
- **Health Check**: `ps aux | grep '[p]refect worker'`
- **Environment Variables**:
  - `PREFECT_API_URL`, `PREFECT_LOGGING_LEVEL`, `PREFECT_API_KEY`

#### Prefect Integration Service (`prefect-integration-service`)
- **Build**: `services/prefect-integration/Dockerfile`
- **Port**: `8084` (configurable via `PREFECT_INTEGRATION_PORT`)
- **Dependencies**: `prefect-server`, `postgres`
- **Health Check**: `curl -f http://localhost:8084/health`
- **Environment Variables**:
  - `PREFECT_API_URL`, `PREFECT_API_KEY`, `DATABASE_URL`, `LOG_LEVEL`, `ENVIRONMENT`

## Network Configuration

### Hub Network (`hub-net`)
- **Driver**: `bridge`
- **Purpose**: Connects all services for internal communication
- **All services are connected to this network**

## Volume Configuration

### Persistent Volumes
- `pgdata`: PostgreSQL data
- `redis-data`: Redis data
- `minio-data`: MinIO object storage data
- `fuseki-data`: Fuseki triple store data
- `prometheus-data`: Prometheus metrics storage
- `grafana-data`: Grafana dashboards and configuration
- `alertmanager-data`: Alertmanager state
- `prefect-server-data`: Prefect server data
- `prefect-db-data`: Prefect database data
- `traefik-letsencrypt`: Traefik Let's Encrypt certificates

## Service Dependencies

### Dependency Graph

```
postgres ──┬── api-service
           ├── worker-service
           ├── workflow-engine-service
           ├── workflow-registry-service
           ├── event-bus-health-service
           ├── event-schema-registry-service
           ├── search-service
           ├── observability-service
           ├── webhook-service
           └── prefect-integration-service

redis ──┬── api-service
       ├── worker-service
       └── workflow-engine-service
       └── event-bus-health-service

minio ──└── api-service

fuseki ──└── semantic-service

jaeger ──┬── workflow-engine-service
        ├── workflow-registry-service
        ├── event-bus-health-service
        ├── event-schema-registry-service
        ├── api-service
        ├── worker-service
        └── traefik

prometheus ──└── observability-service

prefect-server ──┬── prefect-worker
                 └── prefect-integration-service

prefect-db ──└── prefect-server
```

## Health Checks

All services implement health checks with the following pattern:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:PORT/endpoint"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s  # For services that need startup time
```

### Health Check Endpoints

- **API Service**: `/health`
- **Worker Service**: `/healthz`
- **Workflow Engine Service**: `/healthz`
- **Workflow Registry Service**: `/health`
- **Event Bus Health Service**: `/healthz`
- **Event Schema Registry Service**: `/health`
- **All Microservices**: `/health`

## Environment Variables

### Common Environment Variables

All services use these common environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `DJANGO_SETTINGS_MODULE`: Django settings module (default: `hub.settings`)
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (default: `False`)
- `ALLOWED_HOSTS`: Allowed hostnames
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `ENVIRONMENT`: Environment name (default: `development`)
- `APP_VERSION`: Application version (default: `1.0.0`)

### OpenTelemetry Configuration

Services with tracing enabled use:

- `OPENTELEMETRY_ENABLED`: Enable OpenTelemetry (default: `true`)
- `OPENTELEMETRY_METRICS_ENABLED`: Enable metrics (default: `true`)
- `JAEGER_AGENT_HOST`: Jaeger agent hostname (default: `jaeger`)
- `JAEGER_AGENT_PORT`: Jaeger agent port (default: `6831`)

## Prometheus Scraping

Prometheus scrapes metrics from all services via the `/metrics` endpoint:

- `api-service:8000/metrics`
- `worker-service:8080/metrics`
- `workflow-engine-service:8088/metrics`
- `workflow-registry-service:8089/metrics`
- `event-bus-health-service:8090/metrics`
- `event-schema-registry-service:8091/metrics`
- `semantic-service:8081/metrics`
- `dq-service:8083/metrics`
- `compliance-service:8082/metrics`
- `datacontract-service:8080/metrics`
- `prefect-integration-service:8084/metrics`
- `search-service:8085/metrics`
- `observability-service:8086/metrics`
- `webhook-service:8087/metrics`

## Service Startup Order

Services start in dependency order:

1. **Infrastructure**: `postgres`, `redis`, `minio`, `fuseki`
2. **Monitoring**: `prometheus`, `grafana`, `jaeger`, `alertmanager`
3. **Orchestration**: `prefect-db`, `prefect-server`, `prefect-worker`
4. **Application Services**: `api-service`, `worker-service`, `workflow-engine-service`, `workflow-registry-service`, `event-bus-health-service`, `event-schema-registry-service`
5. **Microservices**: `semantic-service`, `dq-service`, `compliance-service`, `datacontract-service`, `search-service`, `observability-service`, `webhook-service`
6. **API Gateway**: `traefik`

## Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache/queue |
| `minio` | 9000, 9001 | Object storage API, Console |
| `fuseki` | 3030 | Triple store |
| `api-service` | 8000 | Django API |
| `worker-service` | 8080 | Worker health |
| `semantic-service` | 8081 | Semantic service |
| `compliance-service` | 8082 | Compliance service |
| `dq-service` | 8083 | Data quality service |
| `prefect-integration-service` | 8084 | Prefect integration |
| `search-service` | 8085 | Search service |
| `observability-service` | 8086 | Observability service |
| `webhook-service` | 8087 | Webhook service |
| `workflow-engine-service` | 8088 | Workflow engine health |
| `workflow-registry-service` | 8089 | Workflow registry |
| `event-bus-health-service` | 8090 | Event bus health |
| `event-schema-registry-service` | 8091 | Event schema registry |
| `prometheus` | 9090 | Prometheus metrics |
| `alertmanager` | 9093 | Alertmanager |
| `grafana` | 3000 | Grafana dashboards |
| `jaeger` | 16686, 14268, 6831 | Jaeger UI, HTTP collector, UDP collector |
| `prefect-server` | 4200, 4201 | Prefect API, UI |
| `prefect-db` | 5433 | Prefect database |
| `traefik` | 80, 443, 8080 | HTTP, HTTPS, Dashboard |

## Best Practices

### Service Configuration

1. **Always use health checks**: All services should have health checks configured
2. **Set dependencies**: Use `depends_on` with `condition: service_healthy` for proper startup order
3. **Use environment variables**: All configuration should be externalized via environment variables
4. **Configure volumes**: Use named volumes for persistent data
5. **Network isolation**: All services should be on `hub-net` network

### Health Checks

1. **Use appropriate intervals**: 30s for most services, 10s for critical infrastructure
2. **Set start periods**: Allow services time to start before health checks begin
3. **Use correct endpoints**: Use `/healthz` for liveness, `/ready` for readiness
4. **Handle failures gracefully**: Set appropriate retry counts

### Environment Variables

1. **Use defaults**: Provide sensible defaults for all environment variables
2. **Use env_file**: Load common variables from `.env.dev` file
3. **Document variables**: Document all environment variables in service READMEs
4. **Use consistent naming**: Follow naming conventions (e.g., `SERVICE_NAME_PORT`)

### Monitoring

1. **Expose metrics**: All services should expose Prometheus metrics at `/metrics`
2. **Configure scraping**: Add all services to Prometheus scrape config
3. **Set up alerts**: Configure alert rules for critical services
4. **Enable tracing**: Enable OpenTelemetry tracing for distributed systems

## Troubleshooting

### Service Won't Start

1. Check service dependencies are healthy
2. Verify environment variables are set correctly
3. Check service logs: `docker compose logs SERVICE_NAME`
4. Verify health check endpoint is accessible

### Health Check Failing

1. Verify service is listening on the correct port
2. Check health check endpoint exists and returns 200
3. Verify health check command is correct
4. Check service logs for errors

### Service Communication Issues

1. Verify services are on the same network (`hub-net`)
2. Check service names are correct (use service name, not container name)
3. Verify ports are exposed correctly
4. Check firewall/security group settings

### Metrics Not Appearing

1. Verify Prometheus scrape config includes the service
2. Check service exposes `/metrics` endpoint
3. Verify Prometheus can reach the service
4. Check Prometheus targets page for errors

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Grafana Dashboards](../monitoring/grafana/dashboards/)
- [Workflow Monitoring Setup](../docs/WORKFLOW_MONITORING_SETUP.md)


---

# Service Startup Guide

Complete guide for starting all services for development and testing.

## Quick Start

### Start All Services (Development)

```bash
# Start all services in development environment
./scripts/start-all-services.sh --env dev

# Start without monitoring services (faster startup)
./scripts/start-all-services.sh --env dev --skip-monitoring

# Start without frontend (backend only)
./scripts/start-all-services.sh --env dev --skip-frontend

# Start only specific services
./scripts/start-all-services.sh --env dev --services postgres,redis,api-service
```

### Check Service Status

```bash
# Check status of all services
./scripts/start-all-services.sh --check-only --env dev

# Or use docker compose directly
docker compose -f docker-compose.dev.yml ps
```

### Stop Services

```bash
# Stop all services
docker compose -f docker-compose.dev.yml down

# Stop and remove volumes (WARNING: deletes all data)
docker compose -f docker-compose.dev.yml down -v
```

## Service Architecture

### Infrastructure Services (Start First)

These services must be started first as other services depend on them:

1. **PostgreSQL** (Port 5432)
   - Database for all application data
   - Health check: `pg_isready`

2. **Redis** (Port 6379)
   - Job queue and caching
   - Health check: `redis-cli ping`

3. **MinIO** (Ports 9000 API, 9001 Console)
   - Object storage for datasets and files
   - Health check: `curl http://localhost:9000/minio/health/live`

4. **Fuseki** (Port 3030)
   - RDF/SPARQL endpoint for semantic data
   - Health check: `curl http://localhost:3030/$/ping`

### Core Application Services

5. **API Service** (Port 8000)
   - Django REST API
   - Main API endpoint: `http://localhost:8000/api/v1/`
   - API Docs: `http://localhost:8000/api/v1/docs`

6. **Worker Service**
   - Background job processing (Django RQ)
   - Processes jobs from Redis queue

### Workflow Services

7. **Workflow Engine Service** (Port 8088)
   - Orchestrates multi-step workflows
   - Executes workflow definitions

8. **Workflow Registry Service** (Port 8089)
   - Stores and manages workflow definitions
   - Provides workflow discovery

### Event Bus Services

9. **Event Bus Health Service** (Port 8090)
   - Monitors event bus health
   - Provides event bus metrics

10. **Event Schema Registry Service** (Port 8091)
    - Manages event schemas
    - Validates event payloads

### Microservices

11. **Semantic Service** (Port 8081)
    - Semantic mapping and RDF operations
    - SPARQL query execution

12. **DQ Service** (Port 8083)
    - Data quality checks and validation
    - Quality rule execution

13. **Compliance Service** (Port 8082)
    - Compliance checking and reporting
    - Policy enforcement

14. **DataContract Service** (Port 8080)
    - Contract validation and management
    - Schema validation

15. **Search Service** (Port 8085)
    - Full-text search and indexing
    - Search query processing

16. **Observability Service** (Port 8086)
    - Metrics collection and aggregation
    - Performance monitoring

17. **Webhook Service** (Port 8087)
    - Webhook delivery and management
    - Event notifications

### Prefect Services

18. **Prefect DB** (Port 5433)
    - PostgreSQL database for Prefect
    - Workflow state storage

19. **Prefect Server** (Port 4200)
    - Prefect orchestration server
    - Workflow scheduling

20. **Prefect Worker**
    - Executes Prefect workflows
    - Task execution

21. **Prefect Integration Service** (Port 8084)
    - Integrates Prefect with Hub workflows
    - Workflow coordination

### Monitoring Services (Optional)

22. **Prometheus** (Port 9090)
    - Metrics collection and storage
    - Time-series database

23. **Grafana** (Port 3001)
    - Metrics visualization and dashboards
    - Alerting

24. **Jaeger** (Port 16686)
    - Distributed tracing
    - Request tracing

25. **Alertmanager** (Port 9093)
    - Alert routing and notification
    - Alert management

### API Gateway

26. **Traefik** (Port 80, 443)
    - Reverse proxy and load balancer
    - SSL termination
    - Service discovery

### Frontend (Development)

27. **Frontend Dev Server** (Port 3000)
    - React development server (Vite)
    - Hot module replacement
    - Runs separately: `cd frontend && npm run dev`

## Startup Order

Services must be started in this order:

1. **Infrastructure** (PostgreSQL, Redis, MinIO, Fuseki)
2. **Core Services** (API, Worker)
3. **Workflow Services** (Workflow Engine, Workflow Registry)
4. **Event Bus Services** (Event Bus Health, Event Schema Registry)
5. **Microservices** (Semantic, DQ, Compliance, DataContract, Search, Observability, Webhook)
6. **Prefect Services** (Prefect DB, Prefect Server, Prefect Worker, Prefect Integration)
7. **Monitoring** (Prometheus, Grafana, Jaeger, Alertmanager) - Optional
8. **API Gateway** (Traefik)
9. **Frontend** (npm run dev) - Optional, runs separately

## Environment Files

### Development Environment

Create `.env.dev` file in project root:

```bash
# Database
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub
POSTGRES_DB=hub
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# MinIO
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=minio123
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001

# Fuseki
FUSEKI_PORT=3030
FUSEKI_DATASET=hub
FUSEKI_ADMIN_PASSWORD=admin

# API Service
API_PORT=8000
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True

# Service URLs
DATACONTRACT_SERVICE_URL=http://localhost:8080
COMPLIANCE_SERVICE_URL=http://localhost:8082
DQ_SERVICE_URL=http://localhost:8083
SEMANTIC_SERVICE_URL=http://localhost:8081
SEARCH_SERVICE_URL=http://localhost:8085
OBSERVABILITY_SERVICE_URL=http://localhost:8086
WEBHOOK_SERVICE_URL=http://localhost:8087

# Frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_GRAPHQL_URL=http://localhost:8000/graphql
```

## Service Health Checks

### Check Individual Service Health

```bash
# API Service
curl http://localhost:8000/api/v1/health

# Semantic Service
curl http://localhost:8081/health

# DQ Service
curl http://localhost:8083/health

# Compliance Service
curl http://localhost:8082/health

# DataContract Service
curl http://localhost:8080/health
```

### Check All Services

```bash
# Using the startup script
./scripts/start-all-services.sh --check-only --env dev

# Or manually check each service
for port in 8000 8080 8081 8082 8083 8085 8086 8087; do
    echo "Checking port $port..."
    curl -f http://localhost:$port/health || echo "Service on port $port is not healthy"
done
```

## Troubleshooting

### Service Won't Start

1. **Check Docker is running**:
   ```bash
   docker info
   ```

2. **Check port conflicts**:
   ```bash
   # Check if ports are in use
   netstat -tuln | grep -E ':(5432|6379|8000|8080|8081|8082|8083)'
   ```

3. **Check logs**:
   ```bash
   docker compose -f docker-compose.dev.yml logs [service-name]
   ```

4. **Check service dependencies**:
   ```bash
   # Ensure infrastructure services are healthy
   docker compose -f docker-compose.dev.yml ps
   ```

### Service is Unhealthy

1. **Check service logs**:
   ```bash
   docker compose -f docker-compose.dev.yml logs -f [service-name]
   ```

2. **Restart the service**:
   ```bash
   docker compose -f docker-compose.dev.yml restart [service-name]
   ```

3. **Check service dependencies**:
   - Ensure PostgreSQL is accessible
   - Ensure Redis is accessible
   - Ensure other required services are running

### Database Connection Issues

1. **Check PostgreSQL is running**:
   ```bash
   docker compose -f docker-compose.dev.yml exec postgres pg_isready -U hub
   ```

2. **Check database credentials**:
   ```bash
   # Verify .env.dev has correct credentials
   cat .env.dev | grep POSTGRES
   ```

3. **Run migrations**:
   ```bash
   docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate
   ```

### Frontend Won't Start

1. **Check Node.js version**:
   ```bash
   node --version  # Should be 18.x or higher
   ```

2. **Install dependencies**:
   ```bash
   cd frontend && npm install
   ```

3. **Check environment variables**:
   ```bash
   # Verify frontend/.env has correct API URLs
   cat frontend/.env
   ```

## Development Workflow

### Starting Services for Development

1. **Start infrastructure and backend**:
   ```bash
   ./scripts/start-all-services.sh --env dev --skip-frontend
   ```

2. **Start frontend separately** (in another terminal):
   ```bash
   cd frontend && npm run dev
   ```

3. **Verify services are running**:
   ```bash
   ./scripts/start-all-services.sh --check-only --env dev
   ```

### Starting Services for Testing

1. **Start all services**:
   ```bash
   ./scripts/start-all-services.sh --env dev
   ```

2. **Run tests**:
   ```bash
   # Backend tests
   pytest

   # Frontend tests
   cd frontend && npm test
   ```

3. **Stop services after testing**:
   ```bash
   docker compose -f docker-compose.dev.yml down
   ```

## Service URLs Summary

| Service | URL | Description |
|---------|-----|-------------|
| API Service | http://localhost:8000 | Main API endpoint |
| API Docs | http://localhost:8000/api/v1/docs | API documentation |
| Frontend | http://localhost:3000 | Frontend application |
| MinIO Console | http://localhost:9001 | Object storage console |
| Grafana | http://localhost:3001 | Metrics dashboards |
| Prometheus | http://localhost:9090 | Metrics database |
| Jaeger | http://localhost:16686 | Distributed tracing |
| Fuseki | http://localhost:3030 | SPARQL endpoint |
| Prefect Server | http://localhost:4200 | Prefect UI |

## Next Steps

After starting all services:

1. **Run database migrations**:
   ```bash
   docker compose -f docker-compose.dev.yml exec api-service python manage.py migrate
   ```

2. **Create superuser** (if needed):
   ```bash
   docker compose -f docker-compose.dev.yml exec api-service python manage.py createsuperuser
   ```

3. **Access the application**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000/api/v1/
   - API Docs: http://localhost:8000/api/v1/docs

4. **Start developing**:
   - Backend: Edit code in `hub/` or `services/`
   - Frontend: Edit code in `frontend/src/`
   - Services will hot-reload automatically


---

# Self-Service Tenant Onboarding

**Last Updated**: 2026-03-22

This document describes the self-service tenant onboarding process.

---

## Overview

New tenants can create accounts and start using the platform through a self-service onboarding process. The onboarding creates a tenant, first user (tenant admin), and assigns a default plan.

---

## Onboarding Endpoint

### Create Tenant with First User

**POST** `/api/v1/tenants/onboarding/` (also available at `/api/v1/tenants/config/onboarding/`)

Creates a new tenant with first user (tenant admin).

**Authentication**: Not required (public endpoint)

**Request Body**:
```json
{
  "name": "My Company",
  "slug": "my-company",
  "plan_slug": "free",
  "first_user": {
    "email": "admin@example.com",
    "password": "securepassword123",
    "display_name": "Admin User"
  },
  "region": "us-east-1"
}
```

**Response**:
```json
{
  "tenant": {
    "id": "uuid",
    "name": "My Company",
    "slug": "my-company",
    "status": "ACTIVE",
    "plan": "plan-uuid"
  },
  "user": {
    "id": "uuid",
    "email": "admin@example.com",
    "display_name": "Admin User",
    "status": "ACTIVE"
  },
  "subscription_id": "uuid",
  "plan": {
    "slug": "free",
    "name": "Free Plan",
    "tier": "FREE"
  }
}
```

---

## Request Fields

### Required Fields

- **name**: Tenant name (e.g., "My Company")
- **slug**: URL-safe tenant identifier (e.g., "my-company")
- **first_user.email**: Email address for first user
- **first_user.password**: Password for first user

### Optional Fields

- **plan_slug**: Plan slug (defaults to "free")
- **first_user.display_name**: Display name for first user (defaults to email username)
- **region**: Cloud region (optional, informational)

---

## Validation

### Email Uniqueness

- Email must be unique across the platform
- If email already exists, returns `400 Bad Request` with code `EMAIL_EXISTS`

### Slug Uniqueness

- Slug must be unique across all tenants
- If slug already exists, returns `400 Bad Request` with code `SLUG_EXISTS`

### Slug Format

- Slug must contain only lowercase letters, numbers, hyphens, and underscores
- Automatically converted to lowercase

---

## What Gets Created

### Tenant

- **Status**: `ACTIVE`
- **KYC Status**: `UNVERIFIED`
- **Plan**: Assigned plan (defaults to FREE)
- **Region**: Optional region (informational)

### First User

- **Email**: Provided email address
- **Password**: Hashed and stored securely
- **Display Name**: Provided display name or email username
- **Status**: `ACTIVE`
- **Role**: `TENANT_ADMIN` (full tenant access)

### Tenant Configuration

- **Default DQ Profile**: Platform default
- **Allowed Compliance Regimes**: Platform defaults
- **Rate Limits**: Platform defaults
- **Job Concurrency**: Platform defaults

### Subscription

- **FREE Plan**: Subscription created without Stripe
- **PRO/ENTERPRISE Plans**: Stripe customer and subscription created (with trial if PRO)

---

## Plan Selection

### Default Plan

- **Default**: FREE plan if `plan_slug` not specified
- **Available Plans**: FREE, PRO, ENTERPRISE

### Plan Features

See `docs/BILLING.md` for plan details and limits.

---

## Post-Onboarding

### Login

After onboarding, the first user can log in:

**POST** `/api/v1/auth/login/`

```json
{
  "email": "admin@example.com",
  "password": "securepassword123"
}
```

### Access

- **Tenant Admin**: Full access to tenant resources
- **Plan Limits**: Subject to plan limits (see `docs/BILLING.md`)
- **API Access**: Can create API keys for programmatic access

---

## Rate Limiting

- **Public Endpoint**: Onboarding endpoint is public (no authentication required)
- **Rate Limiting**: May be rate-limited to prevent abuse
- **IP-based**: Rate limiting may be IP-based

---

## Security Considerations

### Password Requirements

- **Minimum length**: Check password requirements
- **Complexity**: Follow platform password policy
- **Storage**: Passwords hashed using secure hashing algorithm

### Email Verification

- **Optional**: Email verification may be required (check configuration)
- **Invitation**: First user created as ACTIVE (not INVITED)

### Tenant Isolation

- **Immediate isolation**: Tenant data isolated immediately upon creation
- **Scoping**: All operations scoped to tenant

---

## Error Handling

### Validation Errors

- **400 Bad Request**: Invalid input data
- **Error codes**: `EMAIL_EXISTS`, `SLUG_EXISTS`, `PLAN_NOT_FOUND`

### Stripe Errors

- **Non-blocking**: Stripe subscription creation failures don't block tenant creation
- **Logged**: Stripe errors logged for investigation
- **Fallback**: FREE plan subscription created if Stripe fails

---

## Use Cases

### New Customer Signup

- **Self-service**: Customers can sign up without manual intervention
- **Immediate access**: Access granted immediately after signup
- **Plan selection**: Customers can choose plan during signup

### Trial Signup

- **PRO Plan**: Customers can sign up for PRO plan with trial
- **Trial period**: 14-day trial for PRO plan
- **Conversion**: Trial converts to paid subscription after trial period

---

---

## Personal Tenant (Self-Service Registration)

**Endpoint**: `POST /api/v1/auth/register/`

When a user registers **without** providing `tenant_id`, the system creates a **personal tenant** for that user. This enables self-service onboarding: visitors can sign up and immediately use the platform without an invite or manual tenant assignment.

### Behavior

- **tenant_id omitted**: System creates a personal tenant (name: `Personal - {email}`, slug: `personal-{uuid8}`), assigns FREE plan, creates TenantConfig and Subscription, assigns `DATA_PROVIDER` and `DATA_CONSUMER` roles, and returns `tenant_id` in the response.
- **tenant_id provided**: User is associated with that tenant (unchanged behavior).

### What Gets Created

- **Tenant**: ACTIVE, KYC UNVERIFIED, FREE plan
- **TenantConfig**: Platform defaults
- **Subscription**: ACTIVE, FREE plan
- **User roles**: DATA_PROVIDER, DATA_CONSUMER

### Post-Registration

The user can immediately:
- Create assets in their personal tenant
- Access marketplace listings (as DATA_CONSUMER)
- Use platform features subject to FREE plan limits

### Feature Flag

`PERSONAL_TENANT_ON_REGISTRATION` (default: True). When False, legacy behavior: user created with `tenant=None`.

### Troubleshooting

See [Personal tenant creation failures](RUNBOOKS.md#personal-tenant-creation-failures) runbook for FREE plan missing, slug collision, and subscription creation failures.

---

## Tenant Switch

Users with multiple tenants (e.g. personal tenant + org tenant via invitation) can switch active tenant context without re-login.

### How It Works

- **GET /auth/me/tenants/** — Returns list of tenants the user has membership in
- **POST /auth/switch-tenant/** — Validates membership and returns updated me summary with `tenant_id` overridden
- **X-Tenant-Id header** — Clients send this header on subsequent requests to scope operations to the switched tenant

### Prerequisites

- User has membership in at least two tenants (UserTenantMembership)
- `FEATURE_TENANT_SWITCH_ENABLED` is true (default)

### Feature Flag

`FEATURE_TENANT_SWITCH_ENABLED` (default: True). When False, tenant switch API returns 403 and X-Tenant-Id is rejected.

See [TENANT_SWITCH_PLAN.md](TENANT_SWITCH_PLAN.md) for production migration and rollback. See [Tenant switch failures](RUNBOOKS.md#tenant-switch-failures) runbook for troubleshooting.

---

## Related Documentation

- `docs/BILLING.md` - Plans, limits, and billing
- `docs/TENANT_ISOLATION.md` - Tenant isolation and multi-tenancy
- `docs/DATA_RESIDENCY.md` - Data residency and regional considerations
- `docs/API_REFERENCE.md` - POST /auth/register/, tenant switch endpoints
- `docs/TENANT_SWITCH_PLAN.md` - Tenant switch migration and rollback

---

# Landing Page

**Last Updated**: 2026-03-22

## Scope

The **public landing page** is implemented **frontend-only**. The backend does not serve a dedicated landing route; the SPA handles the root path with an auth-based switch.

## Behaviour

- **Route:** Single route `/` (no separate `/landing`).
- **Unauthenticated:** At `/`, the frontend shows the **Landing** component (hero, value proposition, Sign in and Create account links). No redirect to `/login`; the user stays on `/`.
- **Authenticated:** At `/`, the frontend shows the **App shell** and **Dashboard** (current home). No redirect.
- **Auth check:** The frontend uses the auth store (Zustand) and shows a loading state until initialization completes, then renders either Landing or ProtectedRoute + AppShell.

## Backend

No backend change is required for the landing page. The Hub API does not serve HTML for `/`; it exposes API routes under `/api/v1/`, `/health/`, etc. The SPA is typically served by a static server or reverse proxy (e.g. Vite dev server, or nginx serving the built frontend). Unauthenticated access to the landing is entirely handled by the frontend; no backend auth bypass or special route is needed.

## References

- [FEATURES.md](FEATURES.md) — Visitor persona and public capabilities (optional landing)
- [USER_JOURNEYS.md](USER_JOURNEYS.md) — JOURNEY-AUTH-001–004 (Visitor / Authentication)
- [USE_CASES.md](USE_CASES.md) — UC-AUTH-004 (Unauthenticated user accesses public resources)
