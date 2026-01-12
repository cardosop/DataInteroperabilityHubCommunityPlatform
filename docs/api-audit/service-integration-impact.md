# Service Integration Impact Report

**Generated:** 2025-12-28T14:20:51.165638

## Summary

- **Total Services:** 31
- **Total Integrations:** 18
- **Total Service Calls:** 1920
- **Services Involved:** api-service, asset, cli, compliance-service, contract, datacontract, datacontract-service, dataset, dq, dq-service, event-bus-health-service, event-schema-registry-service, governance, grafana, ingestion, jaeger, lineage, normalization, observability-service, prefect-integration, prefect-server, prometheus, sdk, search-service, semantic-service, unknown, versioning, webhook-service, worker-service, workflow-engine-service, workflow-registry-service

## Service Integration Matrix

This matrix shows the number of service calls from each source service to each target service.


| Source → Target | api-service | asset | cli | compliance-service | contract | datacontract | datacontract-service | dataset | dq | dq-service | event-bus-health-service | event-schema-registry-service | governance | grafana | ingestion | jaeger | lineage | normalization | observability-service | prefect-integration | prefect-server | prometheus | sdk | search-service | semantic-service | unknown | versioning | webhook-service | worker-service | workflow-engine-service | workflow-registry-service |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| api-service | - | - | - | 79 | - | - | 59 | - | - | 123 | 1 | 1 | - | - | - | - | - | - | 1 | - | - | - | - | 1 | 106 | - | - | 1 | 131 | 1 | 1 |
| asset | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| cli | 126 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| compliance-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| contract | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| datacontract | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| datacontract-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| dataset | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| dq | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| dq-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| event-bus-health-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| event-schema-registry-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| governance | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| grafana | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| ingestion | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| jaeger | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| lineage | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| normalization | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| observability-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| prefect-integration | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| prefect-server | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| prometheus | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| sdk | 63 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| search-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| semantic-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| unknown | - | - | - | 54 | - | - | 31 | - | - | 82 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 99 | - | - | - | - | - | - |
| versioning | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| webhook-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| worker-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| workflow-engine-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| workflow-registry-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |


## Service Integration Details

### api-service

#### Outbound Integrations

- **worker-service**: 131 calls
  - Endpoints: redis-queue, http://datacontract-service:8080, http://localhost:8080, /health, unknown
  - ... and 2 more

- **dq-service**: 123 calls
  - Endpoints: unknown, /.dockerenv, http://dq-service-test:8083, http://dq-service:8083, http://localhost:8083
  - ... and 2 more

- **compliance-service**: 79 calls
  - Endpoints: unknown, http://compliance-service:8082, http://localhost:8082, /health

- **datacontract-service**: 59 calls
  - Endpoints: unknown, http://datacontract-service:8080, http://localhost:8080, /health, http://localhost:8080/webhooks/payment
  - ... and 1 more

- **semantic-service**: 106 calls
  - Endpoints: unknown, http://semantic-service:8081, http://localhost:8081, http://localhost:8081/health, /health

- **search-service**: 1 calls
  - Endpoints: /health

- **observability-service**: 1 calls
  - Endpoints: /health

- **webhook-service**: 1 calls
  - Endpoints: /health

- **workflow-engine-service**: 1 calls
  - Endpoints: /health

- **workflow-registry-service**: 1 calls
  - Endpoints: /healthz

- **event-bus-health-service**: 1 calls
  - Endpoints: /health

- **event-schema-registry-service**: 1 calls
  - Endpoints: unknown

#### Inbound Integrations

- **cli**: 126 calls
  - Endpoints: unknown, http://localhost:8000/api/v1, http://localhost:8000/api/v1/, /home/ph/Desktop/DataInteroperabilityHub, http://localhost:8000/api/v1/health/
  - ... and 5 more

- **sdk**: 63 calls
  - Endpoints: http://localhost:8000/api/v1, unknown, /home/ph/Desktop/DataInteroperabilityHub

#### Gateway Routes

- **Traefik Router**: api-gateway
  - Middlewares: auth-middleware, rate-limit-middleware, cors-middleware

- **Kubernetes Ingress**: api-service-ingress
  - Host: `api.example.com`
  - Path: `/`

#### Endpoints (27)

- `/.dockerenv`
- `/api/v1/dq/runs/`
- `/app/hub/manage.py`
- `/health`
- `/healthz`
- `/home/ph/Desktop/DataInteroperabilityHub`
- `http://127.0.0.1:8080/webhooks/payment`
- `http://compliance-service:8082`
- `http://datacontract-service:8080`
- `http://dq-service-test:8083`
- ... and 17 more endpoints

---

### asset

