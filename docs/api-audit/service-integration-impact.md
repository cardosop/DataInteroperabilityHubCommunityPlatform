# Service Integration Impact Report

**Generated:** 2026-06-13T21:03:51.404101

## Summary

- **Total Services:** 21
- **Total Integrations:** 10
- **Total Service Calls:** 2880
- **Services Involved:** api-gateway, api-service, compliance-service, datacontract, datacontract-service, dq, dq-service, frontend, grafana, jaeger, observability-service, prefect-integration, prefect-server, prometheus, sdk, search-service, semantic-service, unknown, webhook-delivery, webhook-service, worker-service

## Service Integration Matrix

This matrix shows the number of service calls from each source service to each target service.


| Source → Target | api-gateway | api-service | compliance-service | datacontract | datacontract-service | dq | dq-service | frontend | grafana | jaeger | observability-service | prefect-integration | prefect-server | prometheus | sdk | search-service | semantic-service | unknown | webhook-delivery | webhook-service | worker-service |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| api-gateway | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| api-service | - | - | 185 | - | 91 | - | 216 | - | - | - | - | - | - | - | - | - | 197 | - | - | - | 21 |
| compliance-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| datacontract | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| datacontract-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| dq | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| dq-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| frontend | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| grafana | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| jaeger | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| observability-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| prefect-integration | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| prefect-server | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| prometheus | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| sdk | - | 369 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| search-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| semantic-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| unknown | - | - | 85 | - | 22 | - | 107 | - | - | - | - | - | - | - | - | - | 147 | - | - | - | - |
| webhook-delivery | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| webhook-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| worker-service | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |


## Service Integration Details

### api-gateway

#### Gateway Routes

- **Traefik Router**: api-gateway
  - Path Prefix: `/api/v1`
  - Middlewares: cors-middleware, tracing-middleware

- **Traefik Router**: api-gateway-host
  - Middlewares: cors-middleware, tracing-middleware

#### Endpoints (1)

- `/api/v1`

---

### api-service

#### Outbound Integrations

- **dq-service**: 216 calls
  - Endpoints: unknown, /health, /api/v1/dq/runs/, http://localhost:8083

- **compliance-service**: 185 calls
  - Endpoints: unknown, /scan-file-async, /health, /api/v1/compliance/runs/, http://127.0.0.1:65535
  - ... and 1 more

- **datacontract-service**: 91 calls
  - Endpoints: unknown, http://datacontract-service:8080, http://localhost:8080, http://127.0.0.1:8080/sparql, /health
  - ... and 6 more

- **semantic-service**: 197 calls
  - Endpoints: unknown, http://localhost:8081, http://semantic-service:8081, /api/v1/semantic/ontologies/{ont.id}/, http://semantic-service-test:8081/health
  - ... and 2 more

- **worker-service**: 21 calls
  - Endpoints: http://datacontract-service:8080, http://localhost:8080, http://127.0.0.1:8080/sparql, /health, http://test-odh:8080
  - ... and 3 more

#### Inbound Integrations

- **sdk**: 369 calls
  - Endpoints: unknown, https://meshant-internal.example.com/api/v1/mesh/, http://localhost:8000/api/v1/mesh/, http://localhost:8000/api/v1, /api/v1
  - ... and 15 more

#### Gateway Routes

- **Kubernetes Ingress**: api-service-ingress
  - Host: `api.example.com`
  - Path: `/`

#### Endpoints (41)

- `/api/v1`
- `/api/v1/assets/{asset.id}/contracts/`
- `/api/v1/compliance/runs/`
- `/api/v1/contracts/{contract.id}/validate/`
- `/api/v1/contracts/{invalid_contract.id}/validate/`
- `/api/v1/contracts/{self.contract.id}/validate/`
- `/api/v1/dq/runs/`
- `/api/v1/semantic/ontologies/{ont.id}/`
- `/app/hub/manage.py`
- `/health`
- ... and 31 more endpoints

---

### compliance-service

#### Inbound Integrations

- **api-service**: 185 calls
  - Endpoints: unknown, /scan-file-async, /health, /api/v1/compliance/runs/, http://127.0.0.1:65535
  - ... and 1 more

- **unknown**: 85 calls
  - Endpoints: unknown, /api/v1/compliance/runs/, http://127.0.0.1:65535

#### Gateway Routes

- **Kubernetes Ingress**: compliance-service-ingress
  - Host: `compliance.example.com`
  - Path: `/`

#### Service Clients

- **ComplianceServiceClient**
  - Base URL: `http://compliance-service:8082`
  - Methods: 4

#### Endpoints (8)

- `/api/v1/compliance/runs/`
- `/health`
- `/scan-file`
- `/scan-file-async`
- `/scan-result/`
- `http://127.0.0.1:65535`
- `http://localhost:8082`
- `unknown`

---

### datacontract

#### Service Clients

- **DataContractCLIClient**
  - Base URL: `http://localhost:8080`
  - Methods: 4

---

### datacontract-service

#### Inbound Integrations

- **api-service**: 91 calls
  - Endpoints: unknown, http://datacontract-service:8080, http://localhost:8080, http://127.0.0.1:8080/sparql, /health
  - ... and 6 more

- **unknown**: 22 calls
  - Endpoints: unknown

#### Gateway Routes

- **Kubernetes Ingress**: datacontract-service-ingress
  - Host: `datacontract.example.com`
  - Path: `/`

#### Endpoints (11)

