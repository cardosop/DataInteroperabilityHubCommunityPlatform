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
