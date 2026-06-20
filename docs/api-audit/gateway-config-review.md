# Gateway Configuration Review Report

**Generated:** 2026-06-13T19:42:29.127072

## Summary

- **Traefik Configs:** 2
- **Traefik Routers:** 3
- **Traefik Services:** 12
- **Traefik Middlewares:** 2
- **Ingress Files:** 12
- **Ingress Rules:** 13
- **Total Issues:** 9
- **Mapped Endpoints:** 1247

## Traefik Configuration Review

### Configuration Files (2)

- **infrastructure/traefik/dynamic/routes.yml** (docker-compose)
- **k8s/api-gateway/traefik/configmap.yaml** (kubernetes)

### Routers (3)

- **api-gateway**
  - Path Prefix: `/api/v1`
  - Service: `api-gateway-service`
  - Middlewares: cors-middleware, tracing-middleware
- **api-gateway-host**
  - Path Prefix: `None`
  - Service: `api-gateway-service`
  - Middlewares: cors-middleware, tracing-middleware
- **frontend**
  - Path Prefix: `/`
  - Service: `frontend-service`
  - Middlewares: cors-middleware, tracing-middleware

## Kubernetes Ingress Review

### Ingress Files (12)

- **k8s/observability-service/base/ingress.yaml**
  - Name: `observability-service-ingress`
  - Namespace: `default`
- **k8s/datacontract-service/base/ingress.yaml**
  - Name: `datacontract-service-ingress`
  - Namespace: `default`
- **k8s/prefect-integration/base/ingress.yaml**
  - Name: `prefect-integration-ingress`
  - Namespace: `default`
- **k8s/grafana/base/ingress.yaml**
  - Name: `grafana-ingress`
  - Namespace: `monitoring`
- **k8s/prefect-server/base/ingress.yaml**
  - Name: `prefect-server-ingress`
  - Namespace: `prefect`
- **k8s/jaeger/base/ingress.yaml**
  - Name: `jaeger-ingress`
  - Namespace: `monitoring`
- **k8s/compliance-service/base/ingress.yaml**
  - Name: `compliance-service-ingress`
  - Namespace: `default`
- **k8s/api-service/base/ingress.yaml**
  - Name: `api-service-ingress`
  - Namespace: `default`
- **k8s/semantic-service/base/ingress.yaml**
  - Name: `semantic-service-ingress`
  - Namespace: `default`
- **k8s/prometheus/base/ingress.yaml**
  - Name: `prometheus-ingress`
  - Namespace: `monitoring`
- **k8s/webhook-service/base/ingress.yaml**
  - Name: `webhook-service-ingress`
  - Namespace: `default`
- **k8s/search-service/base/ingress.yaml**
  - Name: `search-service-ingress`
  - Namespace: `default`

### Ingress Rules (13)

- **observability-service-ingress**
  - Host: `observability.example.com`
  - Path: `/`
  - Service: `observability-service:8086`
- **datacontract-service-ingress**
  - Host: `datacontract.example.com`
  - Path: `/`
  - Service: `datacontract-service:8080`
- **prefect-integration-ingress**
  - Host: `prefect-integration.example.com`
  - Path: `/`
  - Service: `prefect-integration-service:8084`
- **grafana-ingress**
  - Host: `grafana.example.com`
  - Path: `/`
  - Service: `grafana:3000`
- **prefect-server-ingress**
  - Host: `prefect-api.example.com`
  - Path: `/`
  - Service: `prefect-server:4200`
- **prefect-server-ingress**
  - Host: `prefect-ui.example.com`
  - Path: `/`
  - Service: `prefect-server:4201`
- **jaeger-ingress**
  - Host: `jaeger.example.com`
  - Path: `/`
  - Service: `jaeger:16686`
- **compliance-service-ingress**
  - Host: `compliance.example.com`
  - Path: `/`
  - Service: `compliance-service:8082`
- **api-service-ingress**
  - Host: `api.example.com`
  - Path: `/`
  - Service: `api-service:8000`
- **semantic-service-ingress**
  - Host: `semantic.example.com`
  - Path: `/`
  - Service: `semantic-service:8081`
- **prometheus-ingress**
  - Host: `prometheus.example.com`
  - Path: `/`
  - Service: `prometheus:9090`
- **webhook-service-ingress**
  - Host: `webhook.example.com`
  - Path: `/`
  - Service: `webhook-service:8087`
- **search-service-ingress**
  - Host: `search.example.com`
  - Path: `/`
  - Service: `search-service:8085`

## Gateway to Endpoint Mappings

### Traefik Route Mappings (2)

- **api-gateway** (`/api/v1`)
  - Service: `api-gateway-service`
  - Endpoints: 1247
- **frontend** (`/`)
  - Service: `frontend-service`
  - Endpoints: 1247

### Ingress Rule Mappings (13)

- **observability-service-ingress** (`observability.example.com`)
  - Service: `observability-service`
  - Endpoints: 1247
- **datacontract-service-ingress** (`datacontract.example.com`)
  - Service: `datacontract-service`
  - Endpoints: 1247
- **prefect-integration-ingress** (`prefect-integration.example.com`)
  - Service: `prefect-integration-service`
  - Endpoints: 1247
- **grafana-ingress** (`grafana.example.com`)
  - Service: `grafana`
  - Endpoints: 1247
- **prefect-server-ingress** (`prefect-api.example.com`)
  - Service: `prefect-server`
  - Endpoints: 1247
- **prefect-server-ingress** (`prefect-ui.example.com`)
  - Service: `prefect-server`
  - Endpoints: 1247
- **jaeger-ingress** (`jaeger.example.com`)
  - Service: `jaeger`
  - Endpoints: 1247
- **compliance-service-ingress** (`compliance.example.com`)
  - Service: `compliance-service`
  - Endpoints: 1247
- **api-service-ingress** (`api.example.com`)
  - Service: `api-service`
  - Endpoints: 1247
- **semantic-service-ingress** (`semantic.example.com`)
  - Service: `semantic-service`
  - Endpoints: 1247
- **prometheus-ingress** (`prometheus.example.com`)
  - Service: `prometheus`
  - Endpoints: 1247
- **webhook-service-ingress** (`webhook.example.com`)
  - Service: `webhook-service`
  - Endpoints: 1247
- **search-service-ingress** (`search.example.com`)
  - Service: `search-service`
  - Endpoints: 1247

## Issues

- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router
- **INFO**: Service defined but not referenced by any router

