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

