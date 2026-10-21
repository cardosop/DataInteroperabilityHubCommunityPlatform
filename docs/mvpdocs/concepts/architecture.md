# Architecture

Meshant is a microservices-based platform built on a Django monolith (with
bounded contexts) backed by FastAPI microservices. It is deployed via Docker
Compose (dev/staging) and Kubernetes with Helm (production).

## Service Map

| Service | Framework | Port | Responsibility |
|---------|-----------|------|---------------|
| API Service | Django | 8000 | REST/GraphQL, auth, tenants, assets, contracts, marketplace, jobs, audit |
| Worker Service | Django RQ | -- | Background jobs: DQ runs, compliance scans, contract validation, file processing |
| Semantic Service | FastAPI | 8081 | RDF mapping, SPARQL queries, URI resolution, Fuseki triple store |
| Compliance Service | FastAPI | 8082 | Compliance scanning, PII detection, risk assessment |
| DQ Service | FastAPI | 8083 | Data quality checks, Great Expectations, Soda, metrics |
| Search Service | FastAPI | 8085 | Full-text search, indexing, ranking |
| Observability Service | FastAPI | 8086 | Data observability metrics, freshness checks, lineage tracking |
| Webhook Service | FastAPI | 8087 | Webhook delivery and management |
| Workflow Engine | -- | 8088 | Workflow orchestration, state management, task execution |
| DataContract Service | FastAPI | 8080 | Contract validation, normalization, conversion, linting |

## Data Layer

| Store | Technology | Purpose |
|-------|-----------|---------|
| Primary database | PostgreSQL 16 | All persistent data (contracts, assets, users, tenants, jobs, audit) |
| Job queue & cache | Redis (4 instances) | Cache, RQ queues, pub/sub events, WebSocket channels |
| Object storage | S3 / MinIO | File uploads, exports, contract files |
| RDF store | Apache Fuseki | Semantic triples, SPARQL queries |

## Key Architectural Decisions

1. **Service independence** -- each service is independently deployable and scalable.
2. **API-first** -- all services expose REST APIs; the API service is the primary gateway.
3. **Stateless services** -- application state lives in databases, not in service memory.
4. **Tenant isolation** -- enforced at middleware, queryset, and storage levels across all services.
5. **Event-driven** -- event bus for asynchronous cross-service communication.
6. **RQ over Celery** -- chosen for simplicity, Django integration, and priority queue support.

## Related

- [Infrastructure Decisions](infrastructure-decisions.md) -- why PostgreSQL, Redis, S3, RQ
- [Tenants concept](tenants.md) -- multi-tenancy model
- [Configuration Reference](../operations/configuration-reference.md) -- service environment variables
