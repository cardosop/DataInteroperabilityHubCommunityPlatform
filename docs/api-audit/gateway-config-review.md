# Gateway Configuration Review Report

**Generated:** 2025-12-28T14:15:36.389602

## Summary

- **Traefik Configs:** 2
- **Traefik Routers:** 15
- **Traefik Services:** 15
- **Traefik Middlewares:** 4
- **Ingress Files:** 13
- **Ingress Rules:** 14
- **Total Issues:** 0
- **Mapped Endpoints:** 517

## Traefik Configuration Review

### Configuration Files (2)

- **infrastructure/traefik/dynamic/routes.yml** (docker-compose)
- **k8s/api-gateway/traefik/configmap.yaml** (kubernetes)

### Routers (15)

- **api-gateway**
  - Path Prefix: `None`
  - Service: `api-service`
  - Middlewares: auth-middleware, rate-limit-middleware, cors-middleware
- **contract-service**
  - Path Prefix: `/api/v1/contracts`
  - Service: `contract-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **asset-service**
  - Path Prefix: `/api/v1/assets`
  - Service: `asset-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **dataset-service**
  - Path Prefix: `/api/v1/datasets`
  - Service: `dataset-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **search-service**
  - Path Prefix: `/api/v1/search`
  - Service: `search-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **observability-service**
  - Path Prefix: `/api/v1/observability`
  - Service: `observability-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **webhook-service**
  - Path Prefix: `/api/v1/webhooks`
  - Service: `webhook-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **semantic-service**
  - Path Prefix: `/api/v1/semantic`
  - Service: `semantic-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **lineage-service**
  - Path Prefix: `/api/v1/lineage`
  - Service: `lineage-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **governance-service**
  - Path Prefix: `/api/v1/governance`
  - Service: `governance-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **ingestion-service**
  - Path Prefix: `/api/v1/ingestion`
  - Service: `ingestion-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **versioning-service**
  - Path Prefix: `/api/v1/versioning`
  - Service: `versioning-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **dq-service**
  - Path Prefix: `/api/v1/dq`
  - Service: `dq-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **compliance-service**
  - Path Prefix: `/api/v1/compliance`
  - Service: `compliance-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware
- **normalization-service**
  - Path Prefix: `/api/v1/normalization`
  - Service: `normalization-service`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

## Kubernetes Ingress Review

### Ingress Files (13)

- **k8s/search-service/base/ingress.yaml**
  - Name: `search-service-ingress`
  - Namespace: `default`
- **k8s/webhook-service/base/ingress.yaml**
  - Name: `webhook-service-ingress`
  - Namespace: `default`
- **k8s/prometheus/base/ingress.yaml**
  - Name: `prometheus-ingress`
  - Namespace: `monitoring`
- **k8s/semantic-service/base/ingress.yaml**
  - Name: `semantic-service-ingress`
  - Namespace: `default`
- **k8s/dq-service/base/ingress.yaml**
  - Name: `dq-service-ingress`
  - Namespace: `default`
- **k8s/api-service/base/ingress.yaml**
  - Name: `api-service-ingress`
  - Namespace: `default`
- **k8s/compliance-service/base/ingress.yaml**
  - Name: `compliance-service-ingress`
  - Namespace: `default`
- **k8s/jaeger/base/ingress.yaml**
  - Name: `jaeger-ingress`
  - Namespace: `monitoring`
- **k8s/prefect-server/base/ingress.yaml**
  - Name: `prefect-server-ingress`
  - Namespace: `prefect`
- **k8s/grafana/base/ingress.yaml**
  - Name: `grafana-ingress`
  - Namespace: `monitoring`
- **k8s/prefect-integration/base/ingress.yaml**
  - Name: `prefect-integration-ingress`
  - Namespace: `default`
- **k8s/datacontract-service/base/ingress.yaml**
  - Name: `datacontract-service-ingress`
  - Namespace: `default`
- **k8s/observability-service/base/ingress.yaml**
  - Name: `observability-service-ingress`
  - Namespace: `default`

### Ingress Rules (14)

- **search-service-ingress**
  - Host: `search.example.com`
  - Path: `/`
  - Service: `search-service:8085`
- **webhook-service-ingress**
  - Host: `webhook.example.com`
  - Path: `/`
  - Service: `webhook-service:8087`
- **prometheus-ingress**
  - Host: `prometheus.example.com`
  - Path: `/`
  - Service: `prometheus:9090`
- **semantic-service-ingress**
  - Host: `semantic.example.com`
  - Path: `/`
  - Service: `semantic-service:8081`
- **dq-service-ingress**
  - Host: `dq.example.com`
  - Path: `/`
  - Service: `dq-service:8083`
- **api-service-ingress**
  - Host: `api.example.com`
  - Path: `/`
  - Service: `api-service:8000`
- **compliance-service-ingress**
  - Host: `compliance.example.com`
  - Path: `/`
  - Service: `compliance-service:8082`
- **jaeger-ingress**
  - Host: `jaeger.example.com`
  - Path: `/`
  - Service: `jaeger:16686`
- **prefect-server-ingress**
  - Host: `prefect-api.example.com`
  - Path: `/`
  - Service: `prefect-server:4200`
- **prefect-server-ingress**
  - Host: `prefect-ui.example.com`
  - Path: `/`
  - Service: `prefect-server:4201`
- **grafana-ingress**
  - Host: `grafana.example.com`
  - Path: `/`
  - Service: `grafana:3000`
- **prefect-integration-ingress**
  - Host: `prefect-integration.example.com`
  - Path: `/`
  - Service: `prefect-integration-service:8084`
- **datacontract-service-ingress**
  - Host: `datacontract.example.com`
  - Path: `/`
  - Service: `datacontract-service:8080`
- **observability-service-ingress**
  - Host: `observability.example.com`
  - Path: `/`
  - Service: `observability-service:8086`

## Gateway to Endpoint Mappings

### Traefik Route Mappings (14)

- **contract-service** (`/api/v1/contracts`)
  - Service: `contract-service`
  - Endpoints: 49
- **asset-service** (`/api/v1/assets`)
  - Service: `asset-service`
  - Endpoints: 22
- **dataset-service** (`/api/v1/datasets`)
  - Service: `dataset-service`
  - Endpoints: 10
- **search-service** (`/api/v1/search`)
  - Service: `search-service`
  - Endpoints: 12
- **observability-service** (`/api/v1/observability`)
  - Service: `observability-service`
  - Endpoints: 0
- **webhook-service** (`/api/v1/webhooks`)
  - Service: `webhook-service`
  - Endpoints: 18
- **semantic-service** (`/api/v1/semantic`)
  - Service: `semantic-service`
  - Endpoints: 11
- **lineage-service** (`/api/v1/lineage`)
  - Service: `lineage-service`
  - Endpoints: 0
- **governance-service** (`/api/v1/governance`)
  - Service: `governance-service`
  - Endpoints: 68
- **ingestion-service** (`/api/v1/ingestion`)
  - Service: `ingestion-service`
  - Endpoints: 0
- **versioning-service** (`/api/v1/versioning`)
  - Service: `versioning-service`
  - Endpoints: 0
- **dq-service** (`/api/v1/dq`)
  - Service: `dq-service`
  - Endpoints: 16
- **compliance-service** (`/api/v1/compliance`)
  - Service: `compliance-service`
  - Endpoints: 10
- **normalization-service** (`/api/v1/normalization`)
  - Service: `normalization-service`
  - Endpoints: 0

### Ingress Rule Mappings (14)

- **search-service-ingress** (`search.example.com`)
  - Service: `search-service`
  - Endpoints: 517
- **webhook-service-ingress** (`webhook.example.com`)
  - Service: `webhook-service`
  - Endpoints: 517
- **prometheus-ingress** (`prometheus.example.com`)
  - Service: `prometheus`
  - Endpoints: 517
- **semantic-service-ingress** (`semantic.example.com`)
  - Service: `semantic-service`
  - Endpoints: 517
- **dq-service-ingress** (`dq.example.com`)
  - Service: `dq-service`
  - Endpoints: 517
- **api-service-ingress** (`api.example.com`)
  - Service: `api-service`
  - Endpoints: 517
- **compliance-service-ingress** (`compliance.example.com`)
  - Service: `compliance-service`
  - Endpoints: 517
- **jaeger-ingress** (`jaeger.example.com`)
  - Service: `jaeger`
  - Endpoints: 517
- **prefect-server-ingress** (`prefect-api.example.com`)
  - Service: `prefect-server`
  - Endpoints: 517
- **prefect-server-ingress** (`prefect-ui.example.com`)
  - Service: `prefect-server`
  - Endpoints: 517
- **grafana-ingress** (`grafana.example.com`)
  - Service: `grafana`
  - Endpoints: 517
- **prefect-integration-ingress** (`prefect-integration.example.com`)
  - Service: `prefect-integration-service`
  - Endpoints: 517
- **datacontract-service-ingress** (`datacontract.example.com`)
  - Service: `datacontract-service`
  - Endpoints: 517
- **observability-service-ingress** (`observability.example.com`)
  - Service: `observability-service`
  - Endpoints: 517