- `/api/v1/contracts/{contract.id}/validate/`
- `/api/v1/contracts/{invalid_contract.id}/validate/`
- `/api/v1/contracts/{self.contract.id}/validate/`
- `/health`
- `http://127.0.0.1:8080/sparql`
- `http://127.0.0.1:8080/webhooks/payment`
- `http://datacontract-service:8080`
- `http://localhost:8080`
- `http://localhost:8080/webhooks/payment`
- `http://test-odh:8080`
- ... and 1 more endpoints

---

### dq

#### Service Clients

- **DQServiceClient**
  - Base URL: `http://localhost:8084`
  - Methods: 2

#### Endpoints (2)

- `/health`
- `/run`

---

### dq-service

#### Inbound Integrations

- **api-service**: 216 calls
  - Endpoints: unknown, /health, /api/v1/dq/runs/, http://localhost:8083

- **unknown**: 107 calls
  - Endpoints: unknown, /api/v1/dq/runs/

#### Endpoints (4)

- `/api/v1/dq/runs/`
- `/health`
- `http://localhost:8083`
- `unknown`

---

### frontend

#### Gateway Routes

- **Traefik Router**: frontend
  - Path Prefix: `/`
  - Middlewares: cors-middleware, tracing-middleware

#### Endpoints (1)

- `/`

---

### grafana

#### Gateway Routes

- **Kubernetes Ingress**: grafana-ingress
  - Host: `grafana.example.com`
  - Path: `/`

---

### jaeger

#### Gateway Routes

- **Kubernetes Ingress**: jaeger-ingress
  - Host: `jaeger.example.com`
  - Path: `/`

---

### observability-service

#### Gateway Routes

- **Kubernetes Ingress**: observability-service-ingress
  - Host: `observability.example.com`
  - Path: `/`

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

- **api-service**: 369 calls
  - Endpoints: unknown, https://meshant-internal.example.com/api/v1/mesh/, http://localhost:8000/api/v1/mesh/, http://localhost:8000/api/v1, /api/v1
  - ... and 15 more

#### Endpoints (20)

- `/api/v1`
- `/app/hub/manage.py`
- `/home/ph/Desktop/DataInteroperabilityHub`
- `http://invalid-host:8000/api/v1`
- `http://localhost:8000/api/v1`
- `http://localhost:8000/api/v1/`
- `http://localhost:8000/api/v1/assets/`
- `http://localhost:8000/api/v1/assets/{asset_id}/`
- `http://localhost:8000/api/v1/datasets/`
- `http://localhost:8000/api/v1/datasets/{dataset_id}/`
- ... and 10 more endpoints

---

### search-service

#### Gateway Routes

- **Kubernetes Ingress**: search-service-ingress
  - Host: `search.example.com`
  - Path: `/`

---

### semantic-service

#### Inbound Integrations

- **api-service**: 197 calls
  - Endpoints: unknown, http://localhost:8081, http://semantic-service:8081, /api/v1/semantic/ontologies/{ont.id}/, http://semantic-service-test:8081/health
  - ... and 2 more

- **unknown**: 147 calls
  - Endpoints: unknown, http://localhost:9999, /api/v1/assets/{asset.id}/contracts/

#### Gateway Routes

- **Kubernetes Ingress**: semantic-service-ingress
  - Host: `semantic.example.com`
  - Path: `/`

#### Service Clients

- **SemanticServiceClient**
  - Base URL: `http://semantic-service:8081`
  - Methods: 14

#### Endpoints (19)

- `/api/v1/assets/{asset.id}/contracts/`
- `/api/v1/semantic/ontologies/{ont.id}/`
- `/context.jsonld`
- `/health`
- `/id/`
- `/ingest`
- `/map/asset`
- `/map/contract`
- `/map/dataset`
- `/map/odps`
- ... and 9 more endpoints

---

### unknown

#### Outbound Integrations

- **compliance-service**: 85 calls
  - Endpoints: unknown, /api/v1/compliance/runs/, http://127.0.0.1:65535

- **dq-service**: 107 calls
  - Endpoints: unknown, /api/v1/dq/runs/

- **datacontract-service**: 22 calls
  - Endpoints: unknown

- **semantic-service**: 147 calls
  - Endpoints: unknown, http://localhost:9999, /api/v1/assets/{asset.id}/contracts/

#### Endpoints (6)

- `/api/v1/assets/{asset.id}/contracts/`
- `/api/v1/compliance/runs/`
- `/api/v1/dq/runs/`
- `http://127.0.0.1:65535`
- `http://localhost:9999`
- `unknown`

---

### webhook-delivery

#### Service Clients

- **WebhookDeliveryClient**
  - Base URL: `unknown`
  - Methods: 3

---

### webhook-service

#### Gateway Routes

- **Kubernetes Ingress**: webhook-service-ingress
  - Host: `webhook.example.com`
  - Path: `/`

---

### worker-service

#### Inbound Integrations

- **api-service**: 21 calls
  - Endpoints: http://datacontract-service:8080, http://localhost:8080, http://127.0.0.1:8080/sparql, /health, http://test-odh:8080
  - ... and 3 more

#### Endpoints (8)

- `/health`
- `http://127.0.0.1:8080/sparql`
- `http://127.0.0.1:8080/webhooks/payment`
- `http://datacontract-service:8080`
- `http://localhost:8080`
- `http://localhost:8080/webhooks/payment`
- `http://test-odh:8080`
- `unknown`

---
