# Services Architecture

This document describes the microservices architecture of the Data Interoperability Hub.

## Service Overview

| Service | Purpose | Communication |
|---------|---------|---------------|
| api-service | REST API gateway, request routing, authentication | HTTP REST, Redis pub/sub |
| worker-service | Background job processing, async task execution | Redis queues |
| semantic-service | RDF/semantic mapping, SPARQL query execution, ontology management | HTTP REST, Redis pub/sub |
| dq-service | Data quality checks, profiling, scorecards | HTTP REST |
| compliance-service | Compliance scanning, policy enforcement | HTTP REST |
| datacontract-service | Data contract creation, normalization, versioning | HTTP REST |
| prefect-integration-service | Scheduled ingestion/export workflow orchestration | HTTP REST, Prefect API |
| VirtualizationService | Virtual dataset management, federated queries across external sources | HTTP REST, Redis pub/sub |
| webhook-service | Outgoing webhook delivery, event subscriptions | HTTP REST, Redis pub/sub |
| search-service | Full-text search, semantic search, indexing | HTTP REST |

## Inter-Service Communication

Services communicate via:
1. **REST APIs** — synchronous request/response for CRUD operations
2. **Redis Pub/Sub** — asynchronous event-driven communication
3. **Redis Queues** — background job dispatch and processing

## Data Flow

```
Client → api-service → [semantic-service, dq-service, compliance-service, ...]
                   ↓
            redis-queue → worker-service → [external systems]
                   ↓
            redis pub/sub → [event subscribers]
```

## Business Rules Framework

The business rules framework provides a structured approach to validating business constraints across the platform. Each domain (contracts, assets, marketplace, governance, semantic) implements its own rule validators that extend common base classes. Rule chains are registered in `hub/apps/core/business_rules/chain_registry.py` and executed via `execute_chain()`.

Key components:
- **BusinessRules base class** — `hub/apps.core.business_rules.base`
- **Chain registry** — `hub/apps/core/business_rules/chain_registry.py`
- **ValidationResult** — standardized output type with domain-specific variants

## Deployment

Services are containerized and orchestrated via Docker Compose for development and Kubernetes for production.
