# Infrastructure Impact Analysis

**Generated:** 2025-12-28T15:00:58.445457

## Executive Summary

This report provides a comprehensive analysis of all infrastructure components in the Data Interoperability Hub platform, including Docker Compose services, Kubernetes resources, monitoring configurations, API gateway rules, rate limiting configurations, and CI/CD workflows.

### Key Statistics

- **Docker Compose Services**: 26
- **Kubernetes Components**: 153
- **Infrastructure Services**: 4
- **Application Services**: 13
- **Monitoring Services**: 4
- **Gateway Services**: 1
- **Orchestration Services**: 4

## Docker Compose Infrastructure

### Infrastructure Services

- **postgres**
  - Image: `postgres:16-alpine`
  - Ports: ${POSTGRES_PORT:-5432}:5432

- **redis**
  - Image: `redis:7-alpine`
  - Ports: ${REDIS_PORT:-6379}:6379

- **minio**
  - Image: `minio/minio:latest`
  - Ports: ${MINIO_API_PORT:-9000}:9000, ${MINIO_CONSOLE_PORT:-9001}:9001

- **fuseki**
  - Image: `stain/jena-fuseki:latest`
  - Ports: ${FUSEKI_PORT:-3030}:3030

### Application Services

- **semantic-service**
  - Image: `N/A`
  - Ports: ${SEMANTIC_PORT:-8081}:8081

- **api-service**
  - Image: `N/A`
  - Ports: ${API_PORT:-8000}:8000

- **worker-service**
  - Image: `N/A`
  - Ports: ${WORKER_HEALTH_PORT:-8080}:8080

- **workflow-engine-service**
  - Image: `N/A`
  - Ports: ${WORKFLOW_ENGINE_HEALTH_PORT:-8088}:8088

- **datacontract-service**
  - Image: `N/A`
  - Ports: ${DATACONTRACT_PORT:-8080}:8080

- **compliance-service**
  - Image: `N/A`
  - Ports: ${COMPLIANCE_PORT:-8082}:8082

- **dq-service**
  - Image: `N/A`
  - Ports: ${DQ_PORT:-8083}:8083

- **search-service**
  - Image: `N/A`
  - Ports: ${SEARCH_PORT:-8085}:8085

- **observability-service**
  - Image: `N/A`
  - Ports: ${OBSERVABILITY_PORT:-8086}:8086

- **webhook-service**
  - Image: `N/A`
  - Ports: ${WEBHOOK_PORT:-8087}:8087

- **event-bus-health-service**
  - Image: `N/A`
  - Ports: ${EVENT_BUS_HEALTH_PORT:-8090}:8090

- **event-schema-registry-service**
  - Image: `N/A`
  - Ports: ${EVENT_SCHEMA_REGISTRY_PORT:-8091}:8091

- **workflow-registry-service**
  - Image: `N/A`
  - Ports: ${WORKFLOW_REGISTRY_PORT:-8089}:8089

### Monitoring Services

- **prometheus**
  - Image: `prom/prometheus:latest`
  - Ports: ${PROMETHEUS_PORT:-9090}:9090

- **grafana**
  - Image: `grafana/grafana:latest`
  - Ports: ${GRAFANA_PORT:-3000}:3000

- **jaeger**
  - Image: `jaegertracing/all-in-one:latest`
  - Ports: ${JAEGER_UI_PORT:-16686}:16686, ${JAEGER_HTTP_PORT:-14268}:14268, ${JAEGER_UDP_PORT:-6831}:6831/udp

- **alertmanager**
  - Image: `prom/alertmanager:latest`
  - Ports: ${ALERTMANAGER_PORT:-9093}:9093

## Kubernetes Infrastructure

- **Services**: 23
- **Deployments**: 17
- **StatefulSets**: 6
- **ConfigMaps**: 23
- **Secrets**: 18
- **Persistent Volume Claims**: 7
- **Ingresses**: 13
- **Namespaces**: 42
- **Network Policies**: 4

## Monitoring and Observability

- **Endpoints Monitored**: 54
- **Prometheus Scrape Configs**: 17
- **Grafana Queries**: 308
- **Jaeger Operation Patterns**: 8

## API Gateway

- **Routing Rules**: 29
- **Rate Limiting Rules**: 2
- **Authentication Rules**: 2
- **Mapped Endpoints**: 234

## Rate Limiting

- **Categories**: 13
- **Rate Limit Rules**: 39
- **Endpoint Mappings**: 71

## CI/CD Infrastructure

- **Total Workflows**: 12
- **Endpoint References**: 56
- **Workflow Types**: 4

## Infrastructure Components List

### Infrastructure Services

- postgres
- redis
- minio
- fuseki

### Application Services

- semantic-service
- api-service
- worker-service
- workflow-engine-service
- datacontract-service
- compliance-service
- dq-service
- search-service
- observability-service
- webhook-service
- event-bus-health-service
- event-schema-registry-service
- workflow-registry-service

### Monitoring Services

- prometheus
- grafana
- jaeger
- alertmanager

### Gateway Services

- traefik

### Orchestration Services

- prefect-server
- prefect-db
- prefect-worker
- prefect-integration-service

## References

- CI/CD Workflows Review: `docs/api-audit/cicd-workflows-review.json`
- Monitoring Review: `monitoring_review_report.json`
- Rate Limiting Review: `docs/api-audit/rate-limiting-review.json`
- Gateway Rules Audit: `docs/api-audit/api-gateway-rules-audit.json`
