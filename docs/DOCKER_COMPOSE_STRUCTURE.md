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