#### Gateway Routes

- **Traefik Router**: asset-service
  - Path Prefix: `/api/v1/assets`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/assets`

---

### cli

#### Outbound Integrations

- **api-service**: 126 calls
  - Endpoints: unknown, http://localhost:8000/api/v1, http://localhost:8000/api/v1/, /home/ph/Desktop/DataInteroperabilityHub, http://localhost:8000/api/v1/health/
  - ... and 5 more

#### Endpoints (10)

- `/app/hub/manage.py`
- `/home/ph/Desktop/DataInteroperabilityHub`
- `http://invalid-host:8000/api/v1`
- `http://localhost:8000/api/v1`
- `http://localhost:8000/api/v1/`
- `http://localhost:8000/api/v1/assets/assets/`
- `http://localhost:8000/api/v1/contracts/`
- `http://localhost:8000/api/v1/health/`
- `http://test.example.com/api/v1`
- `unknown`

---

### compliance-service

#### Inbound Integrations

- **api-service**: 79 calls
  - Endpoints: unknown, http://compliance-service:8082, http://localhost:8082, /health

- **unknown**: 54 calls
  - Endpoints: unknown

#### Gateway Routes

- **Traefik Router**: compliance-service
  - Path Prefix: `/api/v1/compliance`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

- **Kubernetes Ingress**: compliance-service-ingress
  - Host: `compliance.example.com`
  - Path: `/`

#### Service Clients

- **ComplianceServiceClient**
  - Base URL: `http://localhost:8082`
  - Methods: 2

#### Endpoints (6)

- `/api/v1/compliance`
- `/health`
- `/scan-file`
- `http://compliance-service:8082`
- `http://localhost:8082`
- `unknown`

---

### contract

#### Gateway Routes

- **Traefik Router**: contract-service
  - Path Prefix: `/api/v1/contracts`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/contracts`

---

### datacontract

#### Service Clients

- **DataContractCLIClient**
  - Base URL: `http://localhost:8080`
  - Methods: 4

---

### datacontract-service

#### Inbound Integrations

- **api-service**: 59 calls
  - Endpoints: unknown, http://datacontract-service:8080, http://localhost:8080, /health, http://localhost:8080/webhooks/payment
  - ... and 1 more

- **unknown**: 31 calls
  - Endpoints: unknown

#### Gateway Routes

- **Kubernetes Ingress**: datacontract-service-ingress
  - Host: `datacontract.example.com`
  - Path: `/`

#### Endpoints (6)

- `/health`
- `http://127.0.0.1:8080/webhooks/payment`
- `http://datacontract-service:8080`
- `http://localhost:8080`
- `http://localhost:8080/webhooks/payment`
- `unknown`

---

### dataset

#### Gateway Routes

- **Traefik Router**: dataset-service
  - Path Prefix: `/api/v1/datasets`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/datasets`

---

### dq

#### Service Clients

- **DQServiceClient**
  - Base URL: `http://dq-service:8083`
  - Methods: 2

#### Endpoints (2)

- `/health`
- `/run`

---

### dq-service

#### Inbound Integrations

- **api-service**: 123 calls
  - Endpoints: unknown, /.dockerenv, http://dq-service-test:8083, http://dq-service:8083, http://localhost:8083
  - ... and 2 more

- **unknown**: 82 calls
  - Endpoints: unknown, /api/v1/dq/runs/

#### Gateway Routes

- **Traefik Router**: dq-service
  - Path Prefix: `/api/v1/dq`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

- **Kubernetes Ingress**: dq-service-ingress
  - Host: `dq.example.com`
  - Path: `/`

#### Endpoints (8)

- `/.dockerenv`
- `/api/v1/dq`
- `/api/v1/dq/runs/`
- `/health`
- `http://dq-service-test:8083`
- `http://dq-service:8083`
- `http://localhost:8083`
- `unknown`

---

### event-bus-health-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: /health

#### Endpoints (1)

- `/health`

---

### event-schema-registry-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: unknown

#### Endpoints (1)

- `unknown`

---

### governance

#### Gateway Routes

- **Traefik Router**: governance-service
  - Path Prefix: `/api/v1/governance`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/governance`

---

### grafana

#### Gateway Routes

- **Kubernetes Ingress**: grafana-ingress
  - Host: `grafana.example.com`
  - Path: `/`

---

### ingestion

#### Gateway Routes

- **Traefik Router**: ingestion-service
  - Path Prefix: `/api/v1/ingestion`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/ingestion`

---

### jaeger

#### Gateway Routes

- **Kubernetes Ingress**: jaeger-ingress
  - Host: `jaeger.example.com`
  - Path: `/`

---

### lineage

#### Gateway Routes

- **Traefik Router**: lineage-service
  - Path Prefix: `/api/v1/lineage`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/lineage`

---

### normalization

#### Gateway Routes

- **Traefik Router**: normalization-service
  - Path Prefix: `/api/v1/normalization`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/normalization`

---

### observability-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: /health

#### Gateway Routes

- **Traefik Router**: observability-service
  - Path Prefix: `/api/v1/observability`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

- **Kubernetes Ingress**: observability-service-ingress
  - Host: `observability.example.com`
  - Path: `/`

#### Endpoints (2)

- `/api/v1/observability`
- `/health`

---

### prefect-integration

#### Gateway Routes

- **Kubernetes Ingress**: prefect-integration-ingress
  - Host: `prefect-integration.example.com`
  - Path: `/`

---

### prefect-server

#### Gateway Routes

- **Kubernetes Ingress**: prefect-server-ingress
  - Host: `prefect-api.example.com`
  - Path: `/`

- **Kubernetes Ingress**: prefect-server-ingress
  - Host: `prefect-ui.example.com`
  - Path: `/`

---

### prometheus

#### Gateway Routes

- **Kubernetes Ingress**: prometheus-ingress
  - Host: `prometheus.example.com`
  - Path: `/`

---

### sdk

#### Outbound Integrations

- **api-service**: 63 calls
  - Endpoints: http://localhost:8000/api/v1, unknown, /home/ph/Desktop/DataInteroperabilityHub

#### Endpoints (3)

- `/home/ph/Desktop/DataInteroperabilityHub`
- `http://localhost:8000/api/v1`
- `unknown`

---

### search-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: /health

#### Gateway Routes

- **Traefik Router**: search-service
  - Path Prefix: `/api/v1/search`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

- **Kubernetes Ingress**: search-service-ingress
  - Host: `search.example.com`
  - Path: `/`

#### Endpoints (2)

- `/api/v1/search`
- `/health`

---

### semantic-service

#### Inbound Integrations

- **api-service**: 106 calls
  - Endpoints: unknown, http://semantic-service:8081, http://localhost:8081, http://localhost:8081/health, /health

- **unknown**: 99 calls
  - Endpoints: unknown, http://localhost:3030

#### Gateway Routes

- **Traefik Router**: semantic-service
  - Path Prefix: `/api/v1/semantic`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

- **Kubernetes Ingress**: semantic-service-ingress
  - Host: `semantic.example.com`
  - Path: `/`

#### Service Clients

- **SemanticServiceClient**
  - Base URL: `http://localhost:8081`
  - Methods: 9

#### Endpoints (15)

- `/api/v1/semantic`
- `/context.jsonld`
- `/health`
- `/id/`
- `/map/asset`
- `/map/contract`
- `/map/dataset`
- `/map/odps`
- `/ontology`
- `/sparql`
- ... and 5 more endpoints

---

### unknown

#### Outbound Integrations

- **compliance-service**: 54 calls
  - Endpoints: unknown

- **dq-service**: 82 calls
  - Endpoints: unknown, /api/v1/dq/runs/

- **datacontract-service**: 31 calls
  - Endpoints: unknown

- **semantic-service**: 99 calls
  - Endpoints: unknown, http://localhost:3030

#### Endpoints (3)

- `/api/v1/dq/runs/`
- `http://localhost:3030`
- `unknown`

---

### versioning

#### Gateway Routes

- **Traefik Router**: versioning-service
  - Path Prefix: `/api/v1/versioning`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1/versioning`

---

### webhook-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: /health

#### Gateway Routes

- **Traefik Router**: webhook-service
  - Path Prefix: `/api/v1/webhooks`
  - Middlewares: auth-middleware, rate-limit-middleware, tracing-middleware

- **Kubernetes Ingress**: webhook-service-ingress
  - Host: `webhook.example.com`
  - Path: `/`

#### Endpoints (2)

- `/api/v1/webhooks`
- `/health`

---

### worker-service

#### Inbound Integrations

- **api-service**: 131 calls
  - Endpoints: redis-queue, http://datacontract-service:8080, http://localhost:8080, /health, unknown
  - ... and 2 more

#### Endpoints (7)

- `/health`
- `http://127.0.0.1:8080/webhooks/payment`
- `http://datacontract-service:8080`
- `http://localhost:8080`
- `http://localhost:8080/webhooks/payment`
- `redis-queue`
- `unknown`

---

### workflow-engine-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: /health

#### Endpoints (1)

- `/health`

---

### workflow-registry-service

#### Inbound Integrations

- **api-service**: 1 calls
  - Endpoints: /healthz

#### Endpoints (1)

- `/healthz`

---
