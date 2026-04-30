# Architecture

> Consolidated architecture reference for the Meshant platform.
>
> **Source**: Merged from 14 architecture docs during Phase 120E documentation consolidation.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Service Boundaries](#2-service-boundaries)
3. [Inter-Service Communication](#3-inter-service-communication)
4. [Event Bus & Event Types](#4-event-bus--event-types)
5. [Workflow Orchestration](#5-workflow-orchestration)
6. [Job Queue](#6-job-queue)
7. [Caching Strategy](#7-caching-strategy)
8. [Architecture Decision Records](#8-architecture-decision-records)

---


## 1. System Overview


**Last Updated**: 2026-03-22
**Version**: 1.1.0

---

## Overview

The Data Interoperability Hub is a microservices-based platform for managing data contracts, assets, quality, compliance, and marketplace operations. The system is built using Django (monolith with service boundaries) and FastAPI microservices, deployed using Docker Compose for development/staging and Kubernetes for production.

## Architecture Principles

1. **Service Independence**: Services can be developed, deployed, and scaled independently
2. **API-First**: All services expose well-defined REST APIs
3. **Stateless Services**: Services are stateless where possible, with state stored in databases
4. **Tenant Isolation**: All services enforce tenant isolation
5. **Observability**: All services expose metrics, logs, and traces
6. **Event-Driven**: Event bus for asynchronous communication
7. **Workflow Orchestration**: Workflow engine for complex business processes

## High-Level Architecture

**Request paths**: By default, the frontend talks to **api-service (Django)** directly. Optionally, traffic can go through **Traefik (reverse proxy) → API Gateway (FastAPI) → api-service**. See [Request paths](#request-paths) below and `docs/API_GATEWAY_TRAEFIK.md`.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Traefik (reverse proxy) → API Gateway (FastAPI, optional) → API Service │
│  Default path: frontend → api-service (Django) direct                    │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  API Service │ │ GraphQL API  │ │ WebSocket    │
│   (Django)   │ │  (Strawberry)│ │   (Channels) │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
       ├─────────────────────────────────────────┐
       │                                         │
       ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│  Django Apps     │                    │  Microservices   │
│  (Monolith)      │                    │  (FastAPI)       │
│                  │                    │                  │
│  - Contracts     │                    │  - Semantic      │
│  - Assets        │                    │  - DQ            │
│  - Datasets      │                    │  - Compliance    │
│  - Marketplace   │                    │  - DataContract  │
│  - Governance    │                    │  - Search        │
│  - DQ            │                    │  - Observability │
│  - Compliance    │                    │  - Webhook       │
│  - Jobs          │                    │                  │
│  - Orchestration │                    │                  │
└──────┬───────────┘                    └────────┬─────────┘
       │                                         │
       └──────────────────┬──────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │     Redis     │  │    MinIO      │
│  (Primary DB)│  │ (Queue/Cache) │  │ (S3 Storage)  │
└──────────────┘  └──────────────┘  └──────────────┘
                          │
                          ▼
                  ┌──────────────┐
                  │    Fuseki    │
                  │ (RDF Store)  │
                  └──────────────┘
```

### Request paths

| Path | Traffic flow | When to use |
|------|--------------|-------------|
| **Default** | Frontend → api-service (Django) directly | Default; no Traefik or API Gateway in path. Session/cookie or JWT at api-service. |
| **Optional (via Traefik)** | Browser → Traefik → (Frontend or API Gateway → api-service) | Single entrypoint, TLS, API key at gateway. See `docs/API_GATEWAY_TRAEFIK.md`. |

## Core Components

### Application Services

#### API Service (`api-service`)
- **Technology**: Django 6.0+, Django REST Framework
- **Port**: 8000
- **Responsibilities**:
  - REST API endpoints for all platform functionality
  - GraphQL API endpoint
  - Authentication and authorization
  - Tenant management
  - User management
  - Asset management
  - Contract management
  - Marketplace operations
  - Job orchestration
  - Audit logging

#### Worker Service (`worker-service`)
- **Technology**: Django RQ
- **Port**: 8080 (health check)
- **Responsibilities**:
  - Background job processing
  - Data quality runs
  - Compliance scans
  - Contract validation
  - File processing

#### Workflow Engine Service (`workflow-engine-service`)
- **Technology**: Python
- **Port**: 8088 (health check)
- **Responsibilities**:
  - Workflow orchestration
  - Workflow state management
  - Task execution
  - Workflow versioning

### Microservices

#### Semantic Service (`semantic-service`)
- **Technology**: FastAPI
- **Port**: 8081
- **Responsibilities**:
  - RDF mapping
  - SPARQL queries
  - Semantic URI resolution
  - Triple store management

#### DQ Service (`dq-service`)
- **Technology**: FastAPI
- **Port**: 8083
- **Responsibilities**:
  - Data quality checks
  - Great Expectations integration
  - Soda integration
  - Quality metrics

#### Compliance Service (`compliance-service`)
- **Technology**: FastAPI
- **Port**: 8082
- **Responsibilities**:
  - Compliance scanning
  - PII detection
  - Risk assessment
  - Compliance reports

#### DataContract Service (`datacontract-service`)
- **Technology**: FastAPI
- **Port**: 8080
- **Responsibilities**:
  - Contract validation
  - Contract normalization
  - Contract conversion
  - Contract linting

#### Search Service (`search-service`)
- **Technology**: FastAPI
- **Port**: 8085
- **Responsibilities**:
  - Full-text search
  - Search indexing
  - Search result ranking

#### Observability Service (`observability-service`)
- **Technology**: FastAPI
- **Port**: 8086
- **Responsibilities**:
  - Data observability metrics
  - Freshness checks
  - Lineage tracking

#### Webhook Service (`webhook-service`)
- **Technology**: FastAPI
- **Port**: 8087
- **Responsibilities**:
  - Webhook delivery
  - Webhook retry logic
  - Webhook event management

### Infrastructure Services

#### PostgreSQL
- **Version**: 16-alpine
- **Port**: 5432
- **Purpose**: Primary relational database
- **Databases**:
  - `hub` - Main application database
  - `prefect` - Prefect workflow database

#### Redis
- **Version**: 7-alpine
- **Port**: 6379
- **Purpose**:
  - Job queue (django-rq)
  - Event bus (pub/sub)
  - Caching

#### MinIO
- **Version**: latest
- **Ports**: 9000 (API), 9001 (Console)
- **Purpose**: S3-compatible object storage
- **Buckets**: Files, datasets, contracts

#### Apache Jena Fuseki
- **Version**: latest
- **Port**: 3030
- **Purpose**: RDF triple store for semantic layer

### Monitoring & Observability

#### Prometheus
- **Port**: 9090
- **Purpose**: Metrics collection

#### Grafana
- **Port**: 3000
- **Purpose**: Metrics visualization and dashboards

#### Jaeger
- **Ports**: 16686 (UI), 14268 (HTTP), 6831 (UDP)
- **Purpose**: Distributed tracing

#### Alertmanager
- **Port**: 9093
- **Purpose**: Alert management

### Orchestration

#### Prefect Server
- **Ports**: 4200 (API), 4201 (UI)
- **Purpose**: Workflow orchestration platform

#### Prefect Workers
- **Purpose**: Execute Prefect workflows

#### Prefect Integration Service
- **Port**: 8084
- **Purpose**: Integrate Prefect with the platform

### Infrastructure Services

#### PgBouncer (`pgbouncer`)
- **Purpose**: Connection pooling for PostgreSQL
- **Mode**: Transaction-mode pooling (releases server connection after each transaction)
- **Config**: `pool_mode=transaction`, `max_client_conn=200`, `default_pool_size=20`
- **Why**: Prevents connection exhaustion from Django's per-request model + RQ workers

#### AWS Secrets Manager

<!-- Phase 211: replaced HashiCorp Vault with AWS Secrets Manager -->
- **Purpose**: Secrets management, field-level encryption
- **Auth methods**: IRSA (in-cluster pods), GitHub OIDC→AWS STS (CI/CD)
- **Secret storage**: All production secrets stored as JSON blobs under `hub/<env>/` prefix
- **Field-level encryption**: AWS KMS key for encrypt/decrypt operations (replaces Vault Transit)
- **Integration**: ExternalSecrets Operator syncs AWS Secrets Manager entries to Kubernetes Secrets

#### OpenTelemetry Collector (`otel-collector`)
- **Purpose**: Telemetry pipeline (traces, metrics, logs)
- **Sampling**: Tail-based sampling (decision after full trace collected)
- **Exporters**: Grafana Tempo (traces/S3 backend), Loki (logs/S3 backend), Prometheus (metrics)

#### ODH Integration Services
- **Model Registry** (`odh-model-registry`, port 8095): ML model metadata, version tracking
- **Training Operator** (`odh-training-operator`, port 8096): Training job submission, monitoring, completion
- **Inference Scheduler** (`odh-inference-scheduler`, port 8097): Model deployment, inference request routing

### Worker Architecture

| Pool | Concurrency | Purpose |
|------|-------------|---------|
| `worker-light` | 16 | Short jobs: cache invalidation, notifications, audit events, search indexing |
| `worker-heavy` | 4 | Long jobs: DQ runs, compliance scans, ODPS normalization, ML training, file processing |

### Kubernetes Resources (Helm Chart)

23+ resources deployed via Helm chart:
- **Deployments**: api (3 replicas), worker-light, worker-heavy, frontend, compliance, dq, datacontract
- **Services**: ClusterIP for each deployment
- **HPA**: api (3-10 replicas, CPU 70%), worker (2-8, queue depth)
- **PDB**: api (minAvailable: 2), worker (minAvailable: 1)
- **NetworkPolicies**: default-deny ingress/egress per namespace, explicit allow rules (15+)
- **ServiceAccount**: workload identity for cloud provider integration
- **ExternalSecrets**: AWS Secrets Manager → Kubernetes Secret sync
- **Cosign**: Image signature verification via admission webhook
- **Pod Security Standards**: restricted profile enforced

### Security Infrastructure

- **CSP headers**: strict Content-Security-Policy on all responses
- **CORS**: allowlist-based, no wildcard in production
- **TLS**: internal service-to-service TLS via cert-manager
- **Source maps**: disabled in production builds (`VITE_SOURCEMAP=false`)
- **Production guards**: `DEBUG=False`, `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`

### Resilience Patterns

- **StripeCircuitBreaker**: 5 failures in 60s → circuit opens for 30s, prevents cascading billing failures (B6)
- **Classification propagation**: highest classification flows dataset→model→asset (G5)
- **Compensation handler registry**: script-name → handler function mapping for Saga rollback (ML-3)
- **Billing fail-closed**: 503 on DB outage for mutations, read operations continue (B1)

## Data Flow

### Contract Creation Flow

```
User → API Service → Contract Service
                      ↓
                  Workflow Engine
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    Validation   Normalization   Semantic
    (DataContract)  (ODCS→Hub)    Mapping
        ↓             ↓             ↓
                  Event Bus
                      ↓
              Notifications
```

### Structural Floor Invariant (Phase 227 Wave 1)

Every contract that lands in the database carries **resolvable
structure**: at least one `models[*].fields[*]` entry OR a top-level
`schema.fields[*]` entry. This invariant — the *structural floor* —
is enforced at five layers, intentionally redundant so a single
bypass cannot land a structureless row:

```
┌────────────────────────────────────────────────────────────┐
│ 1. ContractService.create_contract / update_contract       │
│    └─ enforce_structural_floor() → ValidationError 400     │
│       (code = STRUCTURELESS_CONTRACT)                      │
├────────────────────────────────────────────────────────────┤
│ 2. NormalizationService.normalize_contract                 │
│    └─ Same floor check, defensive double-gate              │
├────────────────────────────────────────────────────────────┤
│ 3. ODPSService.create_odps / link_odps_to_odcs /           │
│    normalize_odps                                          │
│    └─ Floor check after ODPSNormalizer.normalize()         │
│       (audit-discovered alternate write paths)             │
├────────────────────────────────────────────────────────────┤
│ 4. Asset.can_activate / Asset.clean                        │
│    └─ Floor check on currently-active contract;            │
│       activation rejected with subcode'd blocker           │
├────────────────────────────────────────────────────────────┤
│ 5. MarketplaceService._enforce_publish_structural_floor    │
│    └─ Both publish_listing AND update_listing(PUBLISHED)   │
│       paths route through the shared helper (HTTP 422)     │
└────────────────────────────────────────────────────────────┘
```

**Subcode taxonomy** (carried in `error.details.subcode`):

- `STRUCTURELESS_ODPS_NO_PORTS` — ODPS contract has no resolvable
  `outputPorts[*]` schemas.
- `STRUCTURELESS_ODCS_NO_SCHEMA` — ODCS contract has no
  `schema.fields[]` and no `models[*].fields[]`.
- `STRUCTURELESS_CYCLIC_PORTS` — ODPS port resolution short-circuited
  on a cycle (A → B → A).
- `STRUCTURELESS_GENERIC` — non-ODPS/ODCS spec_type or unrecognised
  shape; ops investigation needed.

Each error payload includes `models_count`, `schema_fields_count`,
`spec_type`, `spec_version`, a per-cause `hint`, and a
`remediation_url` deep-linking to the Schema editor for the offending
contract. The frontend toast switches on `code` programmatically
rather than parsing `message` strings.

**Always-on**: per the 2026-04-30 ungate directive, the floor has no
feature-flag gate, no per-tenant override, and no deprecation period.
Customers who upload structureless contracts must use the Schema
editor to add fields before retrying. See
[`docs/CONTRACTS.md`](CONTRACTS.md) for the canonical shapes per
spec version and the
[ops runbook](runbooks/structureless-contracts.md) for tenant
rejection triage.

### ODCS Recursive Nested-Properties Walker (Phase 227 L2)

The ODCS normalizer recursively descends into `properties[]` (or
`fields[]` keyword for ≤ v3.0.x) of object-typed fields and `items`
of array-typed fields, producing a tree of `HubContractField` entries
up to `CONTRACTS_MAX_NESTING_DEPTH` levels (default 20). The bound is
enforced **before** Python's recursion limit is reached. Beyond the
bound, normalization fails with
`ValidationError(code="SCHEMA_TOO_DEEP")`. The walker is shared
across every ODCS version normalizer (v2.2.2, v3.0.0,
v3.0.0-preview, v3.0.1, v3.0.2, v3.1.0).

### ETag / If-Match Optimistic Concurrency (Phase 227 L4.3)

`PATCH /api/v1/contracts/{id}/` supports RFC 7232 weak ETag
validators. GET responses include an `ETag` header derived from
`Contract.updated_at + version + id`; PATCH validates `If-Match` and
returns HTTP 412 `PRECONDITION_FAILED` on mismatch. The 412 response
body and `ETag` header carry the server's current value so clients
can reconcile in one round-trip. The Schema editor surfaces a
conflict dialog ("Refresh", "Discard my changes", "Open in new tab")
on 412 — no silent overwrites.

### ODPS Creation Flow (Product-First)

```
User → API Service → ODPSService
                      ↓
              ProductCreationWorkflow
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    Parse ODPS   Resolve Refs   Extract ODCS
        ↓             ↓             ↓
    Validate ODCS → Normalize ODCS → Normalize ODPS
        ↓             ↓             ↓
    Create ODCS Contract → Create ODPS Contract
        ↓             ↓             ↓
    Link Contracts (ODPS ↔ ODCS)
        ↓             ↓             ↓
    Index for Search → Semantic Mapping (RDF)
        ↓             ↓             ↓
                  Event Bus
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    Notifications  Audit Log   Webhooks
```

### Data Quality Flow

```
User → API Service → DQ Service
                      ↓
                  Worker Service
                      ↓
                  DQ Execution
                      ↓
                  Results Storage
                      ↓
                  Event Bus
                      ↓
              Notifications
```

## Business Logic Integration

### Service Layer Architecture

The platform uses a service layer pattern to coordinate business logic across features:

- **AIService**: Coordinates ML operations with workflows
- **SocialService**: Coordinates social features with asset operations
- **MarketplaceService**: Coordinates marketplace operations with quality
- **DataMeshService**: Coordinates domain operations with asset ownership
- **ODPSService**: Coordinates ODPS contract operations with normalization, linking, and workflows

All service classes extend `BaseService` and provide:
- Business logic coordination
- Event publishing
- Transaction management
- Error handling
- Audit logging

### Workflow Integration

All multi-step operations are orchestrated through the workflow engine:

- **AssetCreationWorkflow**: Extended with AI schema matching and auto-classification
- **MarketplacePublishingWorkflow**: Orchestrates marketplace publishing with validation
- **SocialFeatureWorkflow**: Orchestrates review moderation and asset updates
- **DataMeshWorkflow**: Orchestrates domain operations
- **ProductCreationWorkflow**: Orchestrates ODPS product creation with ODCS extraction, normalization, and linking

Workflows provide:
- State management
- Retry logic
- Compensation (Saga pattern)
- Progress tracking
- Event publishing

### Event-Driven Coordination

Features coordinate asynchronously through the event bus:

- **AI/ML Events**: `schema_matching_completed`, `classification_completed`, `recommendation_updated`
- **Social Events**: `review_created`, `rating_updated`, `comment_created`
- **Marketplace Events**: `purchase_completed`, `pricing_changed`, `listing_updated`
- **Data Mesh Events**: `domain_created`, `policy_applied`, `topology_updated`
- **ODPS Events**: `odps.created`, `odps.normalized`, `odps.linked`, `odps.workflow.completed`, `odps.ref.resolved`

Event handlers subscribe to events and trigger workflows or update state.

### Business Rules Framework

Centralized business rules framework (`hub/apps/core/business_rules/`) enforces:

- **AIBusinessRules**: ML result validation, schema alignment
- **MarketplaceBusinessRules**: Publishing validation, pricing validation
- **SocialBusinessRules**: Review moderation, rating validation
- **DataMeshBusinessRules**: Domain ownership, policy compliance
- **ODPSBusinessRules**: ODPS document structure validation, version validation, linking validation

### Data Consistency

Event-driven data consistency maintains consistency across features:

- **AI → Asset**: Recommendations updated when assets change
- **Social → Asset**: Ratings reflected in quality scores
- **Data Mesh → Asset**: Topology updated when assets move domains

Consistency is maintained through:
- Event handlers
- Scheduled consistency checks
- Consistency validation rules
- Consistency metrics and monitoring

## Service Communication

### Synchronous Communication
- **REST APIs**: HTTP/HTTPS for synchronous requests
- **GraphQL**: GraphQL endpoint for flexible queries

### Asynchronous Communication
- **Event Bus**: Redis pub/sub for events
- **Job Queue**: Redis (django-rq) for background jobs
- **Webhooks**: HTTP callbacks for external integrations

## Security

- **Authentication**: JWT tokens, API keys
- **Authorization**: Role-based access control (RBAC), Attribute-based access control (ABAC)
- **Tenant Isolation**: Database-level and application-level isolation
- **Encryption**: TLS for transport, encryption at rest for sensitive data
- **Audit Logging**: Comprehensive audit trail for all operations

## Scalability

- **Horizontal Scaling**: Services can be scaled independently
- **Database**: Read replicas, connection pooling
- **Caching**: Redis for frequently accessed data
- **Load Balancing**: **Traefik** is the reverse proxy (TLS, routing). **API Gateway** (FastAPI, optional) is the app-level gateway (API key auth, rate limiting, request routing to api-service). When the optional path is used, Traefik fronts the API Gateway; api-service can also be reached directly (default path).
- **Rate limiting**: Two layers — (1) **Traefik → API Gateway**: rate limiting by the API Gateway (tier, per-tenant/per-API-key). (2) **api-service direct**: rate limiting by Django `hub.apps.rate_limiting.middleware`. Limits and response headers may differ per path; see `docs/API_GATEWAY_TRAEFIK.md` § Rate limiting.

## Deployment

- **Development**: Docker Compose (`docker-compose.dev.yml`)
- **Staging**: Docker Compose (`docker-compose.staging.yml`)
- **Production**: Kubernetes (see `KUBERNETES_DEPLOYMENT.md`)

## ODPS Integration

### Overview

The Data Interoperability Hub provides comprehensive support for ODPS (Open Data Product Standard), a marketplace-focused specification that complements ODCS (Open Data Contract Standard) by adding product information, pricing plans, access methods, and payment gateways.

### ODPS Architecture Components

#### ODPS Normalizer

The ODPS normalizer (`hub/apps/contracts/normalization/odps_normalizer.py`) converts ODPS documents to HubContract format:

- **Version Detection**: Automatically detects ODPS version (4.1, 4.0, 3.x, 2.x)
- **Version-Specific Normalizers**: Separate normalizers for each ODPS version
- **Normalization**: Converts ODPS product structure to HubContract marketplace fields
- **Error Handling**: Comprehensive error tracking with field-level granularity
- **Graceful Degradation**: Handles missing optional fields without failing

**Component Diagram**:
```
ODPS Document (JSON/YAML)
        ↓
ODPSNormalizer (Base)
        ↓
┌───────┼───────┐
↓       ↓       ↓
ODPSNormalizerV4_1  ODPSNormalizerV4_0  ODPSNormalizerV3_X
        ↓       ↓       ↓
    Version-Specific Normalization
        ↓       ↓       ↓
    HubContract (Normalized)
```

#### ProductCreationWorkflow

The ProductCreationWorkflow (`hub/apps/orchestration/workflows/product_creation.py`) orchestrates the complete ODPS product creation process:

**Workflow Steps**:
1. **parse_odps**: Parse ODPS document, validate schema, detect version
2. **resolve_refs**: Resolve `$ref` references (internal, local, external)
3. **extract_contract**: Extract ODCS from `product.contract` (required)
4. **validate_odcs**: Validate extracted ODCS contract
5. **normalize_odcs**: Normalize ODCS → HubContract (technical)
6. **normalize_odps**: Normalize ODPS → HubContract (marketplace)
7. **create_odcs_contract**: Create ODCS contract record
8. **create_odps_contract**: Create ODPS contract record
9. **link_contracts**: Establish bidirectional link (ODPS ↔ ODCS)
10. **index_for_search**: Index for search (ODPS product + ODCS technical)
11. **semantic_mapping**: Map ODPS to RDF (async job)

**Compensation Logic**: Each step has compensation handlers for rollback on failure.

#### ODPSService

The ODPSService (`hub/apps/contracts/services.py`) provides business logic for ODPS operations:

- **create_odps()**: Create ODPS contract with normalization and validation
- **link_odps_to_odcs()**: Link ODPS contract to existing ODCS contract
- **export_odps()**: Export HubContract to ODPS format
- **generate_odps_from_hubcontract()**: Generate ODPS document from HubContract

**Service Integration**:
- Extends `BaseService` for consistent error handling and metrics
- Implements `ODPSEventPublisher` for event-driven coordination
- Uses `ProductCreationWorkflow` for multi-step operations
- Integrates with `ODPSBusinessRules` for validation

### ODPS Event-Driven Architecture

ODPS operations publish events through the event bus for asynchronous coordination:

**Event Types**:
- **Lifecycle Events**: `odps.created`, `odps.updated`, `odps.deleted`
- **Processing Events**: `odps.normalized`, `odps.ref.resolved`, `odps.ref.failed`
- **Linking Events**: `odps.linked`, `odps.unlinked`
- **Export Events**: `odps.export.started`, `odps.export.completed`, `odps.export.failed`
- **Workflow Events**: `odps.workflow.started`, `odps.workflow.completed`, `odps.workflow.failed`
- **Progress Events**: `odps.creation.progress`, `odps.normalization.progress`, `odps.ref.progress`

**Event Subscribers**:
- **SearchService**: Indexes ODPS contracts for search
- **NotificationService**: Sends creation and completion notifications
- **AuditService**: Logs ODPS operations for compliance
- **WebhookService**: Delivers webhooks for ODPS events
- **SemanticService**: Triggers RDF mapping for ODPS contracts

**Event Flow**:
```
ODPSService → ODPSEventPublisher → Event Bus (Redis Pub/Sub + PostgreSQL)
        ↓
┌───────┼───────┬───────────┬───────────┐
↓       ↓       ↓           ↓           ↓
Search  Notify  Audit    Webhook   Semantic
Service Service Service  Service   Service
```

### ODPS Data Flow Diagrams

#### Product-First Flow (Automatic ODCS Extraction)

```
User Request (ODPS Document)
        ↓
API Endpoint: POST /api/v1/contracts/products/
        ↓
ODPSService.create_odps()
        ↓
ProductCreationWorkflow.execute()
        ↓
┌───────────────────────────────────────┐
│ 1. Parse ODPS                         │
│    - Validate schema                  │
│    - Detect version                   │
│    - Parse JSON/YAML                  │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Resolve $ref References            │
│    - Internal references              │
│    - Local file references            │
│    - External HTTP references         │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Extract ODCS from product.contract │
│    - Extract spec field               │
│    - Validate ODCS structure          │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Validate ODCS Contract             │
│    - DataContract Service             │
│    - Schema validation                 │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 5. Normalize ODCS → HubContract       │
│    - ODCSNormalizer                   │
│    - Technical fields                 │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 6. Normalize ODPS → HubContract       │
│    - ODPSNormalizer                   │
│    - Marketplace fields                │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 7. Create ODCS Contract Record        │
│    - Database transaction             │
│    - Status: ACTIVE                   │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 8. Create ODPS Contract Record        │
│    - Database transaction             │
│    - Status: ACTIVE                    │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 9. Link Contracts Bidirectionally     │
│    - ODPS.linked_odcs_id = ODCS.id     │
│    - ODCS.linked_odps_id = ODPS.id    │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 10. Index for Search                  │
│     - SearchIndexer                   │
│     - Full-text search                │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 11. Semantic Mapping (Async)          │
│     - SemanticService                  │
│     - RDF/JSON-LD generation          │
└───────────────┬───────────────────────┘
                ↓
        Event Bus (Publish Events)
                ↓
        ┌───────┼───────┐
        ↓       ↓       ↓
    Notify  Audit  Webhook
```

#### Link Flow (Link ODPS to Existing ODCS)

```
User Request (ODPS Document + ODCS Contract ID)
        ↓
API Endpoint: POST /api/v1/contracts/products/
        ↓
ODPSService.create_odps(link_odcs_id=odcs_id)
        ↓
┌───────────────────────────────────────┐
│ 1. Parse ODPS                          │
│ 2. Resolve $ref References             │
│ 3. Normalize ODPS → HubContract        │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Validate ODCS Contract Exists      │
│    - Check contract_id                │
│    - Verify tenant access             │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 5. Create ODPS Contract Record        │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 6. Link Contracts Bidirectionally     │
│    - ODPS.linked_odcs_id = ODCS.id    │
│    - ODCS.linked_odps_id = ODPS.id    │
└───────────────┬───────────────────────┘
                ↓
        Event Bus (Publish odps.linked)
```

### ODPS Component Integration

**Component Diagram**:
```
┌─────────────────────────────────────────────────────────┐
│                    API Service (Django)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │         ODPS Views (REST + GraphQL)              │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│                  ODPSService                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - create_odps()                                  │  │
│  │  - link_odps_to_odcs()                           │  │
│  │  - export_odps()                                 │  │
│  │  - generate_odps_from_hubcontract()              │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓               ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ProductCreation│ │ODPSNormalizer│ │ODPSBusiness  │
│   Workflow    │ │              │ │    Rules     │
└───────┬───────┘ └──────┬───────┘ └──────┬───────┘
        ↓                ↓                ↓
┌─────────────────────────────────────────────────────────┐
│              Workflow Engine                             │
│  - State management                                      │
│  - Compensation logic                                    │
│  - Retry logic                                           │
└──────────────────┬───────────────────────────────────────┘
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│DataContract│ │Semantic │ │  Search  │
│  Service   │ │ Service │ │ Service  │
└───────────┘ └──────────┘ └──────────┘
        ↓          ↓          ↓
┌─────────────────────────────────────────────────────────┐
│                  Event Bus                              │
│  - Redis Pub/Sub (real-time)                            │
│  - PostgreSQL (persistence)                              │
└──────────────────┬───────────────────────────────────────┘
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│Notification│ │  Audit  │ │ Webhook  │
│  Service   │ │ Service │ │ Service  │
└───────────┘ └──────────┘ └──────────┘
```

## Marketplace Integration Framework

### Overview

The Marketplace Integration Framework enables bidirectional synchronization between the Data Interoperability Hub and external data marketplaces (CKAN, Snowflake Data Marketplace, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks, etc.).

### Marketplace Integration Architecture Components

#### MarketplaceIntegrationService

The MarketplaceIntegrationService (`hub/apps/integrations/services.py`) provides business logic for marketplace integration:

- **create_connection()**: Create marketplace connection with configuration
- **test_connection()**: Test marketplace connection and credentials
- **sync_assets_to_marketplace()**: PUSH sync (Hub → Marketplace)
- **sync_assets_from_marketplace()**: PULL sync (Marketplace → Hub)
- **create_sync_job()**: Create scheduled sync job
- **get_sync_status()**: Get sync job status and progress

**Service Integration**:
- Extends `BaseService` for consistent error handling and metrics
- Implements `IntegrationEventPublisher` and `MarketplaceEventPublisher` for events
- Uses `MarketplaceConnectorFactory` for connector instantiation
- Integrates with `MarketplaceSyncWorkflow` for orchestration

#### Marketplace Connector Architecture

The connector system uses a factory pattern to instantiate marketplace-specific connectors:

**Connector Factory** (`hub/apps/integrations/factory.py`):
- **MarketplaceConnectorFactory**: Creates connectors based on marketplace type
- **Supported Types**: CKAN, Snowflake, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks, etc.
- **Connector Interface**: Standardized interface for all connectors
- **Connection Testing**: Validates credentials and connectivity

**Connector Components**:
```
MarketplaceConnectorFactory
        ↓
┌───────┼───────┬───────────┬───────────┐
↓       ↓       ↓           ↓           ↓
CKAN   Snowflake AWS Data  Azure Data GCP
Connector Connector Exchange Share    Marketplace
```

#### Marketplace Sync Job Architecture

Sync jobs are orchestrated through the workflow engine:

**MarketplaceSyncWorkflow** (`hub/apps/orchestration/workflows/marketplace_sync.py`):
- **PUSH Sync Steps**: Validate assets → Transform to marketplace format → Publish to marketplace → Create mappings
- **PULL Sync Steps**: Discover marketplace listings → Transform to Hub format → Create assets → Create mappings
- **Progress Tracking**: Real-time progress updates via events
- **Error Handling**: Comprehensive error handling with retry logic

#### Marketplace Mapping Architecture

Asset mappings track relationships between Hub assets and marketplace listings:

**Mapping Model** (`hub/apps/integrations/models.py`):
- **MarketplaceMapping**: Links Hub asset to marketplace listing
- **Sync Direction**: PUSH, PULL, or BIDIRECTIONAL
- **Sync Status**: PENDING, IN_PROGRESS, COMPLETED, FAILED
- **Metadata**: Stores marketplace-specific metadata

### Marketplace Integration Data Flow Diagrams

#### PUSH Sync Flow (Hub → Marketplace)

```
User Request (Asset IDs + Marketplace Connection ID)
        ↓
API Endpoint: POST /api/v1/integrations/marketplace/sync/push
        ↓
MarketplaceIntegrationService.sync_assets_to_marketplace()
        ↓
MarketplaceSyncWorkflow.execute()
        ↓
┌───────────────────────────────────────┐
│ 1. Validate Assets                    │
│    - Check asset status (ACTIVE)      │
│    - Verify contract validity         │
│    - Check tenant permissions         │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Get Marketplace Connector          │
│    - MarketplaceConnectorFactory      │
│    - Load connection configuration     │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Transform Assets to Marketplace    │
│    - Convert HubContract to ODPS     │
│    - Map fields to marketplace format│
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Publish to Marketplace             │
│    - Connector.publish_listing()     │
│    - Handle marketplace API calls     │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 5. Create Mappings                    │
│    - MarketplaceMapping records       │
│    - Link Hub asset to listing        │
└───────────────┬───────────────────────┘
                ↓
        Event Bus (Publish marketplace.sync.completed)
                ↓
        ┌───────┼───────┐
        ↓       ↓       ↓
    Notify  Audit  Webhook
```

#### PULL Sync Flow (Marketplace → Hub)

```
User Request (Marketplace Connection ID + Filters)
        ↓
API Endpoint: POST /api/v1/integrations/marketplace/sync/pull
        ↓
MarketplaceIntegrationService.sync_assets_from_marketplace()
        ↓
MarketplaceSyncWorkflow.execute()
        ↓
┌───────────────────────────────────────┐
│ 1. Get Marketplace Connector          │
│    - MarketplaceConnectorFactory       │
│    - Load connection configuration     │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Discover Marketplace Listings      │
│    - Connector.discover_listings()   │
│    - Apply filters                    │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Transform Listings to Hub Format   │
│    - Convert marketplace format       │
│    - Create HubContract structure     │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Create Assets                      │
│    - AssetCreationWorkflow            │
│    - Create contracts                 │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 5. Create Mappings                    │
│    - MarketplaceMapping records       │
│    - Link Hub asset to listing        │
└───────────────┬───────────────────────┘
                ↓
        Event Bus (Publish marketplace.sync.completed)
```

### Marketplace Integration Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    API Service (Django)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │    Marketplace Integration Views (REST + GraphQL) │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│            MarketplaceIntegrationService                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - create_connection()                          │  │
│  │  - sync_assets_to_marketplace()                 │  │
│  │  - sync_assets_from_marketplace()               │  │
│  │  - create_sync_job()                            │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓               ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│MarketplaceSync│ │Marketplace   │ │Marketplace   │
│   Workflow    │ │Connector     │ │Business      │
│               │ │Factory       │ │Rules         │
└───────┬───────┘ └──────┬───────┘ └──────┬───────┘
        ↓                ↓                ↓
┌─────────────────────────────────────────────────────────┐
│              Workflow Engine                             │
│  - State management                                      │
│  - Progress tracking                                     │
│  - Retry logic                                           │
└──────────────────┬───────────────────────────────────────┘
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│  Asset   │ │Contract  │ │  Search  │
│ Service  │ │ Service  │ │ Service  │
└──────────┘ └──────────┘ └──────────┘
        ↓          ↓          ↓
┌─────────────────────────────────────────────────────────┐
│                  Event Bus                               │
│  - Redis Pub/Sub (real-time)                            │
│  - PostgreSQL (persistence)                              │
└──────────────────┬───────────────────────────────────────┘
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│Notification│ │  Audit  │ │ Webhook  │
│  Service   │ │ Service │ │ Service  │
└───────────┘ └──────────┘ └──────────┘
```

## BaaS Platform

### Overview

The BaaS (Backend as a Service) Platform provides API key management, usage tracking, and developer portal access for building applications on top of the Data Interoperability Hub. The platform enables tier-based access control, comprehensive usage analytics, and developer resources.

### BaaS Platform Architecture Components

#### API Gateway

The API Gateway (`services/api-gateway/`) provides centralized API management:

- **Rate Limiting**: Tier-based rate limiting (FREE, PRO, ENTERPRISE)
- **Authentication**: API key validation and JWT token validation
- **Request Routing**: Routes requests to appropriate services
- **Usage Tracking**: Tracks all API requests for analytics
- **Security**: Request validation, path traversal prevention, security logging

**Component Diagram**:
```
API Request
    ↓
API Gateway (FastAPI; optional; Traefik is reverse proxy)
    ↓
┌───────────────────────────────────────┐
│ 1. Authentication                     │
│    - Validate API key                  │
│    - Validate JWT token               │
│    - Check tenant access              │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Rate Limiting                      │
│    - Check tier limits                 │
│    - Enforce quotas                   │
│    - Track usage                      │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Request Routing                    │
│    - Route to service                  │
│    - Load balancing                   │
└───────────────┬───────────────────────┘
                ↓
        Backend Service
```

#### Usage Tracking Service

The UsageTrackingService (`hub/apps/baas/services.py`) provides comprehensive API usage tracking:

- **Request Tracking**: Tracks all API requests with metadata (endpoint, method, status, response time)
- **Statistics**: Aggregates usage statistics by API key, endpoint, tenant, and time range
- **Quota Management**: Checks and enforces tier-based quotas
- **Analytics**: Provides usage analytics by endpoint, tenant, and API key

**Service Integration**:
- Extends `BaseService` for consistent error handling and metrics
- Implements `BaaSEventPublisher` for event-driven coordination
- Integrates with `BaaSBusinessRules` for validation

#### Developer Portal

The Developer Portal (`hub/apps/baas/developer_portal.py`) provides developer resources:

- **API Documentation**: Overview of API endpoints, authentication, and rate limiting
- **OpenAPI Schema**: Complete OpenAPI 3.0 schema for API integration
- **SDK Downloads**: Download links for Python and JavaScript SDKs
- **API Key Management**: Create, list, update, and revoke API keys

**Developer Portal Endpoints**:
- `GET /api/v1/baas/docs/` - Get API documentation
- `GET /api/v1/baas/docs/openapi.json` - Get OpenAPI schema
- `GET /api/v1/baas/docs/sdks/` - Get SDK download links

### BaaS Platform Data Flow Diagrams

#### API Key Creation Flow

```
User Request (API Key Name + Tier)
        ↓
API Endpoint: POST /api/v1/baas/api-keys/
        ↓
APIKeyViewSet.create()
        ↓
┌───────────────────────────────────────┐
│ 1. Validate Request                   │
│    - Check tier validity              │
│    - Validate expiration date         │
│    - Check tenant permissions         │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Generate API Key                   │
│    - Generate secure key              │
│    - Hash key for storage             │
│    - Create APIKey record             │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Set Tier Quotas                    │
│    - Apply tier limits                │
│    - Initialize usage counters        │
└───────────────┬───────────────────────┘
                ↓
        Event Bus (Publish baas.api_key.created)
                ↓
        ┌───────┼───────┐
        ↓       ↓       ↓
    Notify  Audit  Webhook
```

#### API Request Flow with Usage Tracking

```
API Request (with API Key)
        ↓
API Gateway
        ↓
┌───────────────────────────────────────┐
│ 1. Authenticate API Key                │
│    - Validate API key                  │
│    - Check revocation status           │
│    - Get tier information              │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Check Rate Limits                  │
│    - Check tier quotas                │
│    - Enforce rate limits              │
│    - Track request                    │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Route to Service                   │
│    - Forward request                  │
│    - Get response                     │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Track Usage                        │
│    - Record request                   │
│    - Update statistics                │
│    - Check quotas                     │
└───────────────┬───────────────────────┘
                ↓
        Return Response
```

### BaaS Platform Component Integration

**Component Diagram**:
```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - Rate Limiting                                  │  │
│  │  - Authentication                                 │  │
│  │  - Request Routing                                │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              UsageTrackingService                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - track_request()                                │  │
│  │  - get_usage_statistics()                        │  │
│  │  - check_quota()                                 │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              Developer Portal                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - APIKeyViewSet                                  │  │
│  │  - DeveloperDocumentationViewSet                 │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓               ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  PostgreSQL  │ │     Redis     │ │  Event Bus   │
│  (API Keys)  │ │  (Usage Cache)│ │  (Events)    │
└──────────────┘ └──────────────┘ └──────────────┘
```

## ODH Integration

### Overview

The ODH (Open Data Hub) Integration provides comprehensive ML model management, training, and inference operations. The integration bridges the Hub platform with ODH services, enabling model registry, training pipelines, and inference services.

### ODH Integration Architecture Components

#### Model Registry Bridge

The ModelRegistryBridgeService (`hub/apps/ml/services.py`) provides a bridge between Hub assets and ODH Model Registry:

- **Model Linking**: Links ODH models to Hub assets and contracts
- **Model Versioning**: Manages model versions and metadata
- **Dataset Linking**: Links models to training, validation, and test datasets
- **Metadata Sync**: Syncs model metadata from ODH Model Registry
- **Asset Creation**: Creates Hub assets from ODH models

**Service Integration**:
- Extends `BaseService` for consistent error handling and metrics
- Implements `MLEventPublisher` for event-driven coordination
- Uses `ODHModelRegistryClient` for ODH communication
- Integrates with `ODHIntegrationBusinessRules` for validation

#### Training Pipeline

The ModelTrainingWorkflow (`hub/apps/orchestration/workflows/model_training.py`) orchestrates ML model training:

- **Dataset Validation**: Validates training datasets before training
- **DQ and Compliance Checks**: Runs data quality and compliance checks
- **Training Job Submission**: Submits training jobs to ODH Training Operator
- **Training Monitoring**: Monitors training job progress and status
- **Model Linking**: Links trained models to assets after completion

**Workflow Steps**:
1. **validate_dataset**: Validate training dataset exists and is accessible
2. **run_dq_checks**: Run data quality checks on dataset
3. **run_compliance_scan**: Run compliance scan on dataset
4. **submit_training_job**: Submit training job to ODH Training Operator
5. **monitor_training**: Monitor training job progress
6. **link_model**: Link trained model to asset after completion

#### Inference Service

The InferenceValidationService (`hub/apps/ml/inference_service.py`) provides model inference capabilities:

- **Input Validation**: Validates inference input data against contracts
- **Inference Execution**: Executes inference via ODH Inference Scheduler
- **Output Validation**: Validates inference output against contracts
- **Metrics Tracking**: Tracks inference metrics (latency, accuracy, error rate)
- **Quality Monitoring**: Monitors inference quality and data drift

**Inference Flow**:
```
Inference Request
        ↓
InferenceValidationService.validate_input()
        ↓
ODH Inference Scheduler
        ↓
Inference Execution
        ↓
InferenceValidationService.validate_output()
        ↓
Metrics Tracking
        ↓
Return Prediction
```

### ODH Integration Data Flow Diagrams

#### Model Training Flow

```
User Request (Model ID + Dataset ID + Config)
        ↓
API Endpoint: POST /api/v1/ml/training/jobs/
        ↓
ModelTrainingWorkflow.execute()
        ↓
┌───────────────────────────────────────┐
│ 1. Validate Dataset                   │
│    - Check dataset exists              │
│    - Verify dataset accessibility     │
│    - Validate dataset format          │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Run DQ and Compliance Checks       │
│    - DQ Service                        │
│    - Compliance Service                │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Submit Training Job to ODH         │
│    - ODHTrainingClient                 │
│    - Training Operator API             │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Monitor Training Progress           │
│    - Poll ODH Training Operator        │
│    - Track training metrics            │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 5. Link Model to Asset                │
│    - Create model record               │
│    - Link to asset                     │
└───────────────┬───────────────────────┘
                ↓
        Event Bus (Publish ml.training.completed)
```

#### Model Inference Flow

```
Inference Request (Model ID + Input Data)
        ↓
API Endpoint: POST /api/v1/ml/inference/deployments/predict/
        ↓
InferenceValidationService.predict()
        ↓
┌───────────────────────────────────────┐
│ 1. Validate Input                      │
│    - Check contract schema             │
│    - Validate input format             │
│    - Check data types                  │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Execute Inference                   │
│    - ODH Inference Scheduler           │
│    - Model inference                   │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Validate Output                     │
│    - Check contract schema             │
│    - Validate output format            │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Track Metrics                       │
│    - Record latency                    │
│    - Track accuracy                    │
│    - Monitor data drift                │
└───────────────┬───────────────────────┘
                ↓
        Return Prediction
```

### ODH Integration Component Integration

**Component Diagram**:
```
┌─────────────────────────────────────────────────────────┐
│                    API Service (Django)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │         ML/ODH Views (REST + GraphQL)            │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│            ModelRegistryBridgeService                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - link_model_to_asset()                          │  │
│  │  - link_model_to_dataset()                       │  │
│  │  - sync_from_odh()                               │  │
│  └──────────────────┬───────────────────────────────┘  │
└──────────────────────┼─────────────────────────────────┘
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓               ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ModelTraining │ │Inference     │ │ODH           │
│  Workflow    │ │Service       │ │Clients       │
└───────┬───────┘ └──────┬───────┘ └──────┬───────┘
        ↓                ↓                ↓
┌─────────────────────────────────────────────────────────┐
│              Workflow Engine                             │
│  - State management                                      │
│  - Retry logic                                           │
│  - Compensation logic                                    │
└──────────────────┬───────────────────────────────────────┘
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│ODH Model │ │ODH       │ │ODH       │
│Registry  │ │Training   │ │Inference │
│          │ │Operator   │ │Scheduler │
└──────────┘ └──────────┘ └──────────┘
        ↓          ↓          ↓
┌─────────────────────────────────────────────────────────┐
│                  Event Bus                               │
│  - Redis Pub/Sub (real-time)                            │
│  - PostgreSQL (persistence)                              │
└──────────────────┬───────────────────────────────────────┘
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│Notification│ │  Audit  │ │ Webhook  │
│  Service   │ │ Service │ │ Service  │
└───────────┘ └──────────┘ └──────────┘
```

## Related Documentation

- [Services Architecture](SERVICES_ARCHITECTURE.md) - Detailed service documentation
- [Docker Compose Deployment](DOCKER_COMPOSE_DEPLOYMENT.md) - Deployment guide
- [API Standards](API_STANDARDS.md) - API design standards
- [Event Bus Architecture](EVENT_BUS.md) - Event-driven patterns
- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - ODPS usage guide
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture
- [BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md) - BaaS CLI commands
- [BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md) - BaaS SDK APIs
- [ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md) - ODH CLI commands
- [ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md) - ODH SDK APIs
- [Use Cases](USE_CASES.md) - BaaS Platform and ODH Integration use cases
- [User Journeys](USER_JOURNEYS.md) - User journey maps including ML/ODH operations


### Design Principles


**Last Updated**: 2026-03-22

This document records design decisions for the Data Interoperability Hub platform.

---

## Notifications (Header)

**Decision**: Implement minimal notifications placeholder in the header.

**Context**: The header included a notifications button (bell icon) that toggled state but displayed nothing when clicked, creating a dead UI element.

**Options considered**:
1. **Remove the button** — Clean removal; users would not see a non-functional control.
2. **Implement minimal placeholder** — Show a dropdown with empty state when clicked; sets expectations for future functionality.
3. **Implement full notifications** — Requires backend API, real-time updates, persistence; out of scope for current phase.

**Chosen**: Option 2 — Minimal placeholder.

**Implementation**:
- Notifications button remains in the header (bell icon with badge showing "0").
- When clicked, a dropdown opens with:
  - Title: "No notifications yet"
  - Message: "Notifications will appear here when you have updates (e.g. access requests, DQ results)."
- Click outside or Escape key closes the dropdown.
- Dropdown uses `role="region"` (informational content; not `role="menu"` which requires menu items).
- No backend integration; placeholder only.

**Future work**: When notifications backend is available (e.g. from audit events, access requests, DQ run completion), the dropdown will be extended to display real notification items. See `frontend/src/features/shell/components/Header.tsx` and `Header.css` for the implementation.

---

## 2. Service Boundaries


### Backend Architecture


Complete engineering-grade documentation of the ODPS (Open Data Product Standard) backend architecture in the Data Interoperability Hub.

## Table of Contents

1. [Overview](#overview)
2. [Component Architecture](#component-architecture)
3. [Service Layer Architecture](#service-layer-architecture)
4. [Workflow Architecture](#workflow-architecture)
5. [Event System Architecture](#event-system-architecture)
6. [Job Queue Architecture](#job-queue-architecture)
7. [Database Schema](#database-schema)
8. [Data Flows](#data-flows)
9. [Integration Points](#integration-points)
10. [Architecture Diagrams](#architecture-diagrams)

---

## Overview

The ODPS backend architecture provides comprehensive support for the Open Data Product Standard, a marketplace-focused specification that complements ODCS (Open Data Contract Standard). The architecture is designed for:

- **Scalability**: Horizontal scaling with stateless services
- **Reliability**: Transaction management, compensation logic, and retry mechanisms
- **Security**: URL validation, path traversal prevention, rate limiting, and security logging
- **Observability**: Comprehensive event publishing, metrics, and audit logging
- **Maintainability**: Clean separation of concerns, dependency injection, and testability

### Key Architectural Principles

1. **Separation of Concerns**: Clear boundaries between parsing, normalization, generation, and resolution
2. **Dependency Injection**: Services and components are injected rather than tightly coupled
3. **Transaction Management**: Atomic operations with compensation logic for rollback
4. **Event-Driven**: Asynchronous coordination through event bus
5. **Security-First**: Security controls at every layer (validation, rate limiting, audit logging)

---

## Component Architecture

The ODPS backend consists of four core components: **Parser**, **Normalizer**, **Generator**, and **Ref Resolver**.

### 1. ODPS Parser (`hub/apps/contracts/odps_parser.py`)

**Purpose**: Parse and validate ODPS documents in JSON/YAML format.

**Key Features**:
- Automatic format detection (JSON/YAML)
- Schema validation using JSON Schema (Draft 2020-12)
- Version detection (ODPS 4.1, 4.0, etc.)
- Detailed error messages with file path and line number context
- Support for multiple ODPS versions

**Key Classes**:
- `ODPSParser`: Main parser class with static methods
- `ODPSValidationError`: Exception for parsing/validation errors

**Key Methods**:
```python
ODPSParser.parse(content: str, format: str) -> Dict[str, Any]
ODPSParser.validate(odps_document: Dict, version: str) -> Tuple[bool, List[Dict]]
```

**Error Handling**:
- `ODPSValidationError` with context (file_path, line_number, validation_errors, error_code)
- Graceful degradation for missing optional fields
- Field-level error tracking

**Dependencies**:
- `jsonschema` library for schema validation
- `yaml` library for YAML parsing
- `hub/apps/contracts/odps_schema.py` for ODPS schema definitions

---

### 2. ODPS Normalizer (`hub/apps/contracts/normalization/odps_normalizer.py`)

**Purpose**: Normalize ODPS documents to HubContract format.

**Key Features**:
- Version-specific normalization (ODPS 4.1, 4.0, 3.x, 2.x, 1.x)
- Comprehensive error handling with context
- Graceful degradation for missing optional fields
- Field-level error tracking
- Type validation and conversion

**Key Classes**:
- `ODPSNormalizer`: Main normalizer class implementing `SpecNormalizer` protocol
- Version-specific normalizers: `ODPSNormalizerV4_1`, `ODPSNormalizerV4_0`, etc.

**Key Methods**:
```python
ODPSNormalizer.normalize(contract_data: Dict, spec_version: Optional[str]) -> NormalizationResult
ODPSNormalizer.supports(spec_type: str, spec_version: str, contract_data: Dict) -> bool
```

**Normalization Flow**:
1. Detect ODPS version (if not provided)
2. Select version-specific normalizer
3. Map ODPS fields to HubContract structure:
   - `product.details[lang].productID` → `hub_contract.id`
   - `product.details[lang].name` → `hub_contract.info.name`
   - `product.marketplace.pricingPlans` → `hub_contract.marketplace.x_odps.pricing_plans`
   - `product.marketplace.accessMethods` → `hub_contract.marketplace.x_odps.access_methods`
4. Extract marketplace information (pricing, access methods, payment gateways)
5. Extract contract information (from `product.contract.spec` or `product.contract.$ref`)
6. Return `NormalizationResult` with hub_contract, status, errors, warnings

**Error Handling**:
- `ODPSNormalizationError` with context (field_path, expected, actual)
- Field-level error tracking in `NormalizationResult.errors`
- Warnings for missing optional fields in `NormalizationResult.warnings`

**Dependencies**:
- `hub/apps/contracts/normalization.py` for `NormalizationResult` and `SpecNormalizer`
- `hub/apps/contracts/odps_version_detection.py` for version detection

---

### 3. ODPS Generator (`hub/apps/contracts/odps_generator.py`)

**Purpose**: Generate ODPS documents from HubContract format (reverse operation of normalization).

**Key Features**:
- ODPS 4.1 generation (latest version)
- Comprehensive error handling with `ODPSExportError`
- Field-level error context (field name, expected type, actual type)
- Support for YAML and JSON output formatting
- Optional embedding of original ODCS contract inline

**Key Functions**:
```python
generate_odps_from_hubcontract(
    hub_contract: Dict,
    target_version: str = "4.1",
    original_odcs_contract: Optional[Dict] = None,
    original_odcs_url: Optional[str] = None
) -> Dict[str, Any]
```

**Generation Flow**:
1. Validate HubContract structure (required sections: `info`)
2. Map HubContract fields to ODPS structure:
   - `hub_contract.id` → `product.details[lang].productID`
   - `hub_contract.info.name` → `product.details[lang].name`
   - `hub_contract.marketplace.x_odps.pricing_plans` → `product.marketplace.pricingPlans`
   - `hub_contract.marketplace.x_odps.access_methods` → `product.marketplace.accessMethods`
3. Embed original ODCS contract (if provided) as `product.contract.spec`
4. Reference original ODCS contract URL (if provided) as `product.contract.contractURL`
5. Return ODPS document dictionary

**Error Handling**:
- `ODPSExportError` with context (field_path, expected, actual)
- Validation errors for missing required sections
- Type conversion errors with detailed context

**Dependencies**:
- `yaml` library for YAML output (optional)
- `json` library for JSON output

---

### 4. Ref Resolver (`hub/apps/contracts/ref_resolver.py`)

**Purpose**: Securely resolve `$ref` references in ODPS documents (internal, local, external).

**Key Features**:
- **Three Reference Types**:
  - **Internal**: References within the same document (`#/definitions/...`)
  - **Local**: References to local files (`./path/to/file.json`)
  - **External**: References to external URLs (`https://example.com/schema.json`)
- **Security Features**:
  - URL validation (allowlist/denylist)
  - Path traversal prevention
  - Size limits (per-ref and total)
  - Timeout controls (per-ref and total)
  - Redis caching for external refs (TTL: 1 hour)
  - Rate limiting (global, tenant, user)
  - Security logging (all security events)
- **Progress Tracking**: Progress events for long-running resolution operations

**Key Classes**:
- `RefResolver`: Main resolver class
- `ODPSRefsConfig`: Configuration for ref resolution (allowlists, denylists, base directories)
- `ExternalRefHandling`: Enum for external ref handling modes (RESOLVE, SKIP, DISABLE)

**Key Methods**:
```python
RefResolver.resolve_all_refs(
    document: Dict,
    preserve_original: bool = True,
    external_ref_handling: ExternalRefHandling = ExternalRefHandling.RESOLVE
) -> Tuple[Dict, Dict]

RefResolver.resolve_internal(ref_path: str, document: Dict) -> Any
RefResolver.resolve_local(ref_path: str) -> Dict[str, Any]
RefResolver.resolve_external(url: str) -> Dict[str, Any]
```

**Security Controls**:
1. **URL Validation** (`_validate_external_url`):
   - Scheme validation (only `https://` allowed)
   - URL length limit (`MAX_URL_LENGTH = 2048`)
   - Allowlist/denylist checking
   - Malformed URL detection

2. **Path Traversal Prevention** (`resolve_local`):
   - Base directory validation
   - Path normalization and resolution
   - Allowed directories checking
   - Security violation logging

3. **Size Limits** (`_check_size_limit`):
   - Per-ref size limit (default: 1MB)
   - Total size limit (default: 10MB)
   - Security violation logging

4. **Timeout Controls** (`_check_timeout`):
   - Per-ref timeout (default: 30s)
   - Total timeout (default: 5 minutes)
   - Security violation logging

5. **Rate Limiting** (`hub/apps/contracts/odps_rate_limiting.py`):
   - Global rate limit (default: 1000 requests/hour)
   - Tenant rate limit (default: 100 requests/hour)
   - User rate limit (default: 50 requests/hour)
   - Redis-based rate limiting

6. **Security Logging** (`hub/apps/contracts/odps_security_logging.py`):
   - All security events logged to `SecurityAuditLog` model
   - Event types: `EXTERNAL_REF_FETCH`, `RATE_LIMIT_EXCEEDED`, `SECURITY_VIOLATION`, `CACHE_HIT`, `CACHE_MISS`
   - Severity levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

**Dependencies**:
- `redis` for caching and rate limiting
- `requests` for HTTP requests (external refs)
- `hub/apps/contracts/config/odps_refs_config.py` for configuration
- `hub/apps/contracts/models.py` for `SecurityAuditLog` model

---

## Service Layer Architecture

The service layer provides business logic for ODPS operations, encapsulating transaction management, event publishing, and error handling.

### 1. ODPSService (`hub/apps/contracts/services.py`)

**Purpose**: Service for ODPS-specific operations.

**Key Responsibilities**:
- ODPS contract creation
- ODPS normalization
- ODPS linking to ODCS
- ODPS export
- ODPS generation from HubContract

**Key Methods**:
```python
ODPSService.create_odps(
    odps_raw: str,
    odps_format: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    resolve_external_refs: bool = True,
    target_version: Optional[str] = None
) -> Contract

ODPSService.normalize_odps(
    odps_doc: Dict[str, Any],
    odps_version: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]

ODPSService.export_odps(
    contract_id: str,
    target_version: str = "4.1",
    output_format: str = "json",
    tenant_id: Optional[str] = None
) -> str

ODPSService.generate_odps_from_hubcontract(
    hub_contract: Dict[str, Any],
    target_version: str = "4.1",
    original_odcs_contract: Optional[Dict[str, Any]] = None,
    original_odcs_url: Optional[str] = None
) -> Dict[str, Any]
```

**Transaction Management**:
- All operations wrapped in `@transaction.atomic`
- Compensation logic for rollback on failure
- State tracking for compensation (`ODPSCreationState`, `ODPSLinkingState`)

**Event Publishing**:
- Extends `ODPSEventPublisher` for ODPS-specific events
- Publishes `odps.created`, `odps.normalized`, `odps.exported`, `odps.linked` events
- Event IDs tracked for compensation

**Error Handling**:
- `ValidationError` for validation failures
- `NotFoundError` for missing resources
- Compensation logic for partial failures

**Dependencies**:
- `BaseService` for metrics and common functionality
- `ODPSEventPublisher` for event publishing
- `ODPSParser`, `ODPSNormalizer`, `ODPSGenerator`, `RefResolver` for core operations
- `hub/apps/contracts/odps_compensation.py` for compensation logic

---

### 2. ContractService (`hub/apps/contracts/services.py`)

**Purpose**: Service for contract operations, including ODPS-ODCS coordination.

**Key Responsibilities**:
- Contract retrieval and validation
- ODPS-ODCS linking coordination
- Auto-generation of ODPS from ODCS
- Contract lifecycle management

**Key Methods**:
```python
ContractService.link_odps_to_odcs(
    odcs_contract_id: str,
    odps_contract_id: Optional[str] = None,
    odps_raw: Optional[str] = None,
    odps_format: Optional[str] = None,
    resolve_external_refs: bool = True,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Contract

ContractService.coordinate_odcs_odps_operations(
    odcs_contract_id: str,
    odps_operation: str,
    odps_contract_id: Optional[str] = None,
    odps_raw: Optional[str] = None,
    odps_format: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]
```

**ODPS-ODCS Coordination**:
- Validates linking compatibility
- Establishes bidirectional links (ODPS ↔ ODCS)
- Stores links in `hub_contract_json.extensions.x_odps.odcs_link` and `odps_link`
- Compensation logic for rollback

**Dependencies**:
- `ODPSService` for ODPS-specific operations
- `BaseService` for metrics and common functionality
- `ContractEventPublisher` and `ODPSEventPublisher` for event publishing
- `hub/apps/contracts/linking_validation.py` for linking validation

---

## Workflow Architecture

The workflow architecture orchestrates multi-step ODPS operations with proper error handling, retry logic, and compensation.

### ProductCreationWorkflow (`hub/apps/orchestration/workflows/product_creation.py`)

**Purpose**: Orchestrates the ODPS product creation process (Product-First flow).

**Workflow Steps**:
1. **parse_odps**: Parse ODPS document, validate schema, detect version
2. **resolve_refs**: Resolve $ref references (internal, local, external)
3. **extract_contract**: Extract ODCS from `product.contract` (required)
4. **validate_odcs**: Validate extracted ODCS contract
5. **normalize_odcs**: Normalize ODCS → HubContract (technical)
6. **normalize_odps**: Normalize ODPS → HubContract (marketplace)
7. **create_odcs_contract**: Create ODCS contract record
8. **create_odps_contract**: Create ODPS contract record
9. **link_contracts**: Establish bidirectional link (ODPS ↔ ODCS)
10. **link_data_file**: Link data file to ODPS contract (optional)
11. **index_for_search**: Index for search (ODPS product + ODCS technical)
12. **semantic_mapping**: Map ODPS to RDF (async job)

**Compensation Tasks**:
- `rollback_normalize_odcs`: Rollback ODCS normalization
- `rollback_normalize_odps`: Rollback ODPS normalization
- `rollback_odcs_contract`: Rollback ODCS contract creation
- `rollback_odps_contract`: Rollback ODPS contract creation
- `rollback_link_contracts`: Rollback contract linking
- `rollback_link_data_file`: Rollback data file linking

**Error Handling**:
- Transaction rollback on failure
- Compensation logic for partial failures
- Detailed error logging with context
- Workflow status tracking (`WorkflowStatus.PENDING`, `RUNNING`, `COMPLETED`, `FAILED`)

**Event Publishing**:
- Workflow events: `workflow.started`, `workflow.completed`, `workflow.failed`
- Step events: `workflow.step.started`, `workflow.step.completed`, `workflow.step.failed`
- ODPS events: `odps.created`, `odps.normalized`, `odps.linked`

**Dependencies**:
- `WorkflowEngine` for workflow orchestration
- `WorkflowRegistry` for workflow registration
- `ODPSParser`, `RefResolver`, `ODPSNormalizer` for core operations
- `SearchIndexer` for search indexing
- `hub/apps/semantic/utils.py` for semantic mapping

---

## Event System Architecture

The event system provides asynchronous coordination between services using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence.

### Event Bus (`hub/apps/core/events/bus.py`)

**Purpose**: Event-driven communication infrastructure.

**Components**:
1. **Redis Pub/Sub**: Real-time event delivery (fire-and-forget)
2. **PostgreSQL**: Event persistence for replay, audit, and debugging
3. **Dead Letter Queue**: Failed event storage
4. **Event Schema**: JSON Schema validation

**Key Classes**:
- `EventBus`: Main event bus class
- `EventPublisher`: Convenience class for publishing events
- `EventSubscriber`: Subscription management

**Event Publishing**:
```python
publisher = EventPublisher(
    service_name="contract_service",
    tenant_id=tenant_id,
    user_id=user_id
)

event_id = publisher.publish(
    event_type="odps.created",
    data={"contract_id": contract_id, "odps_version": "4.1"},
    tags=["odps", "contract"]
)
```

**Event Schema**:
```json
{
  "event_id": "uuid",
  "event_type": "odps.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "contract_service",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid",
    "odps_version": "4.1"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["odps", "contract"]
  }
}
```

**ODPS Event Types**:
- `odps.created`: ODPS contract created
- `odps.normalized`: ODPS contract normalized
- `odps.exported`: ODPS contract exported
- `odps.linked`: ODPS contract linked to ODCS
- `odps.ref.progress`: $ref resolution progress
- `odps.ref.completed`: $ref resolution completed
- `odps.ref.failed`: $ref resolution failed

**Event Subscribers**:
- `SearchService`: Index contracts for search
- `NotificationService`: Send creation notifications
- `AuditService`: Log contract operations
- `WebhookService`: Deliver webhooks
- `SemanticService`: Trigger semantic mapping

**Dependencies**:
- `redis` for Pub/Sub
- `PostgreSQL` for persistence
- `hub/apps/core/events/schema.py` for event schema validation

---

## Job Queue Architecture

The job queue system processes asynchronous ODPS operations using Redis-backed queues (django-rq).

### Priority Queues

**Three Priority Levels**:
- **HIGH** (`job_critical`): Critical long-running jobs (DQ runs, compliance runs)
- **NORMAL** (`job_default`): Standard jobs (semantic mapping, ODPS normalization, ref resolution)
- **LOW** (`job_low`): Quick validation jobs (contract validation)

**Queue Configuration** (`hub/settings.py`):
```python
RQ_QUEUES = {
    "job_critical": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 1800,  # 30 minutes
    },
    "job_default": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 360,  # 6 minutes
    },
    "job_low": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 60,  # 1 minute
    },
}
```

### ODPS Job Types

**Job Types** (`hub/apps/jobs/models.py`):
- `ODPS_NORMALIZATION`: Normalize ODPS contract (NORMAL priority, 10 min timeout)
- `ODPS_REF_RESOLUTION`: Resolve $ref references (NORMAL priority, 10 min timeout)
- `ODPS_EXPORT`: Export ODPS contract (NORMAL priority, 5 min timeout)
- `ODPS_SEMANTIC_MAPPING`: Map ODPS to RDF (NORMAL priority, 10 min timeout)
- `ODPS_LINKING`: Link ODPS to ODCS (NORMAL priority, 5 min timeout)

**Job Execution** (`hub/apps/jobs/tasks.py`):
```python
def _execute_odps_ref_resolution_job(job_obj: Job) -> dict:
    """
    Execute ODPS_REF_RESOLUTION job.

    Resolves all $ref references in an ODPS contract with progress tracking
    and event publishing.
    """
    # Get contract
    contract = Contract.objects.get(id=contract_id)

    # Parse ODPS document
    odps_doc = ODPSParser.parse(contract.original_raw, contract.original_format.lower())

    # Resolve refs with progress tracking
    resolver = RefResolver(tenant_id=tenant_id, user_id=user_id)
    resolved_doc, _ = resolver.resolve_all_refs(odps_doc)

    # Update contract with resolved document
    contract.original_raw_resolved = json.dumps(resolved_doc)
    contract.save()

    # Publish completion event
    odps_event_publisher.publish_odps_ref_completed(...)

    return {"refs_resolved": len(refs), "contract_id": str(contract.id)}
```

**Progress Tracking**:
- Progress events published via `odps.ref.progress` events
- Progress percentage tracked in `job.details_json.progress_percentage`
- Current phase tracked in `job.details_json.current_phase`

**Dependencies**:
- `django-rq` for job queue management
- `redis` for queue storage
- `hub/apps/jobs/models.py` for `Job` model
- `hub/apps/jobs/utils.py` for job creation utilities

---

## Database Schema

The database schema stores ODPS contracts, security audit logs, and workflow instances.

### Contract Model (`hub/apps/contracts/models.py`)

**Table**: `contracts`

**Key Fields**:
- `id`: UUID (primary key)
- `tenant`: Foreign key to `tenants.Tenant`
- `asset`: Foreign key to `assets.Asset` (nullable)
- `version`: Integer (per-asset version counter)
- `status`: CharField (DRAFT, ACTIVE, RETIRED)
- `original_spec_type`: CharField (ODCS, ODPS)
- `original_spec_version`: CharField (e.g., "4.1", "3.0.2")
- `original_format`: CharField (JSON, YAML)
- `original_raw`: TextField (original contract content)
- `original_raw_resolved`: TextField (resolved contract content, nullable)
- `hub_contract_version`: CharField (HubContract version, nullable)
- `hub_contract_json`: JSONField (normalized HubContract, GIN indexed)
- `normalization_status`: CharField (NOT_NORMALIZED, NORMALIZED_OK, NORMALIZED_WITH_WARNINGS, NORMALIZATION_FAILED)
- `normalization_errors`: JSONField (array of errors)
- `normalization_warnings`: JSONField (array of warnings)
- `validation_status`: CharField (VALID, INVALID, WARNING_ONLY, ERROR)
- `validation_errors`: JSONField (array of errors)
- `validation_warnings`: JSONField (array of warnings)
- `created_by`: Foreign key to `auth.User` (nullable)
- `created_at`: DateTimeField (auto_now_add)
- `updated_at`: DateTimeField (auto_now)

**Indexes**:
- `(tenant, asset)` - For tenant-asset queries
- `(tenant, status)` - For tenant status queries
- `(tenant, validation_status)` - For validation queries
- `hub_contract_json` - GIN index for JSONB queries (Django 6)

**Constraints**:
- Unique constraint: `(tenant, asset, version)` (when asset is not null)

**ODPS-Specific Fields**:
- `original_spec_type = "ODPS"` for ODPS contracts
- `hub_contract_json.extensions.x_odps.odcs_link` - Link to ODCS contract (bidirectional)
- `hub_contract_json.extensions.x_odps.odps_link` - Link to ODPS contract (in ODCS contracts)

---

### SecurityAuditLog Model (`hub/apps/contracts/models.py`)

**Table**: `security_audit_logs`

**Purpose**: Append-only security audit log for ODPS $ref resolution security events.

**Key Fields**:
- `id`: UUID (primary key)
- `event_type`: CharField (EXTERNAL_REF_FETCH, RATE_LIMIT_EXCEEDED, SECURITY_VIOLATION, CACHE_HIT, CACHE_MISS, CACHE_EVICTION)
- `timestamp`: DateTimeField (auto_now_add, indexed)
- `tenant`: Foreign key to `tenants.Tenant` (nullable)
- `user`: Foreign key to `auth.User` (nullable)
- `contract`: Foreign key to `contracts.Contract` (nullable)
- `severity`: CharField (LOW, MEDIUM, HIGH, CRITICAL, nullable)
- `ref_type`: CharField (internal, local, external, nullable)
- `ref_path`: CharField (max_length=2048, nullable)
- `resolved_path`: CharField (max_length=2048, nullable)
- `rate_limit_level`: CharField (global, tenant, user, nullable)
- `cache_operation`: CharField (hit, miss, eviction, nullable)
- `cache_key`: CharField (max_length=512, nullable)
- `violation_type`: CharField (max_length=100, nullable)
- `attempted_path`: CharField (max_length=2048, nullable)
- `attempted_url`: CharField (max_length=2048, nullable)
- `description`: TextField (nullable)
- `metadata_json`: JSONField (additional metadata)

**Indexes**:
- `(event_type, timestamp)` - For event type queries
- `(tenant, timestamp)` - For tenant queries
- `(user, timestamp)` - For user queries
- `(tenant, event_type, timestamp)` - For tenant-event queries
- `(tenant, user, timestamp)` - For tenant-user queries
- `(ref_type, timestamp)` - For ref type queries
- `(cache_operation, timestamp)` - For cache queries
- `(timestamp)` - For retention queries

**Constraints**:
- Append-only: Updates and deletes are prevented (override `save()` and `delete()`)

---

### WorkflowInstance Model (`hub/apps/orchestration/models.py`)

**Table**: `workflow_instances`

**Purpose**: Track workflow execution state.

**Key Fields**:
- `id`: UUID (primary key)
- `workflow_name`: CharField (e.g., "product_creation")
- `status`: CharField (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- `input_data`: JSONField (workflow input)
- `output_data`: JSONField (workflow output, nullable)
- `current_step_index`: IntegerField (current step)
- `error_message`: TextField (nullable)
- `error_details`: JSONField (nullable)
- `tenant`: Foreign key to `tenants.Tenant` (nullable)
- `created_by`: Foreign key to `auth.User` (nullable)
- `created_at`: DateTimeField (auto_now_add)
- `updated_at`: DateTimeField (auto_now)
- `completed_at`: DateTimeField (nullable)

**Indexes**:
- `(workflow_name, status)` - For workflow queries
- `(tenant, status)` - For tenant queries
- `(status, created_at)` - For status queries

---

## Data Flows

### ODPS Ingestion Flow

**Flow**: User → API → ODPSService → ProductCreationWorkflow → Database

**Steps**:
1. **API Request**: `POST /api/v1/contracts/products/` with ODPS document
2. **ODPSService.create_odps()**:
   - Parse ODPS document (`ODPSParser.parse()`)
   - Detect version (`detect_odps_version()`)
   - Validate schema (`ODPSParser.validate()`)
   - Resolve $ref references (`RefResolver.resolve_all_refs()`) [optional]
   - Normalize to HubContract (`ODPSNormalizer.normalize()`)
   - Create contract record (`Contract.objects.create()`)
   - Publish events (`odps.created`, `odps.normalized`)
3. **ProductCreationWorkflow** (if Product-First flow):
   - Extract ODCS from `product.contract`
   - Validate ODCS
   - Normalize ODCS → HubContract
   - Create ODCS contract record
   - Create ODPS contract record
   - Link contracts bidirectionally
   - Index for search
   - Trigger semantic mapping job
4. **Response**: Return created contracts and workflow instance ID

**Error Handling**:
- Validation errors return 400 Bad Request
- Compensation logic rolls back on failure
- Workflow status tracked in `WorkflowInstance`

---

### ODPS Normalization Flow

**Flow**: ODPS Document → ODPSNormalizer → HubContract

**Steps**:
1. **Version Detection**: Detect ODPS version from document
2. **Version-Specific Normalizer**: Select normalizer (V4_1, V4_0, etc.)
3. **Field Mapping**:
   - `product.details[lang].productID` → `hub_contract.id`
   - `product.details[lang].name` → `hub_contract.info.name`
   - `product.details[lang].description` → `hub_contract.info.description`
   - `product.marketplace.pricingPlans` → `hub_contract.marketplace.x_odps.pricing_plans`
   - `product.marketplace.accessMethods` → `hub_contract.marketplace.x_odps.access_methods`
   - `product.marketplace.paymentGateways` → `hub_contract.marketplace.x_odps.payment_gateways`
   - `license[lang].definition` → `hub_contract.marketplace.license_summary`
   - `license[lang].restrictions` → `hub_contract.marketplace.restricted_use`
   - `license[lang].rights` → `hub_contract.marketplace.intended_use`
4. **Contract Extraction**: Extract ODCS from `product.contract.spec` or `product.contract.$ref`
5. **Error Collection**: Collect errors and warnings
6. **Result**: Return `NormalizationResult` with hub_contract, status, errors, warnings

**Error Handling**:
- Field-level errors tracked in `NormalizationResult.errors`
- Warnings for missing optional fields in `NormalizationResult.warnings`
- `ODPSNormalizationError` raised for critical errors

---

### ODPS Export Flow

**Flow**: Contract → ODPSService → ODPSGenerator → ODPS Document

**Steps**:
1. **Contract Retrieval**: Get contract by ID
2. **HubContract Extraction**: Extract `hub_contract_json` from contract
3. **ODPS Generation**: `generate_odps_from_hubcontract()`:
   - Validate HubContract structure
   - Map HubContract fields to ODPS structure
   - Embed original ODCS contract (if linked) as `product.contract.spec`
   - Reference original ODCS contract URL (if available) as `product.contract.contractURL`
4. **Format Conversion**: Convert to JSON or YAML
5. **Response**: Return ODPS document string

**Error Handling**:
- `NotFoundError` if contract not found
- `ODPSExportError` for generation failures
- Validation errors for missing required sections

---

### ODPS Linking Flow

**Flow**: ODPS Contract + ODCS Contract → ContractService → Bidirectional Link

**Steps**:
1. **Validation**: Validate both contracts exist and are compatible
2. **Linking Validation**: Check for circular references, compatibility
3. **Bidirectional Link Creation**:
   - **ODPS → ODCS**: Store ODCS contract ID in `odps_contract.hub_contract_json.extensions.x_odps.odcs_link`
   - **ODCS → ODPS**: Store ODPS contract ID in `odcs_contract.hub_contract_json.extensions.x_odps.odps_link`
4. **Event Publishing**: Publish `odps.linked` event
5. **Response**: Return linked contracts

**Error Handling**:
- `ValidationError` for incompatible contracts
- `NotFoundError` if contracts not found
- Compensation logic for rollback on failure

---

## Integration Points

### Marketplace Service Integration

**Purpose**: Integrate ODPS marketplace information with marketplace listings.

**Integration Points**:
- **ContractMarketplacePolicyExtractor** (`hub/apps/marketplace/contract_integration.py`):
  - Reads marketplace policy from HubContract
  - Extracts pricing plans, access methods, payment gateways
  - Supports both ODCS contracts (with `marketplace.*` structure) and ODPS-linked contracts

**Event Integration**:
- `odps.created` event triggers marketplace listing creation
- `odps.normalized` event updates marketplace policy

**Dependencies**:
- `MarketplaceService` for marketplace operations
- `hub/apps/marketplace/services.py` for marketplace service

---

### Semantic Service Integration

**Purpose**: Map ODPS contracts to RDF/JSON-LD for semantic interoperability.

**Integration Points**:
- **Semantic Mapping** (`hub/apps/semantic/utils.py`):
  - `map_odps_to_semantic()`: Map ODPS contract to RDF
  - `map_odps_contract_to_semantic_via_service()`: Map via semantic service API
  - Triggered asynchronously via `ODPS_SEMANTIC_MAPPING` job

**Event Integration**:
- `odps.created` event triggers semantic mapping job
- `odps.normalized` event updates semantic mapping

**Dependencies**:
- `SemanticService` for RDF mapping
- `services/semantic-service/` for semantic service API

---

### Asset Service Integration

**Purpose**: Link ODPS contracts to assets for data product management.

**Integration Points**:
- **Asset-Contract Relationship**: ODPS contracts can be linked to assets via `contract.asset` foreign key
- **Asset Creation Workflow**: ODPS contracts can trigger asset creation workflows
- **Asset Activation**: ODPS contracts can activate assets when published

**Event Integration**:
- `odps.created` event triggers asset creation/update
- `odps.linked` event updates asset-contract relationships

**Dependencies**:
- `AssetService` for asset operations
- `hub/apps/assets/services.py` for asset service

---

### Event Bus Integration

**Purpose**: Asynchronous coordination between services.

**Integration Points**:
- **Event Publishing**: All ODPS operations publish events via `ODPSEventPublisher`
- **Event Subscribers**: Multiple services subscribe to ODPS events:
  - `SearchService`: Index contracts for search
  - `NotificationService`: Send creation notifications
  - `AuditService`: Log contract operations
  - `WebhookService`: Deliver webhooks
  - `SemanticService`: Trigger semantic mapping

**Event Types**:
- `odps.created`: ODPS contract created
- `odps.normalized`: ODPS contract normalized
- `odps.exported`: ODPS contract exported
- `odps.linked`: ODPS contract linked to ODCS
- `odps.ref.progress`: $ref resolution progress
- `odps.ref.completed`: $ref resolution completed
- `odps.ref.failed`: $ref resolution failed

**Dependencies**:
- `hub/apps/core/events/bus.py` for event bus
- `hub/apps/core/events/service_publishers.py` for `ODPSEventPublisher`

---

### Job Queue Integration

**Purpose**: Process long-running ODPS operations asynchronously.

**Integration Points**:
- **Job Creation**: ODPS operations create jobs via `hub/apps/jobs/utils.py`
- **Job Execution**: Jobs are processed by worker service (`services/worker/`)
- **Progress Tracking**: Jobs publish progress events via `odps.ref.progress`

**Job Types**:
- `ODPS_NORMALIZATION`: Normalize ODPS contract
- `ODPS_REF_RESOLUTION`: Resolve $ref references
- `ODPS_EXPORT`: Export ODPS contract
- `ODPS_SEMANTIC_MAPPING`: Map ODPS to RDF
- `ODPS_LINKING`: Link ODPS to ODCS

**Dependencies**:
- `django-rq` for job queue management
- `hub/apps/jobs/tasks.py` for job execution logic
- `services/worker/` for worker service

---

## Architecture Diagrams

### Component Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ODPS Backend Architecture                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Parser     │    │  Normalizer  │    │   Generator  │    │ Ref Resolver │
│              │    │              │    │              │    │              │
│ - Parse      │───▶│ - Normalize  │───▶│ - Generate   │───▶│ - Resolve    │
│ - Validate   │    │ - Map Fields │    │ - Export     │    │ - Security   │
│ - Detect Ver │    │ - Extract    │    │ - Format     │    │ - Cache      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  ODPSService    │
                          │                 │
                          │ - create_odps() │
                          │ - normalize()   │
                          │ - export()      │
                          │ - link()        │
                          └─────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ ProductCreation │
                          │    Workflow     │
                          │                 │
                          │ - Orchestrate   │
                          │ - Compensate    │
                          │ - Publish Events│
                          └─────────────────┘
```

---

### Data Flow Diagram

```
ODPS Ingestion Flow:

User Request
    │
    ▼
API Endpoint (POST /api/v1/contracts/products/)
    │
    ▼
ODPSService.create_odps()
    │
    ├─▶ ODPSParser.parse() ──────────┐
    │                                  │
    ├─▶ detect_odps_version()          │
    │                                  │
    ├─▶ ODPSParser.validate()          │
    │                                  │
    ├─▶ RefResolver.resolve_all_refs()│
    │                                  │
    └─▶ ODPSNormalizer.normalize() ────┼─▶ HubContract
                                       │
                                       ▼
                              Contract.objects.create()
                                       │
                                       ▼
                              ProductCreationWorkflow
                                       │
                                       ├─▶ Extract ODCS
                                       ├─▶ Normalize ODCS
                                       ├─▶ Create Contracts
                                       ├─▶ Link Contracts
                                       ├─▶ Index for Search
                                       └─▶ Semantic Mapping Job
```

---

### Integration Points Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ODPS Integration Points                  │
└─────────────────────────────────────────────────────────────┘

ODPSService
    │
    ├─▶ MarketplaceService ────▶ Marketplace Listings
    │
    ├─▶ SemanticService ────────▶ RDF/JSON-LD Mapping
    │
    ├─▶ AssetService ───────────▶ Asset-Contract Links
    │
    ├─▶ EventBus ────────────────▶ Event Subscribers
    │                                 │
    │                                 ├─▶ SearchService
    │                                 ├─▶ NotificationService
    │                                 ├─▶ AuditService
    │                                 ├─▶ WebhookService
    │                                 └─▶ SemanticService
    │
    └─▶ JobQueue ─────────────────▶ Worker Service
                                        │
                                        ├─▶ ODPS_NORMALIZATION
                                        ├─▶ ODPS_REF_RESOLUTION
                                        ├─▶ ODPS_EXPORT
                                        ├─▶ ODPS_SEMANTIC_MAPPING
                                        └─▶ ODPS_LINKING
```

---

## Summary

The ODPS backend architecture provides a comprehensive, engineering-grade implementation of the Open Data Product Standard with:

- **Component Architecture**: Parser, Normalizer, Generator, Ref Resolver
- **Service Layer**: ODPSService, ContractService with transaction management
- **Workflow Architecture**: ProductCreationWorkflow with compensation logic
- **Event System**: Event-driven coordination via Redis Pub/Sub and PostgreSQL
- **Job Queue**: Asynchronous processing with priority queues
- **Database Schema**: Contracts, SecurityAuditLog, WorkflowInstance models
- **Data Flows**: Ingestion, Normalization, Export, Linking flows
- **Integration Points**: Marketplace, Semantic, Asset, Event Bus, Job Queue integrations

All components follow Django and coding best practices, with comprehensive error handling, security controls, and observability.


### Services Architecture


**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Service Catalog](#service-catalog)
4. [Core Services](#core-services)
5. [Supporting Services](#supporting-services)
6. [Infrastructure Services](#infrastructure-services)
7. [Service Communication Patterns](#service-communication-patterns)
8. [Data Flow Diagrams](#data-flow-diagrams)
9. [Deployment Architecture](#deployment-architecture)
10. [Service Dependencies](#service-dependencies)

---

## Overview

The Interoperable Data Hub is built as a microservices architecture with clear service boundaries, well-defined APIs, and independent deployment capabilities. This document provides a comprehensive overview of all services, their responsibilities, and how they interact.

**Architecture Style**: Microservices
**Communication**: REST APIs, Message Queue (Redis), Event-Driven (Future)
**Deployment**: Docker containers, Kubernetes (production)
**Database**: PostgreSQL (primary), Redis (queue/cache), MinIO (object storage), Apache Jena Fuseki (RDF store)

---

## Architecture Principles

1. **Service Independence**: Each service can be developed, deployed, and scaled independently
2. **API-First**: All services expose well-defined REST APIs
3. **Stateless Services**: Services are stateless where possible, with state stored in databases
4. **Tenant Isolation**: All services enforce tenant isolation
5. **Observability**: All services expose metrics, logs, and traces
6. **Fail-Fast**: Services fail fast with clear error messages
7. **Backward Compatibility**: API changes maintain backward compatibility

---

## Service Catalog

### Core Services (MVP)

| Service | Implementation Status | Notes |
|---------|----------------------|-------|
| **API Service** (`api-service`) | ✅ Implemented | Main Django backend |
| **Worker Service** (`worker-service`) | ✅ Implemented | Background job processing |
| **DataContract Service** (`datacontract-service`) | ✅ Implemented | Contract validation and conversion |
| **DQ Service** (`dq-service`) | ✅ Implemented | Data quality checks |
| **Compliance Service** (`compliance-service`) | ✅ Implemented | Compliance scanning |
| **Semantic Service** (`semantic-service`) | ✅ Implemented | RDF mapping and SPARQL |

### Supporting Services (Post-MVP)

| Service | Implementation Status | Notes |
|---------|----------------------|-------|
| **Prefect Integration Service** (`prefect-integration-service`) | ✅ Implemented | Prefect workflow sync |
| **Search Service** (`search-service`) | ✅ Implemented | Full-text search |
| **Observability Service** (`observability-service`) | ✅ Implemented | Data observability |
| **Webhook Service** (`webhook-service`) | ✅ Implemented | Webhook delivery |

### Service Layer Services

| Service | Implementation Status | Phase | Notes |
|---------|----------------------|-------|-------|
| **DataMeshService** | ✅ Implemented | Phase 9.5.2 | Domain operations coordination |
| **VirtualizationService** | ✅ Implemented | Phase 9.5.3 | Virtual dataset coordination |
| **ContractService** | ✅ Implemented | MVP | Contract management |
| **AssetService** | ✅ Implemented | MVP | Asset management |
| **MarketplaceService** | ✅ Implemented | MVP | Marketplace operations |
| **IngestionService** | ✅ Implemented | Post-MVP | Scheduled ingestion |
| **GovernanceService** | ✅ Implemented | Post-MVP | Data governance |
| **SearchService** | ✅ Implemented | Post-MVP | Search operations |

### Infrastructure Services

11. **PostgreSQL** - Primary database
12. **Redis** - Job queue and caching
13. **MinIO** - S3-compatible object storage
14. **Apache Jena Fuseki** - RDF triple store
15. **Prometheus** - Metrics collection
16. **Grafana** - Metrics visualization
17. **Jaeger** - Distributed tracing
18. **Alertmanager** - Alert management

---

## Core Services

### API Service (`api-service`)

**Technology**: Django 6.0+, Django REST Framework, PostgreSQL
**Port**: 8000 (default), 8001 (staging)
**Status**: MVP

**Responsibilities**:
- REST API endpoints for all platform functionality
- GraphQL API endpoint
- Authentication and authorization
- Tenant management
- User management
- Asset management
- Contract management
- Marketplace operations
- Job orchestration
- Audit logging

**Key Endpoints**:
- `/api/v1/assets/*` - Asset management
- `/api/v1/contracts/*` - Contract management
- `/api/v1/datasets/*` - Dataset management
- `/api/v1/files/*` - File management
- `/api/v1/marketplace/*` - Marketplace operations
- `/api/v1/jobs/*` - Job management
- `/api/v1/tenants/*` - Tenant management
- `/api/v1/users/*` - User management
- `/graphql` - GraphQL endpoint

**Dependencies**:
- PostgreSQL (primary database)
- Redis (job queue)
- MinIO (file storage)
- DataContract Service (`http://datacontract-service:8080` or `http://localhost:8080`)
- DQ Service (`http://dq-service:8083` or `http://localhost:8083`)
- Compliance Service (`http://compliance-service:8082` or `http://localhost:8082`)
- Semantic Service (`http://semantic-service:8081` or `http://localhost:8081`)

**Scaling**: Horizontal scaling with load balancer

---

### Worker Service (`worker-service`)

**Technology**: Django 6.0+, RQ (Redis Queue), PostgreSQL
**Port**: N/A (background worker)
**Status**: MVP

**Responsibilities**:
- Process background jobs from Redis queue
- Execute contract validation jobs
- Execute DQ run jobs
- Execute compliance run jobs
- Execute semantic mapping jobs
- Execute scheduled ingestion jobs (Post-MVP)
- Job status updates
- Job error handling and retries

**Job Types**:
- `CONTRACT_VALIDATION` - Validate contracts
- `DQ_RUN` - Run data quality checks
- `COMPLIANCE_RUN` - Run compliance scans
- `SEMANTIC_MAPPING` - Map contracts to RDF
- `CONTRACT_MIGRATION` - Migrate contract versions
- `SCHEDULED_INGESTION` - Process scheduled ingestion (Post-MVP)

**Dependencies**:
- Redis (job queue)
- PostgreSQL (job status)
- DataContract Service (contract validation)
- DQ Service (data quality)
- Compliance Service (compliance)
- Semantic Service (semantic mapping)
- MinIO (file access)

**Scaling**: Horizontal scaling with multiple workers

---

### DataContract Service (`datacontract-service`)

**Technology**: FastAPI, DataContract CLI
**Port**: 8080 (default)
**Status**: MVP

**Responsibilities**:
- Contract validation (ODCS v3.0.2+)
- Contract linting
- Contract format conversion
- Contract specification compliance checking

**Key Endpoints**:
- `POST /validate` - Validate contract
- `POST /lint` - Lint contract
- `POST /convert` - Convert contract format
- `GET /health` - Health check

**Dependencies**: None (standalone service)

**Scaling**: Horizontal scaling

---

### DQ Service (`dq-service`)

**Technology**: FastAPI, Great Expectations, Soda
**Port**: 8083 (default)
**Status**: MVP

**Responsibilities**:
- Data quality checks using Great Expectations or Soda
- DQ profile execution (`intake_basic` and custom profiles)
- DQ result generation
- Custom DQ rule support (Post-MVP)

**Key Endpoints**:
- `POST /run` - Run DQ check
- `GET /profiles` - List DQ profiles
- `GET /health` - Health check

**Dependencies**:
- MinIO (data file access)
- Great Expectations / Soda (DQ engines)

**Scaling**: Horizontal scaling

---

### Compliance Service (`compliance-service`)

**Technology**: FastAPI, PII detection libraries
**Port**: 8082 (default)
**Status**: MVP

**Responsibilities**:
- PII and sensitive data detection
- Regulatory mapping (GDPR, HIPAA, SOX, LGPD, CCPA)
- Risk level calculation
- Compliance report generation
- Automatic data classification (Post-MVP)

**Key Endpoints**:
- `POST /run` - Run compliance scan
- `GET /regulations` - List supported regulations
- `GET /health` - Health check

**Dependencies**:
- MinIO (data file access)
- PII detection libraries

**Scaling**: Horizontal scaling

---

### Semantic Service (`semantic-service`)

**Technology**: FastAPI, RDFLib, Apache Jena Fuseki
**Port**: 8081 (default)
**Status**: MVP

**Responsibilities**:
- HubContract → RDF/JSON-LD mapping
- Stable URI generation
- SPARQL query execution
- Ontology management
- JSON-LD context generation

**Key Endpoints** (Direct Service):
- `POST /map/contract` - Map contract to RDF
- `POST /map/asset` - Map asset to RDF
- `POST /sparql` - Execute SPARQL query (read-only)
- `GET /sparql` - Execute SPARQL query via GET
- `GET /id/{type}/{id}` - Resolve URI to JSON-LD
- `GET /ontology` - Get ontology definition (Turtle format)
- `GET /context.jsonld` - Get JSON-LD context
- `GET /health` - Health check

**Key Endpoints** (via API Service `/api/v1/semantic/*`):
- `GET /api/v1/semantic/resources/` - List semantic resources
- `GET /api/v1/semantic/resources/{id}/` - Get semantic resource
- `POST /api/v1/semantic/sparql` - Execute SPARQL query (proxied to service)
- `GET /api/v1/semantic/id/{resource_type}/{resource_id}` - Resolve URI
- `GET /api/v1/semantic/id/field/{asset_uuid}/{field_name}` - Resolve field URI
- `GET /api/v1/semantic/ontology` - Get ontology (proxied to service)
- `GET /api/v1/semantic/context.jsonld` - Get JSON-LD context (proxied to service)

**Dependencies**:
- Apache Jena Fuseki (RDF store)
- PostgreSQL (contract/asset metadata)

**Scaling**: Horizontal scaling

---

## Supporting Services

### Prefect Integration Service (`prefect-integration-service`)

**Technology**: FastAPI, Prefect SDK
**Port**: 8084 (default)
**Status**: Post-MVP

**Responsibilities**:
- Sync scheduled ingestions with Prefect deployments
- Create Prefect workflows from database
- Monitor Prefect flow runs
- Update ingestion run status

**Key Endpoints**:
- `POST /deployments/sync` - Sync scheduled ingestion to Prefect deployment
- `GET /deployments` - List Prefect deployments
- `GET /health` - Health check

**Dependencies**:
- Prefect Server
- PostgreSQL (scheduled ingestions)

**Scaling**: Horizontal scaling

**Scheduled Ingestion Execution Model**:
- **Execution Flow**: Prefect worker → Hub API (Internal Worker API)
- **Prefect Worker**: Executes `scheduled_ingestion_full_flow` (HTTP-only, no Django)
- **Hub API**: Provides internal endpoints (`/api/v1/scheduled-ingestions/internal/*`) for:
  - Creating/updating runs (`POST /internal/runs/`, `PATCH /internal/runs/{id}/`)
  - Processing files (`POST /internal/process-file/`)
  - Getting configuration (`GET /internal/config/{id}/`)
- **Authentication**: Worker API key (`HUB_WORKER_API_KEY` or API key with scope `scheduled_ingestion:internal`)
- **Rate Limiting**: No rate limit (internal worker endpoints)
- **Tenant Isolation**: Enforced via `X-Tenant-ID` header and tenant validation

### Scheduled Export Flow (Prefect Worker → Hub API)

**Execution Model**: Prefect worker → Hub API (Internal Worker API)

```
User (UI/API)
  ↓
API Service (Public API)
  ↓
Create Scheduled Export → API Service
  ↓
Prefect Integration Service
  ↓
Sync to Prefect Deployment → Prefect Server
  ↓
Prefect Scheduler (Cron)
  ↓
Prefect Worker (scheduled_export_full_flow)
  ↓
GET /api/v1/scheduled-exports/internal/config/{id}/ → Hub API (credentials masked)
  ↓
POST /api/v1/scheduled-exports/internal/runs/ → Hub API (create run)
  ↓
For each item in source scope:
  POST /api/v1/scheduled-exports/internal/process-export/ → Hub API
    ↓
    Hub API → Validates run and tenant
    Hub API → Applies business rules (scope, access)
    Hub API → Prepares payload or signed URL
    Hub API → Returns upload instructions
  ↓
Prefect Worker → Uploads to destination (S3/GCS/Azure Blob)
  ↓
PATCH /api/v1/scheduled-exports/internal/runs/{id}/ → Hub API (update status)
  ↓
Hub API → Update ScheduledExport (next_run_at, status)
Hub API → Cost Tracking
Hub API → DLQ Sync
Hub API → Notifications
Hub API → Domain Events
```

**Key Points**:
- **Prefect Worker**: Executes `scheduled_export_full_flow` (HTTP-only, no Django)
- **Hub API**: Provides internal endpoints (`/api/v1/scheduled-exports/internal/*`) for worker communication
- **Authentication**: Worker API key (`HUB_WORKER_API_KEY` or API key with scope `scheduled_export:internal`)
- **Rate Limiting**: No rate limit (internal worker endpoints)
- **Tenant Isolation**: Enforced via `X-Tenant-ID` header and tenant validation
- **Destination Connectors**: S3, GCS, Azure Blob connectors implemented in Prefect worker
- **Hub as Source of Truth**: Configuration and state stored in Hub; Prefect executes exports

---

### Search Service (`search-service`)

**Technology**: FastAPI, PostgreSQL full-text search or Elasticsearch
**Port**: 8085 (default)
**Status**: Post-MVP

**Responsibilities**:
- Full-text search indexing
- Search query execution
- Search ranking
- Search suggestions
- Search analytics

**Key Endpoints**:
- `POST /search` - Execute search
- `POST /suggest` - Get search suggestions
- `GET /analytics` - Get search analytics
- `GET /health` - Health check

**Dependencies**:
- PostgreSQL (full-text search) or Elasticsearch
- PostgreSQL (asset/contract metadata)

**Scaling**: Horizontal scaling

---

### Observability Service (`observability-service`)

**Technology**: FastAPI, Time series database
**Port**: 8086 (default)
**Status**: Post-MVP

**Responsibilities**:
- Data freshness monitoring
- Data volume tracking
- Schema drift detection
- Pipeline monitoring
- SLA tracking
- Incident management

**Key Endpoints**:
- `GET /freshness` - Get freshness metrics
- `GET /volume` - Get volume metrics
- `GET /schema-drift` - Get schema drift alerts
- `GET /slas` - Get SLA status
- `GET /health` - Health check

**Dependencies**:
- Time series database (Prometheus or InfluxDB)
- PostgreSQL (asset/contract metadata)

**Scaling**: Horizontal scaling

---

### Webhook Service (`webhook-service`)

**Technology**: FastAPI, HTTP client libraries
**Port**: 8087 (default)
**Status**: Post-MVP

**Responsibilities**:
- Webhook registration
- Event subscription
- Webhook delivery with retry logic
- Webhook authentication
- Webhook payload customization

**Key Endpoints**:
- `POST /webhooks` - Register webhook
- `GET /webhooks` - List webhooks
- `POST /events` - Trigger webhook delivery
- `GET /health` - Health check

**Dependencies**:
- PostgreSQL (webhook configuration)
- External webhook endpoints

**Scaling**: Horizontal scaling

---

## Infrastructure Services

### PostgreSQL

**Technology**: PostgreSQL 16.x
**Port**: 5432 (default)
**Status**: MVP

**Responsibilities**:
- Primary database for all services
- JSONB storage for contracts
- Full-text search (tsvector, GIN indexes)
- Transaction management
- Data persistence

**Key Features**:
- Multi-tenant data isolation
- JSONB indexes for contract queries
- Full-text search capabilities
- ACID transactions

**Scaling**: Vertical and horizontal scaling (read replicas)

---

### Redis

**Technology**: Redis 7.x
**Port**: 6379 (default)
**Status**: MVP

**Responsibilities**:
- Job queue (RQ)
- Caching
- Session storage
- Rate limiting counters

**Key Features**:
- Job queue persistence
- Pub/sub for events (future)
- Caching layer

**Scaling**: Redis Cluster for high availability

---

### MinIO

**Technology**: MinIO (S3-compatible)
**Port**: 9000 (API), 9001 (Console)
**Status**: MVP

**Responsibilities**:
- Object storage for data files
- S3-compatible API
- File upload/download
- Pre-signed URLs

**Key Features**:
- S3-compatible API
- Multi-tenant bucket isolation
- File versioning
- Lifecycle policies

**Scaling**: MinIO cluster for high availability

---

### Apache Jena Fuseki

**Technology**: Apache Jena Fuseki
**Port**: 3030 (default)
**Status**: MVP

**Responsibilities**:
- RDF triple store
- SPARQL query execution
- RDF data persistence
- Ontology storage

**Key Features**:
- SPARQL 1.1 support
- RDF data management
- Query optimization

**Scaling**: Fuseki cluster for high availability

---

### Prometheus

**Technology**: Prometheus
**Port**: 9090 (default)
**Status**: MVP

**Responsibilities**:
- Metrics collection
- Metrics storage
- Alert rule evaluation
- Service discovery

**Key Features**:
- Time series database
- PromQL query language
- Alert rule evaluation
- Service discovery

**Scaling**: Prometheus federation for large scale

---

### Grafana

**Technology**: Grafana
**Port**: 3000 (default)
**Status**: MVP

**Responsibilities**:
- Metrics visualization
- Dashboard creation
- Alert visualization
- Data source integration

**Key Features**:
- Dashboard management
- Alert visualization
- Multiple data sources
- User management

**Scaling**: Horizontal scaling

---

### Jaeger

**Technology**: Jaeger
**Port**: 16686 (UI), 14268 (HTTP), 6831 (UDP)
**Status**: MVP

**Responsibilities**:
- Distributed tracing
- Trace collection
- Trace visualization
- Performance analysis

**Key Features**:
- OpenTelemetry integration
- Trace visualization
- Performance analysis
- Service dependency graphs

**Scaling**: Jaeger cluster for high availability

---

### Alertmanager

**Technology**: Alertmanager
**Port**: 9093 (default)
**Status**: MVP

**Responsibilities**:
- Alert management
- Alert routing
- Alert silencing
- Notification delivery

**Key Features**:
- Alert routing rules
- Notification channels (email, Slack, PagerDuty)
- Alert grouping
- Alert inhibition

**Scaling**: Horizontal scaling

---

## Service Communication Patterns

### Synchronous Communication

**Pattern**: REST API calls
**Use Cases**:
- API Service → DataContract Service (contract validation)
- API Service → DQ Service (DQ checks)
- API Service → Compliance Service (compliance scans)
- API Service → Semantic Service (RDF mapping)
- Worker Service → External services (job execution)
- ODPSService → DataContract Service (ODCS validation)
- ODPSService → Semantic Service (RDF mapping)
- MarketplaceIntegrationService → Marketplace APIs (external marketplace operations)

**Technology**: HTTP/REST, httpx (Python)

---

### Asynchronous Communication

**Pattern**: Job Queue (Redis/RQ)
**Use Cases**:
- API Service → Worker Service (background jobs)
- Worker Service → External services (long-running operations)

**Technology**: Redis Queue (RQ), Redis pub/sub (future)

---

### Event-Driven Communication ✅ (Implemented - Phase 9.7.1)

**Pattern**: Event Bus (Redis Pub/Sub + PostgreSQL)
**Status**: ✅ Implemented
**Use Cases**:
- Contract created → Semantic mapping
- Asset updated → Search index update
- Compliance scan completed → Notifications
- Data mesh domain updated → Topology updates
- Virtual dataset created → Query optimization

**Technology**: Redis Pub/Sub (real-time delivery) + PostgreSQL (persistence, replay, audit)

**Architecture**: See [Event Bus Architecture](#event-bus-architecture) section below

---

## Data Flow Diagrams

### Asset Onboarding Flow (Data-First)

```
User (UI/API)
  ↓
API Service
  ↓
File Upload → MinIO
  ↓
Schema Inference → API Service
  ↓
Compliance Job → Worker Service → Compliance Service → MinIO
  ↓
DQ Job → Worker Service → DQ Service → MinIO
  ↓
Contract Creation → API Service
  ↓
Contract Validation → Worker Service → DataContract Service
  ↓
Semantic Mapping → Worker Service → Semantic Service → Fuseki
  ↓
Asset Activated → API Service
```

### Contract Validation Flow

```
User (UI/API)
  ↓
API Service
  ↓
Contract Validation Job → Worker Service
  ↓
DataContract Service
  ↓
Validation Result → Worker Service → API Service
  ↓
User (UI/API)
```

### Marketplace Purchase Flow

```
Data Consumer (UI)
  ↓
API Service
  ↓
Order Creation → API Service
  ↓
Entitlement Creation → API Service
  ↓
Asset Access → API Service → MinIO
  ↓
Data Consumer (UI)
```

### Scheduled Ingestion Flow (Prefect Worker → Hub API)

**Execution Model**: Prefect worker → Hub API (Internal Worker API)

```
User (UI/API)
  ↓
API Service (Public API)
  ↓
Create Scheduled Ingestion → API Service
  ↓
Prefect Integration Service
  ↓
Sync to Prefect Deployment → Prefect Server
  ↓
Prefect Scheduler (Cron)
  ↓
Prefect Worker (scheduled_ingestion_full_flow)
  ↓
GET /api/v1/scheduled-ingestions/internal/config/{id}/ → Hub API (credentials masked)
  ↓
POST /api/v1/scheduled-ingestions/internal/runs/ → Hub API (create run)
  ↓
Discover Files (Source Connector: S3/GCS/Azure/HTTP/etc.)
  ↓
Filter Files (incremental, pattern matching)
  ↓
For each file:
  POST /api/v1/scheduled-ingestions/internal/process-file/ → Hub API
    ↓
    Hub API → Files Service (create file)
    Hub API → Datasets Service (create dataset)
    Hub API → DQ Service (optional DQ check)
    Hub API → Search Service (index)
    Hub API → Update incremental state
  ↓
PATCH /api/v1/scheduled-ingestions/internal/runs/{id}/ → Hub API (update status)
  ↓
Hub API → Update ScheduledIngestion (next_run_at, status)
Hub API → Cost Tracking
Hub API → DLQ Sync
Hub API → Notifications
Hub API → Domain Events
```

**Key Points**:
- **Prefect Worker**: Executes `scheduled_ingestion_full_flow` (HTTP-only, no Django)
- **Hub API**: Provides internal endpoints (`/api/v1/scheduled-ingestions/internal/*`) for worker communication
- **Authentication**: Worker API key (`HUB_WORKER_API_KEY` or API key with scope `scheduled_ingestion:internal`)

**Scheduled Export Execution Model**:

- **Prefect Worker**: Executes `scheduled_export_full_flow` (HTTP-only, no Django)
- **Hub API**: Provides internal endpoints (`/api/v1/scheduled-exports/internal/*`) for:
  - Run lifecycle management (create/update run)
  - Export processing (process-export for individual items)
  - Configuration retrieval (config endpoint with masked credentials)
- **Authentication**: Worker API key (`HUB_WORKER_API_KEY` or API key with scope `scheduled_export:internal`)
- **Rate Limiting**: No rate limit (internal worker endpoints)
- **Destination Connectors**: S3, GCS, Azure Blob connectors in Prefect worker
- **Hub as Source of Truth**: Hub stores configuration and state; Prefect worker executes exports
- **Rate Limiting**: No rate limit (internal worker endpoints)
- **Tenant Isolation**: Enforced via `X-Tenant-ID` header and tenant validation

### Scheduled Export Flow (Prefect Worker → Hub API)

**Execution Model**: Prefect worker → Hub API (Internal Worker API)

```
User (UI/API)
  ↓
API Service (Public API)
  ↓
Create Scheduled Export → API Service
  ↓
Prefect Integration Service
  ↓
Sync to Prefect Deployment → Prefect Server
  ↓
Prefect Scheduler (Cron)
  ↓
Prefect Worker (scheduled_export_full_flow)
  ↓
GET /api/v1/scheduled-exports/internal/config/{id}/ → Hub API (credentials masked)
  ↓
POST /api/v1/scheduled-exports/internal/runs/ → Hub API (create run)
  ↓
For each item in source scope:
  POST /api/v1/scheduled-exports/internal/process-export/ → Hub API
    ↓
    Hub API → Validates run and tenant
    Hub API → Applies business rules (scope, access)
    Hub API → Prepares payload or signed URL
    Hub API → Returns upload instructions
  ↓
Prefect Worker → Uploads to destination (S3/GCS/Azure Blob)
  ↓
PATCH /api/v1/scheduled-exports/internal/runs/{id}/ → Hub API (update status)
  ↓
Hub API → Update ScheduledExport (next_run_at, status)
Hub API → Cost Tracking
Hub API → DLQ Sync
Hub API → Notifications
Hub API → Domain Events
```

**Key Points**:
- **Prefect Worker**: Executes `scheduled_export_full_flow` (HTTP-only, no Django)
- **Hub API**: Provides internal endpoints (`/api/v1/scheduled-exports/internal/*`) for worker communication
- **Authentication**: Worker API key (`HUB_WORKER_API_KEY` or API key with scope `scheduled_export:internal`)
- **Rate Limiting**: No rate limit (internal worker endpoints)
- **Tenant Isolation**: Enforced via `X-Tenant-ID` header and tenant validation
- **Destination Connectors**: S3, GCS, Azure Blob connectors implemented in Prefect worker
- **Hub as Source of Truth**: Configuration and state stored in Hub; Prefect executes exports

---

## Service Layer Coordination

### Service Layer Pattern

All business logic is coordinated through service layer classes that extend `BaseService`. This pattern ensures consistent error handling, metrics collection, tenant scoping, and resource management across all services.

#### DataMeshService ✅ (Implemented - Phase 9.5.2)
- **Location**: `hub/apps/mesh/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Coordinate domain operations
  - Manage domain-to-asset relationships
  - Handle federated governance
  - Coordinate mesh topology updates
  - Publish data mesh events (domain.created, domain.updated, etc.)
- **Integration**:
  - Extends `BaseService` and `DataMeshEventPublisher`
  - Integrates with DataMeshWorkflow, AssetUpdateWorkflow
  - Uses Event Bus for asynchronous coordination
- **Key Methods**:
  - `create_domain()` - Create data mesh domain
  - `update_domain()` - Update domain configuration
  - `transfer_ownership()` - Transfer asset ownership between domains

#### VirtualizationService ✅ (Implemented - Phase 9.5.3)
- **Location**: `hub/apps/virtualization/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Coordinate virtual dataset operations
  - Manage query execution across multiple sources
  - Handle schema alignment and validation
  - Coordinate virtualization events
  - Publish virtualization events (dataset.created, query.executed, etc.)
- **Integration**:
  - Extends `BaseService` and `VirtualizationEventPublisher`
  - Integrates with VirtualizationWorkflow, AssetUpdateWorkflow
  - Uses Event Bus for asynchronous coordination
- **Key Methods**:
  - `create_virtual_dataset()` - Create virtual dataset
  - `execute_query()` - Execute query across sources
  - `validate_schema_alignment()` - Validate schema compatibility

#### ContractService ✅ (Implemented - MVP)
- **Location**: `hub/apps/contracts/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Contract creation and validation
  - Contract lifecycle management
  - Contract-to-asset relationships
  - Contract versioning
- **Integration**: Extends `BaseService`, integrates with ContractCreationWorkflow

#### AssetService ✅ (Implemented - MVP)
- **Location**: `hub/apps/assets/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Asset creation and management
  - Asset lifecycle coordination
  - Asset-to-contract relationships
  - Asset activation workflows
- **Integration**: Extends `BaseService`, integrates with AssetCreationWorkflow

#### MarketplaceService ✅ (Implemented - MVP)
- **Location**: `hub/apps/marketplace/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Coordinate publishing with quality
  - Manage purchase workflows
  - Handle pricing model validation
  - Coordinate marketplace events with asset updates
- **Integration**: Extends `BaseService`, integrates with MarketplacePublishingWorkflow

#### ODPSService ✅ (Implemented - ODPS Integration)
- **Location**: `hub/apps/contracts/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - ODPS contract creation and normalization
  - ODPS linking to ODCS contracts
  - ODPS export and generation
  - ODPS workflow orchestration
  - Publish ODPS events (odps.created, odps.normalized, odps.linked, etc.)
- **Integration**:
  - Extends `BaseService` and `ODPSEventPublisher`
  - Integrates with ProductCreationWorkflow for multi-step operations
  - Uses ODPSNormalizer for document normalization
  - Uses ODPSBusinessRules for validation
  - Uses Event Bus for asynchronous coordination
- **Key Methods**:
  - `create_odps()` - Create ODPS contract with normalization
  - `link_odps_to_odcs()` - Link ODPS to existing ODCS contract
  - `export_odps()` - Export HubContract to ODPS format
  - `generate_odps_from_hubcontract()` - Generate ODPS from HubContract

#### MarketplaceIntegrationService ✅ (Implemented - Marketplace Integration Framework)
- **Location**: `hub/apps/integrations/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Marketplace connection management (CRUD operations)
  - Connection testing and validation
  - Bidirectional asset synchronization (PUSH and PULL)
  - Sync job management and tracking
  - Asset mapping management
  - Publish marketplace integration events (marketplace.connection.created, marketplace.sync.completed, etc.)
- **Integration**:
  - Extends `BaseService`, `IntegrationEventPublisher`, and `MarketplaceEventPublisher`
  - Integrates with MarketplaceSyncWorkflow for orchestration
  - Uses MarketplaceConnectorFactory for connector instantiation
  - Uses MarketplaceBusinessRules for validation
  - Uses Event Bus for asynchronous coordination
- **Key Methods**:
  - `create_connection()` - Create marketplace connection
  - `test_connection()` - Test marketplace connection and credentials
  - `sync_assets_to_marketplace()` - PUSH sync (Hub → Marketplace)
  - `sync_assets_from_marketplace()` - PULL sync (Marketplace → Hub)
  - `create_sync_job()` - Create scheduled sync job
  - `get_sync_status()` - Get sync job status and progress

#### AIService
- **Location**: `hub/apps/ai/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Coordinate ML operations with workflows
  - Manage ML model lifecycle
  - Handle ML result validation
  - Coordinate schema matching with contract creation
- **Integration**: Integrates with AssetCreationWorkflow, ContractCreationWorkflow

#### SocialService
- **Location**: `hub/apps/social/services.py`
- **Status**: ✅ Implemented
- **Responsibilities**:
  - Coordinate ratings/reviews with asset updates
  - Manage review moderation workflows
  - Handle social feature events
  - Coordinate activity feeds with asset operations
- **Integration**: Integrates with SocialFeatureWorkflow, AssetUpdateWorkflow

### Service Communication Patterns

Services communicate through:
1. **Direct Service Calls**: For synchronous coordination
2. **Event Bus**: For asynchronous coordination
3. **Workflow Engine**: For multi-step orchestration

### Service Dependencies

```
AIService
  ├── ContractService (for schema matching)
  ├── AssetService (for asset updates)
  ├── WorkflowEngine (for ML orchestration)
  └── EventBus (for event publishing)

SocialService
  ├── AssetService (for quality score updates)
  ├── WorkflowEngine (for moderation orchestration)
  └── EventBus (for event publishing)

MarketplaceService
  ├── AssetService (for asset updates)
  ├── WorkflowEngine (for publishing orchestration)
  └── EventBus (for event publishing)

DataMeshService
  ├── AssetService (for ownership updates)
  ├── GovernanceService (for policy application)
  ├── WorkflowEngine (for domain orchestration)
  └── EventBus (for event publishing)

ODPSService
  ├── ContractService (for contract operations)
  ├── ProductCreationWorkflow (for multi-step orchestration)
  ├── ODPSNormalizer (for document normalization)
  ├── ODPSBusinessRules (for validation)
  ├── WorkflowEngine (for workflow orchestration)
  └── EventBus (for event publishing)

MarketplaceIntegrationService
  ├── AssetService (for asset operations)
  ├── ContractService (for contract operations)
  ├── MarketplaceSyncWorkflow (for sync orchestration)
  ├── MarketplaceConnectorFactory (for connector instantiation)
  ├── MarketplaceBusinessRules (for validation)
  ├── WorkflowEngine (for workflow orchestration)
  └── EventBus (for event publishing)
```

---

## Deployment Architecture

### Development Environment

- Docker Compose for local development
- All services in containers
- Single-node deployment
- Development databases

### Staging Environment

- Kubernetes cluster
- Multi-node deployment
- Production-like configuration
- Staging databases

### Production Environment

- Kubernetes cluster (multi-region future)
- High availability deployment
- Auto-scaling
- Production databases with backups
- CDN for static assets (future)

---

## Service Dependencies

### Dependency Graph

```
API Service
  ├── PostgreSQL
  ├── Redis
  ├── MinIO
  ├── DataContract Service
  ├── DQ Service
  ├── Compliance Service
  └── Semantic Service

Worker Service
  ├── Redis
  ├── PostgreSQL
  ├── MinIO
  ├── DataContract Service
  ├── DQ Service
  ├── Compliance Service
  └── Semantic Service

Semantic Service
  ├── Apache Jena Fuseki
  └── PostgreSQL

DataContract Service
  └── (standalone)

DQ Service
  └── MinIO

Compliance Service
  └── MinIO
```

### Service Health Checks

All services expose health check endpoints:
- `/health` - Basic health check
- `/health/ready` - Readiness check
- `/health/live` - Liveness check

### Service Discovery

- **Development**: Docker Compose service names
- **Kubernetes**: Kubernetes service names and DNS
- **Future**: Service mesh (Istio, Linkerd)

---

## Event Bus Architecture ✅ (Implemented - Phase 9.7.1)

### Overview

The Event Bus provides event-driven communication infrastructure for the Data Interoperability Hub. It enables decoupled, asynchronous communication between services using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence, replay, and audit.

### Architecture Components

1. **Event Bus** (`hub/apps/core/events/bus.py`)
   - Redis Pub/Sub for real-time event delivery
   - PostgreSQL for event persistence
   - Dead letter queue for failed events
   - Event replay functionality

2. **Event Schema** (`hub/apps/core/events/schema.py`)
   - JSON Schema validation
   - Event building utilities
   - Type-specific schemas
   - Schema versioning support

3. **Event Publishers** (`hub/apps/core/events/publisher.py`)
   - Convenience classes for publishing events
   - Decorator support for automatic event publishing
   - Service-specific publishers (DataMeshEventPublisher, VirtualizationEventPublisher, etc.)

4. **Event Subscribers** (`hub/apps/core/events/subscriber.py`)
   - Subscription management
   - Handler wrapping with error handling
   - Transaction management
   - Pattern matching for event types

5. **Event Models** (`hub/apps/core/events/models.py`)
   - `Event`: Event persistence
   - `DeadLetterQueue`: Failed event storage
   - `EventSubscription`: Subscription tracking

### Event Schema

Events follow a standardized schema:

```json
{
  "event_id": "uuid",
  "event_type": "contract.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "hub",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["tag1", "tag2"]
  }
}
```

**Event Type Format**: `domain.entity.action` (e.g., `contract.created`, `asset.activated`, `mesh.domain.created`)

### Performance Characteristics

- **Throughput**: ~1,500-2,000 events/sec
- **Latency**: <10ms (Pub/Sub only), <150ms (with persistence)
- **Persistence**: 100% of events persisted to PostgreSQL
- **Reliability**: Dead letter queue for failed events
- **Replay**: Event replay functionality for recovery

### Integration Points

- **DataMeshService**: Publishes `mesh.domain.*` events
- **VirtualizationService**: Publishes `virtualization.dataset.*` and `virtualization.query.*` events
- **ContractService**: Publishes `contract.*` events
- **AssetService**: Publishes `asset.*` events
- **WebhookService**: Subscribes to events for webhook delivery

### Documentation

- **Full Documentation**: `docs/EVENT_BUS.md`
- **Architecture Decision**: `docs/EVENT_BUS_ARCHITECTURE_DECISION.md`
- **Performance Analysis**: `docs/EVENT_BUS_PERFORMANCE_ANALYSIS.md`

---

## ODPS Workflow Orchestration ✅ (Implemented - ODPS Integration)

### Overview

ODPS operations are orchestrated through the ProductCreationWorkflow, which manages the complete ODPS product creation process with proper error handling, retry logic, and compensation.

### ProductCreationWorkflow

**Location**: `hub/apps/orchestration/workflows/product_creation.py`
**Status**: ✅ Implemented
**Workflow Name**: `product_creation`

**Workflow Steps**:
1. **parse_odps**: Parse ODPS document, validate schema, detect version
2. **resolve_refs**: Resolve `$ref` references (internal, local, external)
3. **extract_contract**: Extract ODCS from `product.contract` (required)
4. **validate_odcs**: Validate extracted ODCS contract
5. **normalize_odcs**: Normalize ODCS → HubContract (technical)
6. **normalize_odps**: Normalize ODPS → HubContract (marketplace)
7. **create_odcs_contract**: Create ODCS contract record
8. **create_odps_contract**: Create ODPS contract record
9. **link_contracts**: Establish bidirectional link (ODPS ↔ ODCS)
10. **index_for_search**: Index for search (ODPS product + ODCS technical)
11. **semantic_mapping**: Map ODPS to RDF (async job)

**Compensation Logic**: Each step has compensation handlers for rollback on failure.

**Integration**:
- Uses WorkflowEngine for orchestration
- Publishes workflow events (`odps.workflow.started`, `odps.workflow.completed`, `odps.workflow.failed`)
- Publishes progress events (`odps.workflow.progress`, `odps.creation.progress`)
- Integrates with ODPSService for business logic
- Uses ODPSNormalizer for normalization
- Uses ODPSBusinessRules for validation

### ODPS Event Publishing Patterns

**ODPSEventPublisher** (`hub/apps/core/events/service_publishers.py`):
- **Lifecycle Events**: `odps.created`, `odps.updated`, `odps.deleted`
- **Processing Events**: `odps.normalized`, `odps.ref.resolved`, `odps.ref.failed`
- **Linking Events**: `odps.linked`, `odps.unlinked`
- **Export Events**: `odps.export.started`, `odps.export.completed`, `odps.export.failed`
- **Workflow Events**: `odps.workflow.started`, `odps.workflow.completed`, `odps.workflow.failed`
- **Progress Events**: `odps.creation.progress`, `odps.normalization.progress`, `odps.ref.progress`

**Event Subscribers**:
- **SearchService**: Indexes ODPS contracts for search
- **NotificationService**: Sends creation and completion notifications
- **AuditService**: Logs ODPS operations for compliance
- **WebhookService**: Delivers webhooks for ODPS events
- **SemanticService**: Triggers RDF mapping for ODPS contracts

---

## Marketplace Integration Workflow Orchestration ✅ (Implemented - Marketplace Integration Framework)

### Overview

Marketplace integration operations are orchestrated through the MarketplaceSyncWorkflow, which manages bidirectional asset synchronization between the Hub and external marketplaces.

### MarketplaceSyncWorkflow

**Location**: `hub/apps/orchestration/workflows/marketplace_sync.py`
**Status**: ✅ Implemented
**Workflow Name**: `marketplace_sync`

**PUSH Sync Steps** (Hub → Marketplace):
1. **validate_assets**: Validate assets are ACTIVE and have valid contracts
2. **get_connector**: Get marketplace connector from factory
3. **transform_assets**: Transform HubContract to marketplace format (ODPS)
4. **publish_to_marketplace**: Publish listings to marketplace via connector
5. **create_mappings**: Create MarketplaceMapping records linking Hub assets to listings

**PULL Sync Steps** (Marketplace → Hub):
1. **get_connector**: Get marketplace connector from factory
2. **discover_listings**: Discover marketplace listings via connector
3. **transform_listings**: Transform marketplace format to HubContract
4. **create_assets**: Create assets using AssetCreationWorkflow
5. **create_mappings**: Create MarketplaceMapping records linking Hub assets to listings

**Compensation Logic**: Each step has compensation handlers for rollback on failure.

**Integration**:
- Uses WorkflowEngine for orchestration
- Publishes marketplace events (`marketplace.sync.started`, `marketplace.sync.completed`, `marketplace.sync.failed`)
- Publishes progress events (`marketplace.sync.progress`)
- Integrates with MarketplaceIntegrationService for business logic
- Uses MarketplaceConnectorFactory for connector instantiation
- Uses MarketplaceBusinessRules for validation

### Marketplace Integration Event Publishing Patterns

**MarketplaceEventPublisher** (`hub/apps/integrations/event_publishers.py`):
- **Connection Events**: `marketplace.connection.created`, `marketplace.connection.updated`, `marketplace.connection.deleted`, `marketplace.connection.tested`
- **Sync Events**: `marketplace.sync.started`, `marketplace.sync.completed`, `marketplace.sync.failed`, `marketplace.sync.progress`
- **Mapping Events**: `marketplace.mapping.created`, `marketplace.mapping.updated`, `marketplace.mapping.deleted`

**IntegrationEventPublisher** (`hub/apps/core/events/service_publishers.py`):
- **Integration Events**: `integration.connection.created`, `integration.connection.updated`, `integration.sync.completed`

**Event Subscribers**:
- **NotificationService**: Sends sync completion and failure notifications
- **AuditService**: Logs marketplace operations for compliance
- **WebhookService**: Delivers webhooks for marketplace events
- **SearchService**: Updates search index when assets are synced

### Marketplace Connector Factory Pattern

**MarketplaceConnectorFactory** (`hub/apps/integrations/factory.py`):
- **Purpose**: Creates marketplace-specific connectors based on marketplace type
- **Supported Types**: CKAN, Snowflake, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks, etc.
- **Connector Interface**: Standardized interface for all connectors
- **Connection Testing**: Validates credentials and connectivity

**Connector Methods**:
- `publish_listing()` - Publish asset listing to marketplace
- `discover_listings()` - Discover listings from marketplace
- `update_listing()` - Update existing listing
- `delete_listing()` - Delete listing from marketplace
- `test_connection()` - Test marketplace connection

**Integration**:
- Used by MarketplaceIntegrationService for connector instantiation
- Connectors implement standardized interface for consistency
- Factory pattern enables easy addition of new marketplace types

### Marketplace Job Queue Integration

**Scheduled Sync Jobs**:
- **ScheduledMarketplaceSync**: Model for scheduled sync jobs
- **Schedule Types**: ONCE, DAILY, WEEKLY, MONTHLY
- **Job Execution**: Jobs are executed via Worker Service
- **Status Tracking**: Tracks sync status and progress

**Integration**:
- Uses Redis Queue (RQ) for job execution
- Jobs trigger MarketplaceSyncWorkflow
- Progress tracked via workflow events
- Status stored in ScheduledMarketplaceSyncStatus model

---

## Redis Instance Separation ✅ (Implemented - Phase 9.7.1.3)

### Overview

Redis has been separated into four dedicated instances to improve isolation, performance, scalability, and operational management. This separation addresses resource contention and enables independent scaling of different workloads.

### Four Redis Instances

#### 1. Redis Cache Instance
- **Purpose**: Response caching, contract caching, lineage caching
- **Port**: 6379 (default)
- **Memory**: 2-4 GB (configurable)
- **Persistence**: Optional (AOF recommended for cache warming)
- **Characteristics**:
  - High read-to-write ratio (90%+ reads)
  - Short TTLs (5 minutes to 1 hour)
  - Cache eviction policies: LRU, LFU
- **Use Cases**:
  - HTTP response caching
  - Contract data caching
  - Lineage resolution caching
  - Dataset/asset query result caching

#### 2. Redis Queue Instance
- **Purpose**: Job queues (RQ)
- **Port**: 6380
- **Memory**: 1-2 GB (configurable)
- **Persistence**: Required (AOF recommended)
- **Characteristics**:
  - High write-to-read ratio (job enqueueing)
  - Long-lived data (job results, metadata)
  - Persistence required for job reliability
- **Use Cases**:
  - Priority queues: `job_critical`, `job_default`, `job_low`
  - Job result storage
  - Job metadata and state
  - Worker coordination

#### 3. Redis Events Instance
- **Purpose**: Event bus (Pub/Sub, Streams)
- **Port**: 6381
- **Memory**: 1-2 GB (configurable)
- **Persistence**: Optional (AOF for Streams, not needed for Pub/Sub)
- **Characteristics**:
  - High throughput (1,500-2,000 events/sec)
  - Low latency requirements (<10ms)
  - Fire-and-forget (Pub/Sub) or persistent (Streams)
- **Use Cases**:
  - Event publishing (Pub/Sub channels)
  - Event subscription management
  - Event deduplication keys
  - Message acknowledgment tracking

#### 4. Redis Channels Instance
- **Purpose**: WebSocket channels (Django Channels)
- **Port**: 6382
- **Memory**: 512 MB - 1 GB (configurable)
- **Persistence**: Not required
- **Characteristics**:
  - Real-time messaging
  - Low latency (<50ms)
  - Ephemeral data (messages expire quickly)
- **Use Cases**:
  - WebSocket channel groups
  - Real-time message delivery
  - Channel layer coordination
  - Presence tracking

### Benefits

1. **Isolation**: Prevents resource contention between workloads
2. **Performance**: Optimized configurations per workload type
3. **Scalability**: Independent scaling of each workload
4. **Operational Management**: Granular monitoring, tuning, and troubleshooting

### Configuration

Environment variables for each instance:
- `REDIS_CACHE_URL` - Cache instance
- `REDIS_QUEUE_URL` - Queue instance
- `REDIS_EVENTS_URL` - Events instance
- `REDIS_CHANNELS_URL` - Channels instance

### Documentation

- **Full Design**: `docs/REDIS_INSTANCE_SEPARATION_DESIGN.md`
- **Architecture Review**: `docs/REDIS_INSTANCE_SEPARATION_ARCHITECTURE_REVIEW.md`
- **Design Review**: `docs/REDIS_INSTANCE_SEPARATION_DESIGN_REVIEW.md`

---

## Business Rules Framework ✅ (Implemented - Phase 9.7.2)

### Overview

The Business Rules Framework provides a standardized approach to validation and business logic enforcement across all services. All business rules classes follow consistent patterns for validation, error handling, and result reporting.

### Framework Components

1. **Base Class** (`hub/apps/core/business_rules/base.py`)
   - `BusinessRules` abstract base class
   - `ValidationResult` dataclass (standardized result structure)
   - Common validation patterns
   - Error handling utilities

2. **Common Utilities** (`hub/apps/core/business_rules/utils.py`)
   - Shared validation utilities
   - Tenant ID validation
   - User permission checking
   - Cross-tenant access validation
   - Schema structure validation

3. **Registry** (`hub/apps/core/business_rules/registry.py`)
   - Business rules registration
   - Rule discovery and loading
   - Rule execution coordination

### Business Rules Implementations

#### Contract Business Rules
- **ODPSBusinessRules** (`hub/apps/contracts/business_rules.py`)
  - ODPS document structure validation
  - ODPS version validation
  - ODPS-ODCS linking validation
- **ODPSLinkingRules** - Link validation, circular reference detection
- **ODPSExportRules** - Export format validation, fidelity validation

  - Cross-tenant operation validation

#### Data Mesh Business Rules
- **DataMeshBusinessRules** (`hub/apps/mesh/business_rules.py`)
  - Domain structure validation
  - Ownership transfer validation
  - Boundaries validation
  - Policy conflict detection
- **PolicyBusinessRules** - Policy application validation, compliance checking
- **TopologyBusinessRules** - Relationship calculation, health metrics

#### Virtualization Business Rules
- **VirtualizationBusinessRules** (`hub/apps/virtualization/business_rules.py`)
  - Query syntax validation
  - Schema alignment validation
  - Source compatibility validation
  - Cross-source compatibility validation
- **QueryExecutionBusinessRules** - Query optimization, execution mode selection
- **ResultBusinessRules** - Result caching validation, pagination validation

### ValidationResult Pattern

All business rules return a standardized `ValidationResult`:

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]
```

### Common Patterns

1. **Initialization**: All rules accept `tenant_id` and `user_id`
2. **Validation Methods**: Return `ValidationResult`, support `raise_on_error` parameter
3. **Error Handling**: Consistent use of `ValidationError` from `hub.apps.core.services.base`
4. **Error Messages**: Comprehensive context in error messages and `details` dictionary

### Integration

- Business rules are integrated into service layer classes
- Rules are executed during service operations (create, update, delete)
- Rules can be registered and discovered via the registry
- Rules support dependency injection and testing

### Documentation

- **Framework Review**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`
- **Integration Guide**: `docs/BUSINESS_LOGIC_INTEGRATION.md`

---

**Last Updated**: 2026-03-22
**Version**: 2.0.0


---

## 3. Inter-Service Communication


### Service Integration Patterns


## Overview

This document describes the standard integration patterns used in the Data Interoperability Hub for service-to-service communication. These patterns ensure reliable, scalable, and maintainable inter-service coordination.

## Table of Contents

1. [Pattern 1: Direct Service Calls (Synchronous)](#pattern-1-direct-service-calls-synchronous)
2. [Pattern 2: Event-Driven Coordination (Asynchronous)](#pattern-2-event-driven-coordination-asynchronous)
3. [Pattern 3: Workflow Orchestration (Multi-Step)](#pattern-3-workflow-orchestration-multi-step)
4. [Pattern Selection Criteria](#pattern-selection-criteria)
5. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Pattern 1: Direct Service Calls (Synchronous)

### When to Use

- **Simple operations** that require immediate response
- **Real-time validation** or data retrieval needed
- **Low latency requirements** (< 1 second response time)
- **Strong consistency** required (cannot tolerate eventual consistency)
- **Simple request-response** interactions without complex state management

### Pattern Architecture

```
Service A → HTTP/REST → Service B
         ← Response ←
```

### Implementation

#### Service Client Pattern

All service clients follow a consistent pattern with:
- HTTP client (httpx) with connection pooling
- Retry logic with exponential backoff
- Circuit breaker for fault tolerance
- Distributed tracing support
- Health check capabilities

#### Example: ComplianceServiceClient

**Location**: `hub/apps/compliance/service_client.py`

```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker
from hub.apps.core.redis import get_redis_client
import httpx
import time

class ComplianceServiceClient:
    """Client for interacting with the Compliance service."""

    def __init__(self):
        self.base_url = getattr(settings, 'COMPLIANCE_SERVICE_URL', 'http://compliance-service:8082')
        self.timeout = getattr(settings, 'COMPLIANCE_SERVICE_TIMEOUT', 1800)
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="compliance-service",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make HTTP requests with retry logic"""
        # Add trace headers for distributed tracing
        from hub.apps.api.middleware.trace_propagation import get_trace_headers
        trace_headers = get_trace_headers()
        if trace_headers:
            kwargs.setdefault('headers', {}).update(trace_headers)

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries + 1):
            try:
                # Use circuit breaker to protect against cascading failures
                response = self._circuit_breaker.call(
                    lambda: self.client.request(method, endpoint, **kwargs)
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                # Retry on 5xx errors
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.warning(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise
            except httpx.RequestError as e:
                # Retry on network errors
                if attempt < self.max_retries:
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise

    def scan_asset(self, asset_id: str, tenant_id: str) -> dict:
        """Scan asset for compliance violations"""
        response = self._request_with_retry(
            "POST",
            "/scan",
            json={"asset_id": asset_id, "tenant_id": tenant_id}
        )
        return response.json()
```

#### Other Service Clients

- **DQServiceClient** (`hub/apps/dq/service_client.py`) - Data quality checks
- **SemanticServiceClient** (`hub/apps/semantic/service_client.py`) - RDF mapping operations
- **DataContractCLIClient** (`hub/apps/contracts/cli_client.py`) - Contract validation

### Error Handling

#### Retry Logic

**Strategy**: Exponential backoff with configurable max retries

- **Base delay**: 1 second
- **Backoff factor**: 2 (doubles each retry)
- **Max retries**: 2-3 attempts (configurable per service)
- **Retryable errors**: 5xx HTTP status codes, network errors
- **Non-retryable errors**: 4xx HTTP status codes (client errors)

**Example**:
```python
# Retry delays: 1s, 3s, 7s (if max_retries=3)
delay = backoff_factor * (2 ** attempt)
```

#### Circuit Breaker

**Purpose**: Prevent cascading failures when downstream service is unavailable

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures detected, requests rejected immediately
- **HALF_OPEN**: Testing recovery, allows limited requests

**Configuration**:
- **Failure threshold**: 5 consecutive failures
- **Success threshold**: 2 successful requests to close circuit
- **Timeout**: 60 seconds before transitioning to HALF_OPEN

**Implementation**: `hub/apps/core/error_handling/error_recovery.py`

```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker

circuit_breaker = CircuitBreaker(
    service_name="compliance-service",
    failure_threshold=5,
    timeout_seconds=60,
    success_threshold=2,
    redis_client=get_redis_client()
)

# Usage
response = circuit_breaker.call(lambda: service_client.request(...))
```

### Transaction Management

#### Distributed Transactions

For operations requiring ACID guarantees across services:

1. **Two-Phase Commit (2PC)**: Not recommended due to blocking nature
2. **Saga Pattern**: Preferred for distributed transactions (see Pattern 3)
3. **Compensating Actions**: Use workflow orchestration for complex multi-service transactions

**Example**: Contract creation with validation
```python
# Service A: Create contract
contract = contract_service.create_contract(...)

# Service B: Validate contract (if fails, compensate)
try:
    validation_result = validation_service.validate(contract.id)
except ValidationError:
    # Compensate: Delete contract
    contract_service.delete_contract(contract.id)
    raise
```

### Use Cases

- **API Service → Compliance Service**: Real-time compliance scanning
- **API Service → DQ Service**: Data quality validation
- **API Service → Semantic Service**: RDF mapping operations
- **API Service → DataContract Service**: Contract validation

### Performance Characteristics

- **Latency**: < 100ms (P50), < 500ms (P95)
- **Throughput**: ~100-1000 requests/second per service
- **Availability**: 99.9% (with circuit breaker protection)

---

## Pattern 2: Event-Driven Coordination (Asynchronous)

### When to Use

- **Decoupled operations** where services don't need immediate response
- **Eventual consistency** is acceptable
- **Scalability** requirements (high throughput)
- **Multiple subscribers** need to react to same event
- **Long-running operations** that shouldn't block request flow
- **Cross-cutting concerns** (logging, auditing, notifications)

### Pattern Architecture

```
Service A → Event Bus (Redis Pub/Sub) → Service B (Subscriber)
         ↓                              ↓
    PostgreSQL                      Service C (Subscriber)
    (Persistence)                  Service D (Subscriber)
```

### Implementation

#### Event Bus Architecture

**Components**:
- **Redis Pub/Sub**: Real-time event delivery (fire-and-forget)
- **PostgreSQL**: Event persistence for replay, audit, and debugging
- **Dead Letter Queue**: Failed event storage
- **Event Schema**: JSON Schema validation

**Location**: `hub/apps/core/events/`

#### Event Publishing

**Using EventPublisher Class**:

```python
from hub.apps.core.events import EventPublisher

# Initialize publisher
publisher = EventPublisher(
    service_name="contract_service",
    tenant_id=tenant_id,
    user_id=user_id
)

# Publish event
event_id = publisher.publish(
    event_type="contract.created",
    data={
        "contract_id": str(contract.id),
        "asset_id": str(asset.id),
        "spec_type": contract.original_spec_type
    },
    correlation_id=correlation_id,
    tags=["contract", "odcs"]
)
```

**Using Decorator**:

```python
from hub.apps.core.events import event_publisher

@event_publisher('contract.created', tenant_id=tenant_id)
def create_contract(contract_data: dict) -> dict:
    contract = Contract.objects.create(**contract_data)
    return {"contract_id": str(contract.id)}
```

**Using Function**:

```python
from hub.apps.core.events import publish_event

event_id = publish_event(
    event_type="contract.created",
    data={"contract_id": str(contract.id)},
    tenant_id=tenant_id,
    user_id=user_id
)
```

#### Event Subscription

**Using EventSubscriber Class**:

```python
from hub.apps.core.events import EventSubscriber

def handle_contract_created(event: dict):
    """Handle contract.created events"""
    contract_id = event["data"]["contract_id"]
    # Update search index
    search_service.index_contract(contract_id)
    # Send notification
    notification_service.notify_contract_created(contract_id)

# Subscribe to events
subscriber = EventSubscriber("search_service")
subscriber.subscribe("contract.created", handle_contract_created)
subscriber.subscribe("contract.updated", handle_contract_updated)
subscriber.subscribe("contract.*", handle_all_contract_events)  # Pattern matching
```

**Using Decorator**:

```python
from hub.apps.core.events import event_subscriber

@event_subscriber('search_service', 'contract.*')
def handle_contract_events(event: dict):
    """Handle all contract events"""
    event_type = event["event_type"]
    contract_id = event["data"]["contract_id"]

    if event_type == "contract.created":
        search_service.index_contract(contract_id)
    elif event_type == "contract.updated":
        search_service.update_contract_index(contract_id)
    elif event_type == "contract.deleted":
        search_service.remove_contract_index(contract_id)
```

#### Event Schema

**Base Event Structure**:

```json
{
  "event_id": "uuid",
  "event_type": "contract.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "contract_service",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid",
    "asset_id": "uuid"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["contract", "odcs"]
  }
}
```

**Event Type Format**: `domain.entity.action` (e.g., `contract.created`, `asset.activated`)

### Error Handling

#### Dead Letter Queue

Failed events are automatically moved to Dead Letter Queue (DLQ) for manual inspection and replay.

**Location**: `hub/apps/core/events/models.py` - `DeadLetterQueue` model

**Replay Failed Events**:

```python
from hub.apps.core.events import get_event_bus

event_bus = get_event_bus()

# Replay events from DLQ
failed_events = DeadLetterQueue.objects.filter(
    event_type="contract.created",
    created_at__gte=timezone.now() - timedelta(hours=1)
)

for failed_event in failed_events:
    event_bus.replay_event(failed_event.event_id)
```

#### Retry Logic

Event handlers should implement their own retry logic:

```python
from hub.apps.core.error_handling.error_recovery import with_retry

@with_retry(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)
def handle_contract_created(event: dict):
    """Handle contract.created events with retry"""
    contract_id = event["data"]["contract_id"]
    search_service.index_contract(contract_id)
```

### Transaction Management

#### Saga Pattern

For multi-step operations requiring eventual consistency:

1. **Choreography**: Services coordinate through events (preferred for simple flows)
2. **Orchestration**: Central coordinator manages workflow (see Pattern 3)

**Example: Contract Creation Saga**:

```python
# Step 1: Create contract
contract = contract_service.create_contract(...)
publish_event("contract.created", {"contract_id": contract.id})

# Step 2: Validate contract (async)
@event_subscriber('validation_service', 'contract.created')
def validate_contract(event):
    contract_id = event["data"]["contract_id"]
    try:
        validation_result = validation_service.validate(contract_id)
        publish_event("contract.validated", {"contract_id": contract_id})
    except ValidationError as e:
        publish_event("contract.validation_failed", {
            "contract_id": contract_id,
            "error": str(e)
        })

# Step 3: Compensate on failure
@event_subscriber('contract_service', 'contract.validation_failed')
def compensate_contract_creation(event):
    contract_id = event["data"]["contract_id"]
    contract_service.delete_contract(contract_id)
    publish_event("contract.deleted", {"contract_id": contract_id})
```

### Use Cases

- **Contract Created → Semantic Mapping**: Asynchronous RDF mapping
- **Asset Updated → Search Index Update**: Decoupled indexing
- **Compliance Scan Completed → Notifications**: Event-driven notifications
- **Contract Validated → Workflow Progression**: State machine transitions

### Performance Characteristics

- **Latency**: < 100ms (P50) for event delivery
- **Throughput**: ~1,500-2,000 events/second
- **Persistence**: 100% of events persisted to PostgreSQL
- **Availability**: 99.9% (Redis Pub/Sub + PostgreSQL persistence)

---

## Pattern 3: Workflow Orchestration (Multi-Step)

### When to Use

- **Complex multi-step operations** requiring coordination
- **State management** needed across multiple steps
- **Compensation logic** required for rollback
- **Long-running processes** (minutes to hours)
- **Conditional branching** based on step results
- **Parallel execution** of independent steps
- **Progress tracking** and resumability needed

### Pattern Architecture

```
Workflow Engine → Step 1 (Service A)
              → Step 2 (Service B)
              → Step 3 (Service C)
              ↓
         State Management
         (PostgreSQL)
```

### Implementation

#### Workflow Engine

**Location**: `hub/apps/orchestration/workflow_engine.py`

**Key Features**:
- Workflow DSL (JSON/YAML) for defining workflows
- Step execution with retry logic
- Compensation (Saga pattern) for rollback
- State management and progress tracking
- Event publishing for workflow lifecycle

#### Workflow DSL

**Location**: `hub/apps/orchestration/WORKFLOW_DSL.md`

**Simple Sequential Workflow**:

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "validate_contract",
      "type": "task",
      "task": "validate_contract_task",
      "input": {
        "contract_id": "{{input.contract_id}}"
      }
    },
    {
      "name": "normalize_contract",
      "type": "task",
      "task": "normalize_contract_task",
      "input": {
        "contract_id": "{{state.contract_id}}"
      }
    },
    {
      "name": "publish_contract",
      "type": "task",
      "task": "publish_contract_task",
      "input": {
        "contract_id": "{{state.contract_id}}"
      }
    }
  ]
}
```

**Workflow with Compensation**:

```json
{
  "version": "1.0.0",
  "compensation": {
    "enabled": true
  },
  "steps": [
    {
      "name": "create_contract",
      "type": "task",
      "task": "create_contract_task",
      "compensation": {
        "type": "task",
        "task": "delete_contract_task"
      }
    },
    {
      "name": "validate_contract",
      "type": "task",
      "task": "validate_contract_task",
      "compensation": {
        "type": "task",
        "task": "revert_validation_task"
      }
    }
  ]
}
```

**Workflow with Conditional Branching**:

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "check_contract_status",
      "type": "task",
      "task": "check_status_task"
    },
    {
      "name": "conditional_process",
      "type": "conditional",
      "condition": {
        "operator": "equals",
        "field": "status",
        "value": "active"
      },
      "then": [
        {
          "name": "activate_contract",
          "type": "task",
          "task": "activate_contract_task"
        }
      ],
      "else": [
        {
          "name": "deactivate_contract",
          "type": "task",
          "task": "deactivate_contract_task"
        }
      ]
    }
  ]
}
```

#### Creating and Executing Workflows

**Create Workflow Instance**:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

workflow_engine = WorkflowEngine()

# Create workflow instance
instance = workflow_engine.create_instance(
    workflow_name="contract_creation",
    input_data={
        "contract_id": contract_id,
        "tenant_id": tenant_id
    },
    tenant_id=tenant_id,
    created_by_id=user_id
)

# Start workflow execution
workflow_engine.start_instance(instance.id)

# Execute workflow (runs synchronously or asynchronously)
workflow_engine.execute_instance(instance.id)
```

**Register Task Functions**:

```python
def validate_contract_task(workflow_instance, step, input_data, state_data):
    """Task function for contract validation"""
    contract_id = input_data.get("contract_id")

    # Perform validation
    validation_result = contract_service.validate_contract(contract_id)

    # Return step output (merged into state_data)
    return {
        "validation_result": validation_result,
        "contract_id": contract_id,
        "status": "validated"
    }

# Register task
workflow_engine.register_task("validate_contract_task", validate_contract_task)
```

#### Saga Pattern Implementation

**Location**: `hub/apps/orchestration/saga.py`

**Saga Orchestrator**:

```python
from hub.apps.orchestration.saga import SagaOrchestrator, SagaStep

# Define saga steps
steps = [
    SagaStep(
        name="create_contract",
        execute=lambda state: contract_service.create_contract(...),
        compensate=lambda state: contract_service.delete_contract(state["contract_id"])
    ),
    SagaStep(
        name="validate_contract",
        execute=lambda state: validation_service.validate(state["contract_id"]),
        compensate=lambda state: None  # No compensation needed
    ),
    SagaStep(
        name="publish_contract",
        execute=lambda state: publish_service.publish(state["contract_id"]),
        compensate=lambda state: publish_service.unpublish(state["contract_id"])
    )
]

# Execute saga
saga = SagaOrchestrator()
result = saga.execute(steps, initial_state={"tenant_id": tenant_id})

# If any step fails, all previous steps are compensated in reverse order
```

### Error Handling

#### Retry Logic

Workflow steps automatically retry on failure:

```json
{
  "name": "validate_contract",
  "type": "retry",
  "max_retries": 3,
  "steps": [
    {
      "name": "validate_step",
      "type": "task",
      "task": "validate_contract_task"
    }
  ]
}
```

#### Compensation

Compensation is automatically executed on workflow failure:

1. **Forward execution**: Steps execute sequentially
2. **Failure detected**: Step fails, compensation triggered
3. **Reverse compensation**: Previous steps compensated in reverse order
4. **State restoration**: System restored to initial state

**Example**:

```python
# Step 1: Create contract (succeeds)
contract = contract_service.create_contract(...)

# Step 2: Validate contract (fails)
try:
    validation_service.validate(contract.id)
except ValidationError:
    # Compensation: Delete contract (Step 1 compensation)
    contract_service.delete_contract(contract.id)
    raise WorkflowExecutionError("Validation failed")
```

### Transaction Management

#### Saga Pattern with Compensation

The workflow engine implements the Saga pattern for distributed transactions:

- **No distributed locks**: Each step commits independently
- **Compensating actions**: Each step defines compensation logic
- **Eventual consistency**: System eventually consistent after compensation

**Compensation Flow**:

```
Step 1 (Create) → Step 2 (Validate) → Step 3 (Publish)
     ↓ (fails)
Compensate Step 2 → Compensate Step 1
```

### Use Cases

- **Asset Creation Workflow**: Multi-step asset onboarding with validation
- **Contract Creation Workflow**: Contract creation, validation, normalization, publishing
- **Transformation Pipeline Workflow**: Pipeline execution with quality checks
- **Marketplace Publishing Workflow**: Publishing with transformation and quality validation

### Performance Characteristics

- **Latency**: Variable (seconds to hours depending on workflow complexity)
- **Throughput**: ~10-100 workflows/second
- **State Management**: PostgreSQL-backed, durable
- **Resumability**: Workflows can be paused and resumed

---

## Pattern Selection Criteria

### Decision Matrix

| Criteria | Direct Calls | Event-Driven | Workflow Orchestration |
|----------|-------------|--------------|----------------------|
| **Response Time** | < 1 second | < 100ms (event delivery) | Variable (seconds to hours) |
| **Consistency** | Strong | Eventual | Eventual (with compensation) |
| **Coupling** | Tight | Loose | Medium |
| **Scalability** | Medium | High | Medium |
| **Complexity** | Low | Medium | High |
| **State Management** | None | Event log | Full state tracking |
| **Error Handling** | Retry + Circuit Breaker | DLQ + Retry | Compensation + Retry |
| **Use Case** | Simple operations | Decoupled operations | Complex multi-step |

### Selection Guidelines

#### Choose Direct Service Calls When:

- ✅ Immediate response required (< 1 second)
- ✅ Strong consistency needed
- ✅ Simple request-response interaction
- ✅ Low latency critical
- ✅ Synchronous validation or data retrieval

**Example**: Contract validation during creation, real-time compliance scanning

#### Choose Event-Driven When:

- ✅ Decoupled operations acceptable
- ✅ Eventual consistency acceptable
- ✅ Multiple subscribers needed
- ✅ High throughput required
- ✅ Long-running operations shouldn't block

**Example**: Search index updates, notifications, audit logging

#### Choose Workflow Orchestration When:

- ✅ Complex multi-step operations
- ✅ State management required
- ✅ Compensation logic needed
- ✅ Conditional branching required
- ✅ Progress tracking needed

**Example**: Asset onboarding workflow, contract creation with validation and normalization

### Hybrid Approaches

**Combining Patterns**:

1. **Direct Call + Event Publishing**: Call service directly, then publish event for downstream processing
   ```python
   # Direct call for immediate response
   result = compliance_service.scan_asset(asset_id)

   # Event for downstream processing
   publish_event("compliance.scan.completed", {"asset_id": asset_id, "result": result})
   ```

2. **Workflow + Event-Driven**: Workflow orchestrates steps, events trigger workflow progression
   ```python
   # Workflow step publishes event
   publish_event("contract.validated", {"contract_id": contract_id})

   # Event triggers next workflow step
   @event_subscriber('workflow_engine', 'contract.validated')
   def proceed_to_normalization(event):
       workflow_engine.execute_next_step(workflow_instance_id)
   ```

---

## Real-World Examples

This section provides comprehensive, real-world examples from the codebase demonstrating each integration pattern with actual code and tests.

### Example 1: Direct Service Call (ContractService → AssetService)

**Use Case**: AssetService needs to link an ODPS contract to an asset, requiring validation from ContractService.

**Location**: `hub/apps/assets/services.py` (lines 412-500)

**Implementation**:

```python
from hub.apps.assets.services import AssetService
from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.core.exceptions import NotFoundError, ValidationError

class AssetService(BaseService):
    """Service for asset operations."""

    def link_odps_contract_to_asset(
        self,
        asset_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Contract:
        """
        Link ODPS contract to asset using direct service calls.

        This method demonstrates Pattern 1: Direct Service Calls
        - Synchronous validation via ContractService
        - Immediate response required
        - Strong consistency needed
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        def _link():
            # Step 1: Get asset (direct database access)
            asset = self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )

            # Step 2: Direct service call to ODPSService
            odps_service = ODPSService(
                tenant_id=effective_tenant_id,
                user_id=effective_user_id
            )

            if odps_contract_id:
                # Step 3: Direct service call to ContractService for validation
                contract_service = ContractService(
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id
                )

                # Synchronous call - waits for response
                odps_contract = contract_service.get_contract(
                    contract_id=odps_contract_id,
                    tenant_id=effective_tenant_id
                )

                # Step 4: Validate contract type (synchronous validation)
                if odps_contract.original_spec_type != OriginalSpecType.ODPS:
                    raise ValidationError(
                        f"Contract {odps_contract_id} is not an ODPS contract",
                        code="INVALID_CONTRACT_TYPE"
                    )

                # Step 5: Link contract to asset (atomic operation)
                odps_contract.asset = asset
                odps_contract.version = self._calculate_version(asset, effective_tenant_id)
                odps_contract.save(update_fields=['asset', 'version'])

                return odps_contract
            elif odps_raw:
                # Direct service call to create new ODPS contract
                odps_contract = odps_service.create_odps(
                    odps_raw=odps_raw,
                    odps_format=odps_format or "json",
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    asset_id=asset_id
                )
                return odps_contract

        # Execute within transaction for atomicity
        return self.execute_with_metrics(
            operation="link_odps_contract_to_asset",
            tenant_id=effective_tenant_id,
            func=_link
        )
```

**Test Example**:

**Location**: `hub/apps/contracts/tests/test_odps_service_integration.py` (lines 300-330)

```python
from django.test import TestCase
from hub.apps.assets.services import AssetService
from hub.apps.contracts.services import ODPSService
from hub.apps.contracts.models import OriginalSpecType
from hub.apps.assets.models import Asset, AssetStatus

class AssetServiceODPSIntegrationTest(TestCase):
    """Tests for AssetService integration with ODPSService."""

    def test_link_odps_contract_to_asset_with_existing_contract(self):
        """Test direct service call pattern: AssetService → ContractService."""
        # Setup: Create ODPS contract
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute: Direct service call
        asset_service = AssetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        linked_contract = asset_service.link_odps_contract_to_asset(
            asset_id=str(self.asset.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify: Synchronous response with strong consistency
        self.assertIsNotNone(linked_contract)
        self.assertEqual(linked_contract.asset, self.asset)
        self.assertEqual(linked_contract.original_spec_type, OriginalSpecType.ODPS)

        # Verify: Contract version calculated synchronously
        self.assertGreater(linked_contract.version, 0)
```

**Key Characteristics**:
- ✅ Synchronous execution (waits for response)
- ✅ Strong consistency (immediate validation)
- ✅ Error handling via exceptions
- ✅ Transaction management for atomicity
- ✅ Direct service-to-service communication

---

### Example 2: Event-Driven Coordination (ContractService → Event Bus → SearchService)

**Use Case**: When an ODPS contract is created, multiple services need to be notified (SearchService for indexing, NotificationService for alerts, AuditService for logging).

**Location**: `hub/apps/contracts/services.py` (lines 2400-2440)

**Implementation**:

```python
from hub.apps.core.events.service_publishers import ODPSEventPublisher
from hub.apps.contracts.models import Contract

class ODPSService(BaseService, ODPSEventPublisher):
    """Service for ODPS contract operations."""

    @transaction.atomic
    def create_odps(
        self,
        odps_raw: str,
        odps_format: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> Contract:
        """
        Create ODPS contract and publish events.

        This method demonstrates Pattern 2: Event-Driven Coordination
        - Decoupled operations (search indexing, notifications)
        - Eventual consistency acceptable
        - Multiple subscribers can react
        """
        # ... contract creation logic ...

        # Publish event to event bus (asynchronous, fire-and-forget)
        try:
            event_id = self.publish_odps_created(
                contract_id=str(contract.id),
                asset_id=str(asset.id) if asset else None,
                status=contract.status,
                odps_version=odps_version,
                original_format=contract.original_format
            )

            # Track event ID for compensation if needed
            if event_id and state.events_published is not None:
                state.events_published.append(str(event_id))

        except Exception as e:
            # If event publishing fails, compensate
            logger.exception(
                "odps_created_event_publish_failed",
                contract_id=str(contract.id),
                error=str(e),
                message="Failed to publish ODPS created event, triggering compensation"
            )

            # Compensation logic (Saga pattern)
            compensation.compensate(
                state=state,
                rollback_contract=True,
                cleanup_resources=True,
                restore_state=True,
                publish_compensation_events=True
            )
            raise ValidationError(
                message=f"Failed to publish ODPS created event: {str(e)}",
                code="ODPS_EVENT_PUBLISH_FAILED"
            ) from e

        return contract
```

**Event Publisher Implementation**:

**Location**: `hub/apps/core/events/service_publishers.py`

```python
class ODPSEventPublisher:
    """Event publisher for ODPS-related events."""

    def publish_odps_created(
        self,
        contract_id: str,
        asset_id: Optional[str] = None,
        status: str = None,
        odps_version: str = None,
        original_format: str = None
    ) -> str:
        """
        Publish odps.created event to event bus.

        Subscribers:
        - SearchService: Index contract for search
        - NotificationService: Send creation notifications
        - AuditService: Log contract creation
        """
        from hub.apps.core.events.publisher import EventPublisher

        publisher = EventPublisher(
            service_name="contract_service",
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        event_id = publisher.publish(
            event_type="odps.created",
            data={
                "contract_id": contract_id,
                "asset_id": asset_id,
                "status": status,
                "odps_version": odps_version,
                "original_format": original_format
            },
            tags=["odps", "contract", "product"]
        )

        return event_id
```

**Event Subscriber Implementation**:

**Location**: `hub/apps/search/indexing.py` (example)

```python
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.core.events.bus import get_event_bus

class SearchIndexer:
    """Service for indexing contracts in search."""

    def __init__(self):
        self.event_bus = get_event_bus()
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Subscribe to ODPS events for indexing."""
        subscriber = EventSubscriber("search_service")

        # Subscribe to ODPS created events
        subscriber.subscribe(
            "odps.created",
            self._handle_odps_created
        )

        # Subscribe to ODPS updated events
        subscriber.subscribe(
            "odps.updated",
            self._handle_odps_updated
        )

    def _handle_odps_created(self, event: dict):
        """Handle odps.created event - index contract for search."""
        try:
            contract_id = event["data"]["contract_id"]
            asset_id = event["data"].get("asset_id")

            # Index contract asynchronously
            self.index_contract(contract_id, asset_id)

            logger.info(
                "Contract indexed from event",
                contract_id=contract_id,
                event_id=event["event_id"]
            )
        except Exception as e:
            # Event automatically moved to Dead Letter Queue
            logger.error(
                "Failed to index contract from event",
                contract_id=event["data"].get("contract_id"),
                error=str(e),
                event_id=event.get("event_id")
            )
            raise  # Re-raise to trigger DLQ

    def index_contract(self, contract_id: str, asset_id: Optional[str] = None):
        """Index contract in search engine."""
        # ... indexing logic ...
        pass
```

**Test Example**:

**Location**: `hub/apps/contracts/tests/test_odps_event_bus_integration.py`

```python
from django.test import TestCase, override_settings
from hub.apps.contracts.services import ODPSService
from hub.apps.core.events.models import Event

@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False)
class ODPSEventPublishingTest(TestCase):
    """Tests for ODPS event publishing."""

    def test_odps_created_event_published(self):
        """Test event-driven pattern: ContractService → Event Bus → Subscribers."""
        # Setup: Create ODPS service
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute: Create ODPS contract (publishes event)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify: Event was published to PostgreSQL
        events = Event.objects.filter(
            event_type="odps.created",
            tenant_id=self.tenant.id
        )

        self.assertGreater(events.count(), 0, "Event should be persisted")

        # Verify: Event contains correct data
        contract_event = events.first()
        self.assertEqual(contract_event.event_type, "odps.created")
        event_data = contract_event.data if isinstance(contract_event.data, dict) else {}
        self.assertEqual(event_data.get("contract_id"), str(contract.id))

        # Note: In production, subscribers would process events asynchronously
        # SearchService would index the contract
        # NotificationService would send notifications
```

**Key Characteristics**:
- ✅ Asynchronous execution (fire-and-forget)
- ✅ Eventual consistency (subscribers process independently)
- ✅ Multiple subscribers (search, notifications, audit)
- ✅ Dead Letter Queue for failed events
- ✅ Saga pattern for compensation

---

### Example 3: Workflow Orchestration (ProductCreationWorkflow)

**Use Case**: Creating an ODPS product requires multiple coordinated steps: parsing, validation, normalization, contract creation, linking, indexing, and semantic mapping.

**Location**: `hub/apps/orchestration/workflows/product_creation.py`

**Workflow Definition**:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance

class ProductCreationWorkflow:
    """
    Product creation workflow orchestrator (ODPS Product-First flow).

    This workflow demonstrates Pattern 3: Workflow Orchestration
    - Complex multi-step operations
    - State management across steps
    - Compensation logic for rollback
    - Retry logic for transient failures
    """

    WORKFLOW_NAME = "product_creation"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """Register workflow definition with DSL."""
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "parse_odps",
                    "type": "task",
                    "task": "product_creation.parse_odps"
                },
                {
                    "name": "resolve_refs",
                    "type": "task",
                    "task": "product_creation.resolve_refs",
                    "dependencies": ["parse_odps"]
                },
                {
                    "name": "extract_contract",
                    "type": "task",
                    "task": "product_creation.extract_contract",
                    "dependencies": ["resolve_refs"]
                },
                {
                    "name": "validate_odcs",
                    "type": "task",
                    "task": "product_creation.validate_odcs",
                    "dependencies": ["extract_contract"]
                },
                {
                    "name": "normalize_odcs",
                    "type": "task",
                    "task": "product_creation.normalize_odcs",
                    "dependencies": ["validate_odcs"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_normalize_odcs"
                    }
                },
                {
                    "name": "create_odcs_contract",
                    "type": "task",
                    "task": "product_creation.create_odcs_contract",
                    "dependencies": ["normalize_odcs"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_odcs_contract"
                    }
                },
                {
                    "name": "create_odps_contract",
                    "type": "task",
                    "task": "product_creation.create_odps_contract",
                    "dependencies": ["create_odcs_contract"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_odps_contract"
                    }
                },
                {
                    "name": "link_contracts",
                    "type": "task",
                    "task": "product_creation.link_contracts",
                    "dependencies": ["create_odps_contract"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_link_contracts"
                    }
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "product_creation.index_for_search",
                    "dependencies": ["link_contracts"]
                },
                {
                    "name": "semantic_mapping",
                    "type": "task",
                    "task": "product_creation.semantic_mapping",
                    "dependencies": ["index_for_search"]
                }
            ],
            "compensation": {
                "enabled": True
            }
        }

        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates ODPS product creation with validation, normalization, linking, indexing, and semantic mapping"
        )
```

**Workflow Task Implementation**:

```python
    @staticmethod
    def _create_odcs_contract_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step
    ) -> Dict[str, Any]:
        """
        Create ODCS contract from normalized data.

        This task demonstrates:
        - State management (contract_id stored in state_data)
        - Error handling (raises exceptions for workflow engine)
        - Compensation support (rollback task registered)
        """
        from hub.apps.contracts.services import ContractService

        tenant_id = input_data.get("tenant_id")
        user_id = input_data.get("user_id")
        normalized_odcs = input_data.get("normalized_odcs")

        # Create contract service
        contract_service = ContractService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Create ODCS contract
        odcs_contract = contract_service.create_contract(
            original_raw=normalized_odcs["original_raw"],
            original_format=normalized_odcs["original_format"],
            tenant_id=tenant_id,
            user_id=user_id,
            original_spec_type="ODCS"
        )

        # Update workflow state
        state_data = instance.state_data or {}
        state_data["odcs_contract_id"] = str(odcs_contract.id)
        instance.state_data = state_data
        instance.save(update_fields=["state_data", "updated_at"])

        logger.info(
            "ODCS contract created in workflow",
            workflow_instance_id=str(instance.id),
            contract_id=str(odcs_contract.id)
        )

        return {
            "odcs_contract_id": str(odcs_contract.id),
            "state": state_data
        }

    @staticmethod
    def _rollback_odcs_contract_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step
    ) -> Dict[str, Any]:
        """
        Compensation task: Delete ODCS contract if workflow fails.

        This demonstrates Saga pattern compensation logic.
        """
        from hub.apps.contracts.models import Contract

        state_data = instance.state_data or {}
        odcs_contract_id = state_data.get("odcs_contract_id")

        if odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
                odcs_contract.delete()

                logger.info(
                    "ODCS contract rolled back",
                    workflow_instance_id=str(instance.id),
                    contract_id=odcs_contract_id
                )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODCS contract not found for rollback",
                    workflow_instance_id=str(instance.id),
                    contract_id=odcs_contract_id
                )

        return {"compensated": True}
```

**Workflow Execution**:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow

# Initialize workflow engine and registry
engine = WorkflowEngine()
registry = WorkflowRegistry()

# Register workflow and tasks
ProductCreationWorkflow.register_workflow(registry)
ProductCreationWorkflow.register_tasks(engine)

# Create workflow instance
input_data = {
    "original_raw": odps_raw,
    "original_format": "json",
    "tenant_id": tenant_id,
    "user_id": user_id
}

instance = engine.create_instance(
    workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
    input_data=input_data,
    tenant_id=tenant_id,
    created_by_id=user_id
)

# Start workflow execution
instance = engine.start_instance(str(instance.id))

# Execute workflow (runs all steps in order)
instance = engine.execute_instance(str(instance.id))

# Check workflow status
if instance.status == WorkflowStatus.COMPLETED:
    # Workflow succeeded
    odcs_contract_id = instance.state_data.get("odcs_contract_id")
    odps_contract_id = instance.state_data.get("odps_contract_id")
    # ... use results ...
elif instance.status == WorkflowStatus.FAILED:
    # Workflow failed - compensation executed automatically
    error_message = instance.error_message
    # ... handle failure ...
```

**Test Example**:

**Location**: `hub/apps/orchestration/workflows/tests/test_product_creation.py`

```python
from django.test import TestCase
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.orchestration.models import WorkflowStatus

class ProductCreationWorkflowTest(TestCase):
    """Tests for ProductCreationWorkflow."""

    def setUp(self):
        """Set up workflow engine and registry."""
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

    def test_product_creation_workflow_success(self):
        """Test workflow orchestration pattern: Multi-step coordination."""
        # Setup: Prepare input data
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        # Execute: Create and run workflow
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Verify: Workflow completed successfully
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify: All steps executed in order
        steps = instance.steps.all().order_by('step_index')
        self.assertEqual(len(steps), 11)  # All 11 steps

        # Verify: State data contains contract IDs
        self.assertIn("odcs_contract_id", instance.state_data)
        self.assertIn("odps_contract_id", instance.state_data)

        # Verify: Contracts were created
        from hub.apps.contracts.models import Contract
        odcs_contract = Contract.objects.get(
            id=instance.state_data["odcs_contract_id"]
        )
        odps_contract = Contract.objects.get(
            id=instance.state_data["odps_contract_id"]
        )

        self.assertIsNotNone(odcs_contract)
        self.assertIsNotNone(odps_contract)

    def test_product_creation_workflow_compensation(self):
        """Test workflow compensation: Rollback on failure."""
        # Setup: Create workflow with invalid data (will fail)
        input_data = {
            "original_raw": "invalid json",
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        # Execute: Run workflow (will fail)
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        instance = self.engine.start_instance(str(instance.id))

        try:
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify: Workflow failed
        self.assertEqual(instance.status, WorkflowStatus.FAILED)

        # Verify: Compensation executed (no partial contracts created)
        from hub.apps.contracts.models import Contract
        contracts = Contract.objects.filter(
            tenant_id=self.tenant.id
        )
        self.assertEqual(contracts.count(), 0, "Compensation should rollback contracts")
```

**Key Characteristics**:
- ✅ Multi-step orchestration (11 steps in sequence)
- ✅ State management (state_data persists across steps)
- ✅ Dependency management (steps depend on previous steps)
- ✅ Compensation logic (automatic rollback on failure)
- ✅ Retry logic (transient failures retried automatically)
- ✅ Saga pattern (distributed transaction management)

---

## Anti-Patterns to Avoid

### 1. Synchronous Calls in Event Handlers

**❌ Anti-Pattern**:
```python
@event_subscriber('service_a', 'contract.created')
def handle_contract_created(event):
    # Synchronous call blocks event processing
    result = compliance_service.scan_contract(event["data"]["contract_id"])
    # If compliance service is slow, blocks all event processing
```

**✅ Correct Pattern**:
```python
@event_subscriber('service_a', 'contract.created')
def handle_contract_created(event):
    # Publish event for async processing
    publish_event("compliance.scan.requested", {
        "contract_id": event["data"]["contract_id"]
    })
```

### 2. Tight Coupling Through Direct Calls

**❌ Anti-Pattern**:
```python
# Service A directly calls Service B, C, D
def process_asset(asset_id):
    compliance_result = compliance_service.scan(asset_id)  # Direct call
    dq_result = dq_service.validate(asset_id)  # Direct call
    semantic_result = semantic_service.map(asset_id)  # Direct call
    # Tight coupling: if any service fails, entire operation fails
```

**✅ Correct Pattern**:
```python
# Use workflow orchestration for coordination
def process_asset(asset_id):
    workflow_engine.create_instance(
        workflow_name="asset_processing",
        input_data={"asset_id": asset_id}
    )
    # Workflow handles retries, compensation, and parallel execution
```

### 3. Ignoring Circuit Breakers

**❌ Anti-Pattern**:
```python
def call_external_service():
    # No circuit breaker protection
    response = requests.get("https://external-api.com/data")
    # If service is down, all requests fail immediately
    return response.json()
```

**✅ Correct Pattern**:
```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker

circuit_breaker = CircuitBreaker(
    service_name="external-api",
    failure_threshold=5,
    timeout_seconds=60
)

def call_external_service():
    # Protected by circuit breaker
    return circuit_breaker.call(lambda: requests.get("https://external-api.com/data").json())
```

### 4. Missing Retry Logic

**❌ Anti-Pattern**:
```python
def call_service():
    # No retry logic
    response = httpx.get("http://service:8080/api")
    response.raise_for_status()
    # Transient failures cause immediate failure
    return response.json()
```

**✅ Correct Pattern**:
```python
def call_service():
    # Retry with exponential backoff
    for attempt in range(3):
        try:
            response = httpx.get("http://service:8080/api")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < 2:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

### 5. Blocking Operations in Workflows

**❌ Anti-Pattern**:
```python
def workflow_step(workflow_instance, step, input_data, state_data):
    # Blocking operation in workflow step
    result = long_running_service.process(data)  # Blocks for minutes
    # Workflow engine blocked, can't process other workflows
    return {"result": result}
```

**✅ Correct Pattern**:
```python
def workflow_step(workflow_instance, step, input_data, state_data):
    # Trigger async operation, update workflow state
    job_id = long_running_service.start_async_process(data)
    workflow_instance.state_data["job_id"] = job_id
    workflow_instance.status = WorkflowStatus.WAITING
    workflow_instance.save()

    # Subscribe to completion event
    @event_subscriber('workflow_engine', f'job.{job_id}.completed')
    def resume_workflow(event):
        workflow_engine.resume_instance(workflow_instance.id)

    return {"job_id": job_id}
```

### 6. Missing Distributed Tracing

**❌ Anti-Pattern**:
```python
def call_service():
    # No trace propagation
    response = httpx.get("http://service:8080/api")
    # Can't trace request across services
    return response.json()
```

**✅ Correct Pattern**:
```python
from hub.apps.api.middleware.trace_propagation import get_trace_headers

def call_service():
    # Propagate trace headers
    trace_headers = get_trace_headers()
    response = httpx.get(
        "http://service:8080/api",
        headers=trace_headers
    )
    # Request traced across all services
    return response.json()
```

### 7. Ignoring Dead Letter Queue

**❌ Anti-Pattern**:
```python
@event_subscriber('service', 'contract.created')
def handle_event(event):
    # No error handling, failed events lost
    process_contract(event["data"]["contract_id"])
```

**✅ Correct Pattern**:
```python
@event_subscriber('service', 'contract.created')
def handle_event(event):
    try:
        process_contract(event["data"]["contract_id"])
    except Exception as e:
        # Event automatically moved to DLQ
        logger.error(f"Failed to process event: {e}")
        # Monitor DLQ and replay failed events
        raise
```

### 8. Inconsistent Error Handling

**❌ Anti-Pattern**:
```python
# Different error handling in each service client
class ServiceA:
    def call(self):
        try:
            return requests.get(...).json()
        except:  # Too broad
            return None

class ServiceB:
    def call(self):
        return requests.get(...).json()  # No error handling
```

**✅ Correct Pattern**:
```python
# Consistent error handling pattern
class BaseServiceClient:
    def _request_with_retry(self, method, endpoint, **kwargs):
        # Standardized retry logic
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
```

---

## Summary

### Quick Reference

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| **Direct Calls** | Immediate response needed, strong consistency | High throughput, eventual consistency acceptable |
| **Event-Driven** | Decoupled operations, high scalability | Immediate response required, strong consistency needed |
| **Workflow** | Complex multi-step, state management | Simple operations, low latency critical |

### Best Practices

1. **Always use circuit breakers** for external service calls
2. **Implement retry logic** with exponential backoff
3. **Propagate distributed tracing** headers across service boundaries
4. **Use event-driven patterns** for decoupled operations
5. **Use workflow orchestration** for complex multi-step operations
6. **Monitor Dead Letter Queue** and replay failed events
7. **Implement compensation logic** for distributed transactions
8. **Follow consistent error handling** patterns across all services

### Related Documentation

- [Event Bus Documentation](EVENT_BUS.md)
- [Workflow DSL Documentation](hub/apps/orchestration/WORKFLOW_DSL.md)
- [Error Handling Guide](ERROR_HANDLING.md)
- [Services Architecture](SERVICES_ARCHITECTURE.md)

---

**Last Updated**: 2026-03-22
**Version**: 1.0.0


### Business Logic Integration


**Last Updated**: 2026-03-22
**Version**: 2.1.0

---

## Overview

This document describes how business logic is integrated across all features of the Data Interoperability Hub. The platform uses a comprehensive integration layer that coordinates features through workflows, service layers, events, and business rules.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Service Layer Coordination](#service-layer-coordination)
3. [Workflow Integration](#workflow-integration)
4. [Event-Driven Coordination](#event-driven-coordination)
5. [Business Rules Framework](#business-rules-framework-implemented---phase-972)
6. [Service Integration Patterns](#service-integration-patterns-implemented---phase-973)
7. [Compensation Logic](#compensation-logic)
8. [Data Consistency](#data-consistency)
9. [Frontend Integration](#frontend-integration)
10. [Best Practices](#best-practices)

---

## Architecture

### Integration Layer Components

```
┌─────────────────────────────────────────────────────────┐
│              Business Logic Integration Layer            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Service    │  │   Workflow   │  │    Event     │ │
│  │    Layer     │  │   Engine     │  │     Bus      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                  │                  │         │
│         └──────────────────┼──────────────────┘         │
│                            │                              │
│                   ┌────────▼────────┐                    │
│                   │ Business Rules  │                    │
│                   │    Framework    │                    │
│                   └─────────────────┘                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Features    │    │  Features    │    │  Features    │
│  (AI/ML)     │    │(Transformation)│  │  (Social)   │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## Service Layer Coordination

### Service Layer Pattern

All business logic is coordinated through service layer classes that extend `BaseService`:

#### BaseService

```python
from hub.apps.core.services.base import BaseService

class MyService(BaseService):
    service_name = "my_service"

    def do_something(self, tenant_id: str, data: dict):
        # Business logic here
        # Publish events
        # Return result
        pass
```

#### Service Responsibilities

1. **Business Logic Coordination**: Coordinate operations across features
2. **Event Publishing**: Publish events for asynchronous coordination
3. **Transaction Management**: Manage transaction boundaries
4. **Error Handling**: Handle errors consistently
5. **Audit Logging**: Log all operations (emit audit events once per mutation)

#### Service Layer Consistency (Phase 24.7)

**CRITICAL**: All create/update/delete operations for domain resources MUST go through a service layer. Views use serializers for request validation only.

**Rule**: No direct `serializer.save()` in views for writes. All mutations go through service layer methods that:
- Apply business rules validation
- Emit audit events once per mutation
- Handle transaction boundaries
- Publish domain events

**Pattern**:
```python
# ✅ CORRECT: Use service layer
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    service = MyService(tenant_id=tenant_id, user_id=str(request.user.id))
    resource = service.create_resource(
        tenant_id=tenant_id,
        user_id=str(request.user.id),
        **serializer.validated_data,
    )
    return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)

# ❌ WRONG: Direct serializer.save() bypasses business rules and audit
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    resource = serializer.save()  # ❌ Bypasses service layer
    return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)
```

**Examples**:
- `ScheduledIngestionViewSet`: Uses `IngestionService.create_scheduled_ingestion()`, `IngestionService.update_scheduled_ingestion()`, and `IngestionService.delete_scheduled_ingestion()`
- `UserViewSet`: Uses `UserService.create_user()`, `UserService.update_user()`, and `UserService.delete_user()`
- `APIKeyViewSet`: Uses `APIKeyService.create_api_key()` and `APIKeyService.delete_api_key()`

**Note**: Serializers are still used for request validation and response serialization. The service layer handles the actual database mutations.

See `docs/DEVELOPMENT_GUIDE.md` for complete guidelines.

### Service Classes

#### TransformationService ✅ (Implemented - Phase 9.5.1)

**Location**: `hub/apps/transformation/services.py`
**Status**: ✅ Implemented
**Phase**: 9.5.1

**Responsibilities**:
- Coordinate pipeline execution with asset lifecycle
- Manage pipeline-to-asset relationships
- Handle pipeline result synchronization
- Validate pipeline compatibility with assets
- Publish transformation events (pipeline.created, pipeline.executed, etc.)

**Integration**:
- Extends `BaseService` and `TransformationEventPublisher`
- Integrates with AssetCreationWorkflow, TransformationPipelineWorkflow
- Uses Event Bus for asynchronous coordination
- Uses TransformationBusinessRules for validation

**Key Methods**:
- `create_pipeline()` - Create and validate transformation pipeline
- `execute_pipeline()` - Execute pipeline with asset coordination
- `validate_pipeline_compatibility()` - Validate pipeline against assets

**Example**:
```python
from hub.apps.transformation.services import TransformationService

service = TransformationService(tenant_id=tenant_id, user_id=user_id)
pipeline = service.create_pipeline(
    name="data_cleaning",
    asset_id=asset_id,
    nodes=[...]
)
result = service.execute_pipeline(pipeline.id, asset_id)
```

#### DataMeshService ✅ (Implemented - Phase 9.5.2)

**Location**: `hub/apps/mesh/services.py`
**Status**: ✅ Implemented
**Phase**: 9.5.2

**Responsibilities**:
- Coordinate domain operations
- Manage domain-to-asset relationships
- Handle federated governance
- Coordinate mesh topology updates
- Publish data mesh events (domain.created, domain.updated, etc.)

**Integration**:
- Extends `BaseService` and `DataMeshEventPublisher`
- Integrates with DataMeshWorkflow, AssetUpdateWorkflow
- Uses Event Bus for asynchronous coordination
- Uses DataMeshBusinessRules, PolicyBusinessRules, TopologyBusinessRules for validation

**Key Methods**:
- `create_domain()` - Create data mesh domain
- `update_domain()` - Update domain configuration
- `transfer_ownership()` - Transfer asset ownership between domains

#### VirtualizationService ✅ (Implemented - Phase 9.5.3)

**Location**: `hub/apps/virtualization/services.py`
**Status**: ✅ Implemented
**Phase**: 9.5.3

**Responsibilities**:
- Coordinate virtual dataset operations
- Manage query execution across multiple sources
- Handle schema alignment and validation
- Coordinate virtualization events
- Publish virtualization events (dataset.created, query.executed, etc.)

**Integration**:
- Extends `BaseService` and `VirtualizationEventPublisher`
- Integrates with VirtualizationWorkflow, AssetUpdateWorkflow
- Uses Event Bus for asynchronous coordination
- Uses VirtualizationBusinessRules, QueryExecutionBusinessRules, ResultBusinessRules for validation

**Key Methods**:
- `create_virtual_dataset()` - Create virtual dataset
- `execute_query()` - Execute query across sources
- `validate_schema_alignment()` - Validate schema compatibility

#### AIService ✅ (Implemented - MVP)

**Location**: `hub/apps/ai/services.py`
**Status**: ✅ Implemented
**Phase**: MVP

**Responsibilities**:
- Coordinate ML operations with workflows
- Manage ML model lifecycle
- Handle ML result validation
- Coordinate schema matching with contract creation
- Publish AI/ML events (schema_matching_completed, classification_completed, etc.)

**Integration**:
- Extends `BaseService`
- Integrates with AssetCreationWorkflow for schema matching
- Uses Event Bus for asynchronous coordination
- Uses AI business rules for validation (if implemented)

**Key Methods**:
- `match_schema()` - AI-powered schema matching
- `classify_asset()` - Auto-classification of assets
- `validate_ml_result()` - Validate ML model results

#### SocialService ✅ (Implemented - MVP)

**Location**: `hub/apps/social/services.py`
**Status**: ✅ Implemented
**Phase**: MVP

**Responsibilities**:
- Coordinate ratings/reviews with asset updates
- Manage review moderation workflows
- Handle social feature events
- Coordinate activity feeds with asset operations
- Publish social events (review.created, rating.updated, etc.)

**Integration**:
- Extends `BaseService`
- Integrates with SocialFeatureWorkflow
- Uses Event Bus for asynchronous coordination
- Uses Social business rules for validation (if implemented)

**Key Methods**:
- `create_review()` - Create asset review
- `update_rating()` - Update asset rating
- `moderate_review()` - Moderate review content

#### MarketplaceService ✅ (Implemented - MVP)

**Location**: `hub/apps/marketplace/services.py`
**Status**: ✅ Implemented
**Phase**: MVP

**Responsibilities**:
- Coordinate publishing with transformation/quality
- Manage purchase workflows
- Handle pricing model validation
- Coordinate marketplace events with asset updates
- Publish marketplace events (purchase.completed, pricing.changed, etc.)

**Integration**:
- Extends `BaseService`
- Integrates with MarketplacePublishingWorkflow
- Uses Event Bus for asynchronous coordination
- Uses MarketplaceBusinessRules for validation

**Key Methods**:
- `publish_listing()` - Publish asset to marketplace
- `create_purchase()` - Create purchase order
- `validate_pricing()` - Validate pricing model

#### ODPSService ✅ (Implemented - ODPS Integration)

**Location**: `hub/apps/contracts/services.py`
**Status**: ✅ Implemented
**Phase**: ODPS Integration

**Responsibilities**:
- Coordinate ODPS contract creation with normalization and validation
- Manage ODPS linking to ODCS contracts
- Handle ODPS export and generation
- Coordinate ODPS workflow orchestration
- Publish ODPS events (odps.created, odps.normalized, odps.linked, etc.)

**Integration**:
- Extends `BaseService` and `ODPSEventPublisher`
- Integrates with ProductCreationWorkflow for multi-step operations
- Uses ODPSNormalizer for document normalization
- Uses ODPSBusinessRules for validation
- Uses Event Bus for asynchronous coordination

**Key Methods**:
- `create_odps()` - Create ODPS contract with normalization
- `link_odps_to_odcs()` - Link ODPS to existing ODCS contract
- `export_odps()` - Export HubContract to ODPS format
- `generate_odps_from_hubcontract()` - Generate ODPS from HubContract

**Example**:
```python
from hub.apps.contracts.services import ODPSService

service = ODPSService(tenant_id=tenant_id, user_id=user_id)
contract = service.create_odps(
    odps_raw=odps_document,
    odps_format="JSON",
    asset_id=asset_id,
    resolve_external_refs=True
)
```

#### MarketplaceIntegrationService ✅ (Implemented - Marketplace Integration Framework)

**Location**: `hub/apps/integrations/services.py`
**Status**: ✅ Implemented
**Phase**: Marketplace Integration Framework

**Responsibilities**:
- Coordinate marketplace connection management
- Manage bidirectional asset synchronization (PUSH and PULL)
- Handle sync job management and tracking
- Coordinate marketplace events with asset updates
- Publish marketplace integration events (marketplace.connection.created, marketplace.sync.completed, etc.)

**Integration**:
- Extends `BaseService`, `IntegrationEventPublisher`, and `MarketplaceEventPublisher`
- Integrates with MarketplaceSyncWorkflow for orchestration
- Uses MarketplaceConnectorFactory for connector instantiation
- Uses MarketplaceBusinessRules for validation
- Uses Event Bus for asynchronous coordination

**Key Methods**:
- `create_connection()` - Create marketplace connection
- `test_connection()` - Test marketplace connection and credentials
- `sync_assets_to_marketplace()` - PUSH sync (Hub → Marketplace)
- `sync_assets_from_marketplace()` - PULL sync (Marketplace → Hub)
- `create_sync_job()` - Create scheduled sync job
- `get_sync_status()` - Get sync job status and progress

**Example**:
```python
from hub.apps.integrations.services import MarketplaceIntegrationService

service = MarketplaceIntegrationService(tenant_id=tenant_id, user_id=user_id)
connection = service.create_connection(
    marketplace_type="CKAN",
    name="My CKAN Connection",
    config={"url": "https://example.com", "api_key": "..."}
)
sync_result = service.sync_assets_to_marketplace(
    connection_id=connection.id,
    asset_ids=[asset_id1, asset_id2]
)
```

---

## Workflow Integration

### Workflow Engine

All multi-step operations are orchestrated through the workflow engine:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
instance = engine.create_instance(
    workflow_name="asset_creation",
    input_data={"asset_id": "..."},
    tenant_id="...",
)
engine.start_instance(instance.id)
```

### Extended Workflows

#### AssetCreationWorkflow (Extended)

**New Steps**:
- AI schema matching
- Auto-classification
- ML-based quality checks

**DSL Example**:
```json
{
  "version": "1.0.0",
  "steps": [
    {"name": "create_asset", "type": "task", "task": "asset_creation.create_asset"},
    {"name": "ai_schema_matching", "type": "task", "task": "ai.schema_matching"},
    {"name": "auto_classification", "type": "task", "task": "ai.auto_classification"},
    {"name": "ml_quality_check", "type": "task", "task": "ai.ml_quality_check"}
  ]
}
```

#### TransformationPipelineWorkflow

**Steps**:
- Pipeline validation
- Pipeline execution
- Result synchronization
- Compensation on failure

#### MarketplacePublishingWorkflow

**Steps**:
- Transformation validation
- Quality check
- Pricing validation
- Listing creation

#### SocialFeatureWorkflow

**Steps**:
- Review validation
- Asset quality score update
- Notification

#### DataMeshWorkflow

**Steps**:
- Domain creation
- Asset ownership update
- Policy application

#### ProductCreationWorkflow ✅ (Implemented - ODPS Integration)

**Location**: `hub/apps/orchestration/workflows/product_creation.py`
**Status**: ✅ Implemented
**Phase**: ODPS Integration

**Steps**:
1. Parse ODPS document, validate schema, detect version
2. Resolve `$ref` references (internal, local, external)
3. Extract ODCS from `product.contract` (required)
4. Validate extracted ODCS contract
5. Normalize ODCS → HubContract (technical)
6. Normalize ODPS → HubContract (marketplace)
7. Create ODCS contract record
8. Create ODPS contract record
9. Link contracts bidirectionally (ODPS ↔ ODCS)
10. Index for search (ODPS product + ODCS technical)
11. Generate semantic mapping (RDF)

**Compensation Logic**: Each step has compensation handlers for rollback on failure.

**DSL Example**:
```json
{
  "version": "1.0.0",
  "steps": [
    {"name": "parse_odps", "type": "task", "task": "product_creation.parse_odps"},
    {"name": "resolve_refs", "type": "task", "task": "product_creation.resolve_refs"},
    {"name": "extract_contract", "type": "task", "task": "product_creation.extract_contract"},
    {"name": "validate_odcs", "type": "task", "task": "product_creation.validate_odcs"},
    {"name": "normalize_odcs", "type": "task", "task": "product_creation.normalize_odcs", "compensation": {"type": "task", "task": "product_creation.rollback_normalize_odcs"}},
    {"name": "normalize_odps", "type": "task", "task": "product_creation.normalize_odps", "compensation": {"type": "task", "task": "product_creation.rollback_normalize_odps"}},
    {"name": "create_odcs_contract", "type": "task", "task": "product_creation.create_odcs_contract", "compensation": {"type": "task", "task": "product_creation.rollback_odcs_contract"}},
    {"name": "create_odps_contract", "type": "task", "task": "product_creation.create_odps_contract", "compensation": {"type": "task", "task": "product_creation.rollback_odps_contract"}},
    {"name": "link_contracts", "type": "task", "task": "product_creation.link_contracts", "compensation": {"type": "task", "task": "product_creation.rollback_link_contracts"}},
    {"name": "index_for_search", "type": "task", "task": "product_creation.index_for_search"},
    {"name": "semantic_mapping", "type": "task", "task": "product_creation.semantic_mapping"}
  ]
}
```

#### MarketplaceSyncWorkflow ✅ (Implemented - Marketplace Integration Framework)

**Location**: `hub/apps/orchestration/workflows/marketplace_sync.py`
**Status**: ✅ Implemented
**Phase**: Marketplace Integration Framework

**PUSH Sync Steps** (Hub → Marketplace):
1. Validate assets (ACTIVE status, valid contracts)
2. Get marketplace connector from factory
3. Transform HubContract to marketplace format (ODPS)
4. Publish listings to marketplace via connector
5. Create MarketplaceMapping records

**PULL Sync Steps** (Marketplace → Hub):
1. Get marketplace connector from factory
2. Discover marketplace listings via connector
3. Transform marketplace format to HubContract
4. Create assets using AssetCreationWorkflow
5. Create MarketplaceMapping records

**Compensation Logic**: Each step has compensation handlers for rollback on failure.

---

## Event-Driven Coordination

### Event Publishers

Services publish events for asynchronous coordination:

```python
from hub.apps.core.events.service_publishers import EventPublisher

class TransformationEventPublisher(EventPublisher):
    def publish_pipeline_completed(self, pipeline_id: str, result: dict):
        self.publish(
            event_type="transformation.pipeline_completed",
            data={"pipeline_id": pipeline_id, "result": result}
        )
```

### Event Handlers

Event handlers subscribe to events and trigger workflows:

```python
@event_handler("transformation.pipeline_completed")
def handle_pipeline_completed(event):
    # Update asset with pipeline results
    # Trigger asset update workflow
    pass
```

### Event Types

#### Transformation Events
- `transformation.pipeline_started`
- `transformation.pipeline_completed`
- `transformation.pipeline_failed`

#### AI/ML Events
- `ai.schema_matching_completed`
- `ai.classification_completed`
- `ai.recommendation_updated`

#### Social Events
- `social.review_created`
- `social.rating_updated`
- `social.comment_created`

#### Marketplace Events
- `marketplace.purchase_completed`
- `marketplace.pricing_changed`
- `marketplace.listing_updated`

#### Data Mesh Events
- `mesh.domain_created`
- `mesh.policy_applied`
- `mesh.topology_updated`

#### ODPS Events ✅ (Implemented - ODPS Integration)
- `odps.created` - ODPS contract created
- `odps.updated` - ODPS contract updated
- `odps.deleted` - ODPS contract deleted
- `odps.normalized` - ODPS contract normalized
- `odps.linked` - ODPS contract linked to ODCS
- `odps.unlinked` - ODPS contract unlinked from ODCS
- `odps.ref.resolved` - ODPS $ref resolution completed
- `odps.ref.failed` - ODPS $ref resolution failed
- `odps.export.started` - ODPS export started
- `odps.export.completed` - ODPS export completed
- `odps.export.failed` - ODPS export failed
- `odps.workflow.started` - ODPS workflow started
- `odps.workflow.completed` - ODPS workflow completed
- `odps.workflow.failed` - ODPS workflow failed
- `odps.workflow.progress` - ODPS workflow progress update
- `odps.creation.progress` - ODPS creation progress update
- `odps.normalization.progress` - ODPS normalization progress update
- `odps.ref.progress` - ODPS $ref resolution progress update

#### Marketplace Integration Events ✅ (Implemented - Marketplace Integration Framework)
- `marketplace.connection.created` - Marketplace connection created
- `marketplace.connection.updated` - Marketplace connection updated
- `marketplace.connection.deleted` - Marketplace connection deleted
- `marketplace.connection.tested` - Marketplace connection tested
- `marketplace.sync.started` - Marketplace sync started
- `marketplace.sync.completed` - Marketplace sync completed
- `marketplace.sync.failed` - Marketplace sync failed
- `marketplace.sync.progress` - Marketplace sync progress update
- `marketplace.mapping.created` - Marketplace mapping created
- `marketplace.mapping.updated` - Marketplace mapping updated
- `marketplace.mapping.deleted` - Marketplace mapping deleted

---

## Business Rules Framework ✅ (Implemented - Phase 9.7.2)

### Overview

The Business Rules Framework provides a standardized approach to validation and business logic enforcement across all services. All business rules classes follow consistent patterns for validation, error handling, and result reporting.

**Status**: ✅ Implemented (Phase 9.7.2)
**Location**: `hub/apps/core/business_rules/`
**Documentation**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`

### Framework Architecture

The framework consists of three main components:

1. **Base Classes** (`hub/apps/core/business_rules/base.py`)
   - `BusinessRules` - Abstract base class for all business rules
   - `ValidationResult` - Standardized validation result structure
   - `RuleExecutionContext` - Context for rule execution

2. **Common Utilities** (`hub/apps/core/business_rules/utils.py`)
   - Shared validation utilities
   - Tenant ID validation
   - User permission checking
   - Cross-tenant access validation
   - Schema structure validation

3. **Registry** (`hub/apps/core/business_rules/registry.py`)
   - Business rules registration
   - Rule discovery and loading
   - Rule execution coordination
   - Metrics and monitoring

### Framework Components

#### Base Class

**Location**: `hub/apps/core/business_rules/base.py`

The `BusinessRules` abstract base class provides:
- Standardized initialization with `tenant_id` and `user_id`
- Common validation patterns
- Error handling utilities
- Result creation helpers
- Tenant context validation

```python
from hub.apps.core.business_rules.base import BusinessRules, ValidationResult, RuleExecutionContext
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Standardized validation result structure."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

class BusinessRules(ABC):
    """Abstract base class for all business rules implementations."""

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @abstractmethod
    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """Main validation method (to be implemented by subclasses)."""
        pass

    def _create_result(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Helper method to create ValidationResult."""
        return ValidationResult(
            is_valid=is_valid,
            errors=errors or [],
            warnings=warnings or [],
            details=details or {}
        )

    def _validate_tenant_context(
        self,
        entity_tenant_id: Optional[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Validate tenant context consistency."""
        errors = []
        if self.tenant_id and entity_tenant_id:
            if str(entity_tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Tenant mismatch: entity tenant ({entity_tenant_id}) "
                    f"does not match context tenant ({self.tenant_id})"
                )
        return errors
```

**Example Implementation**:
```python
from hub.apps.core.business_rules.base import BusinessRules, ValidationResult

class TransformationBusinessRules(BusinessRules):
    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """Main validation method"""
        pipeline = kwargs.get('pipeline')
        asset = kwargs.get('asset')

        errors = []
        warnings = []
        details = {}

        # Validate schema compatibility
        schema_result = self.validate_schema_alignment(pipeline, asset)
        if not schema_result.is_valid:
            errors.extend(schema_result.errors)
            details['schema_validation'] = schema_result.details

        # Validate data type compatibility
        type_result = self.validate_data_type_compatibility(pipeline, asset)
        if not type_result.is_valid:
            errors.extend(type_result.errors)
            details['type_validation'] = type_result.details

        result = self._create_result(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if kwargs.get('raise_on_error', False) and not result.is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(result.errors)

        return result
```

#### ValidationResult Pattern

All business rules return a standardized `ValidationResult`:

```python
@dataclass
class ValidationResult:
    """Standardized validation result structure."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]
```

**Usage**:
```python
result = rules.validate(pipeline=pipeline, asset=asset)
if result.is_valid:
    # Proceed with operation
    proceed_with_operation()
else:
    # Handle errors
    for error in result.errors:
        logger.error(f"Validation error: {error}")
    # Check warnings
    for warning in result.warnings:
        logger.warning(f"Validation warning: {warning}")
    # Access detailed validation information
    schema_details = result.details.get('schema_validation', {})
```

**ValidationResult Features**:
- **Boolean evaluation**: `if result:` checks `is_valid`
- **Error collection**: Comprehensive error messages with context
- **Warning support**: Non-critical issues reported as warnings
- **Details dictionary**: Structured validation details for debugging and metrics
- **Consistent interface**: All business rules return same structure

#### Rule Execution Context

**Location**: `hub/apps/core/business_rules/base.py`

The `RuleExecutionContext` provides context for rule execution:

```python
@dataclass
class RuleExecutionContext:
    """Context for business rule execution."""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    resource: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        return {
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'resource_id': str(self.resource.id) if self.resource and hasattr(self.resource, 'id') else None,
            'metadata': self.metadata or {}
        }
```

**Extended Contexts**:
- `TransformationRuleExecutionContext` - Adds `pipeline`, `source_asset`, `target_asset`
- `DataMeshRuleExecutionContext` - Adds `domain`, `asset`
- `VirtualizationRuleExecutionContext` - Adds `virtual_dataset`, `query`

#### Framework Registry

**Location**: `hub/apps/core/business_rules/registry.py`

The registry provides:
- Rule registration and discovery
- Rule metadata management
- Metrics collection
- Rule execution coordination

**Registration**:
```python
from hub.apps.core.business_rules.registry import register_rule

@register_rule(
    rule_name="transformation_pipeline_validation",
    description="Validates transformation pipeline structure and compatibility",
    tags=["transformation", "pipeline", "validation"],
    priority=10
)
class TransformationBusinessRules(BusinessRules):
    # Implementation
    pass
```

**Discovery**:
```python
from hub.apps.core.business_rules.registry import BusinessRulesRegistry

registry = BusinessRulesRegistry()
rule_metadata = registry.get_rule("transformation_pipeline_validation")
rules = rule_metadata.rule_class(tenant_id=tenant_id, user_id=user_id)
```

**Registry Features**:
- Automatic rule discovery via decorator
- Rule metadata storage (name, description, tags, priority)
- Rule lookup by name or tags
- Metrics collection per rule
- Rule execution tracking

### Business Rules Implementations

#### Transformation Business Rules ✅ (Implemented - Phase 9.5.1)

**Location**: `hub/apps/transformation/business_rules.py`
**Class**: `TransformationBusinessRules`
**Registry Name**: `transformation_pipeline_validation`
**Phase**: 9.5.1

**Overview**:
The TransformationBusinessRules class provides comprehensive validation for transformation pipelines, ensuring pipeline structure integrity, node compatibility, schema alignment, and asset compatibility before execution.

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all validation checks
   - Accepts `TransformationRuleExecutionContext` or standard context
   - Supports validation type filtering (`structure`, `node_compatibility`, `schema_alignment`, `asset_compatibility`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_pipeline_structure()`** - Pipeline structure validation
   - Validates pipeline definition is valid JSON object
   - Ensures required fields (`version`, `steps`) are present
   - Validates step structure and ordering
   - Checks for duplicate step names
   - Validates node types are valid (`FILTER`, `JOIN`, `AGGREGATE`, `TRANSFORM`, `OUTPUT`)
   - Enforces node execution order constraints (e.g., `AGGREGATE` must come after `FILTER`)

3. **`validate_node_compatibility()`** - Node compatibility validation
   - Validates node dependencies are satisfied
   - Ensures required fields per node type are present
   - Validates node configuration structure
   - Checks node execution order constraints

4. **`validate_schema_alignment()`** - Schema alignment validation
   - Validates pipeline input/output schemas align with asset schemas
   - Checks data type compatibility
   - Validates field mappings
   - Ensures schema transformations are valid

5. **`validate_asset_compatibility()`** - Asset compatibility validation
   - Validates source asset compatibility with pipeline
   - Validates target asset compatibility (if specified)
   - Checks asset data types match pipeline requirements
   - Validates asset status allows pipeline execution

6. **`validate_cross_tenant_operations()`** - Cross-tenant validation
   - Ensures tenant isolation
   - Validates cross-tenant operation permissions
   - Checks tenant context consistency

7. **`validate_resource_quota()`** - Resource quota validation
   - Validates pipeline resource requirements
   - Checks tenant resource quotas
   - Ensures sufficient resources available

8. **`validate_pipeline_execution_permission()`** - Permission validation
   - Validates user permissions for pipeline execution
   - Checks pipeline ownership
   - Validates execution context

**Node Type Constraints**:
- **FILTER**: Can be first node, no dependencies
- **JOIN**: Requires FILTER nodes before it
- **AGGREGATE**: Requires FILTER and/or JOIN nodes before it
- **TRANSFORM**: Can come after FILTER, JOIN, or AGGREGATE
- **OUTPUT**: Should be last node, requires all other node types before it

**Required Fields per Node Type**:
- **FILTER**: `filter_expression`
- **JOIN**: `join_keys`, `join_type`
- **AGGREGATE**: `group_by`, `aggregation_functions`
- **TRANSFORM**: `transform_expression`
- **OUTPUT**: No specific required fields

**Example Usage**:
```python
from hub.apps.transformation.business_rules import TransformationBusinessRules
from hub.apps.core.business_rules.base import RuleExecutionContext

# Initialize rules
rules = TransformationBusinessRules(tenant_id=tenant_id, user_id=user_id)

# Validate pipeline structure
structure_result = rules.validate_pipeline_structure(pipeline, raise_on_error=False)
if not structure_result.is_valid:
    for error in structure_result.errors:
        logger.error(f"Pipeline structure error: {error}")

# Validate pipeline compatibility with assets
compatibility_result = rules.validate_pipeline_compatibility(
    pipeline=pipeline,
    source_asset=source_asset,
    target_asset=target_asset,
    raise_on_error=True
)

# Full validation with context
context = TransformationRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    pipeline=pipeline,
    source_asset=source_asset,
    target_asset=target_asset
)
result = rules.validate(context=context, validation_type='all')
```

**Integration Points**:
- Used by `TransformationService` for pipeline validation before execution
- Integrated with `TransformationPipelineWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

#### Data Mesh Business Rules ✅ (Implemented - Phase 9.5.2)

**Location**: `hub/apps/mesh/business_rules.py`
**Classes**: `DataMeshBusinessRules`, `PolicyBusinessRules`, `TopologyBusinessRules`
**Registry Names**: `data_mesh_domain_validation`, `policy_validation`, `topology_calculation`
**Phase**: 9.5.2

**Overview**:
The Data Mesh business rules provide comprehensive validation for data mesh domains, including domain structure, ownership transfer, boundaries, policy conflicts, and topology calculations.

##### DataMeshBusinessRules

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all domain validation checks
   - Accepts `DataMeshRuleExecutionContext` or standard context
   - Supports validation type filtering (`structure`, `ownership`, `boundaries`, `policy_conflicts`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_domain_structure()`** - Domain structure validation
   - Validates domain name is present and non-empty
   - Ensures domain has valid tenant assignment
   - Validates boundaries structure (if present)
   - Validates capabilities structure (if present)
   - Validates resource_quota and resource_usage structures
   - Ensures owner belongs to same tenant as domain
   - Validates domain status is valid

3. **`validate_ownership_transfer()`** - Ownership transfer validation
   - Validates new owner exists (if provided)
   - Ensures new owner belongs to same tenant as domain
   - Validates transfer permissions
   - Checks for active dependencies that prevent transfer

4. **`validate_boundaries()`** - Domain boundaries validation
   - Validates boundaries structure is valid dictionary
   - Ensures boundary definitions are complete
   - Validates boundary constraints are consistent

5. **`validate_domain_boundary_definition()`** - Boundary definition validation
   - Validates boundary structure and constraints
   - Ensures boundary definitions are complete and consistent

6. **`validate_asset_domain_boundary()`** - Asset boundary validation
   - Validates asset placement within domain boundaries
   - Ensures asset meets boundary constraints
   - Checks asset compatibility with domain

7. **`validate_cross_domain_access()`** - Cross-domain access validation
   - Validates cross-domain access permissions
   - Checks domain access policies
   - Ensures tenant isolation

8. **`validate_domain_resource_quota()`** - Resource quota validation
   - Validates domain resource quotas
   - Checks resource usage against quotas
   - Ensures sufficient resources available

9. **`validate_domain_ownership()`** - Domain ownership validation
   - Validates domain ownership structure
   - Checks owner permissions
   - Ensures ownership consistency

10. **`validate_asset_ownership_transfer()`** - Asset ownership transfer validation
    - Validates asset ownership transfer operations
    - Checks transfer permissions
    - Validates source and target domains
    - Ensures transfer constraints are met

11. **`validate_policy_conflicts()`** - Policy conflict detection
    - Detects conflicting policies within domain
    - Identifies policy incompatibilities
    - Reports conflict details

12. **`validate_policy_compatibility()`** - Policy compatibility validation
    - Validates policy compatibility with domain
    - Checks policy constraints
    - Ensures policy consistency

**Example Usage**:
```python
from hub.apps.mesh.business_rules import DataMeshBusinessRules, PolicyBusinessRules
from hub.apps.core.business_rules.base import RuleExecutionContext

# Initialize rules
mesh_rules = DataMeshBusinessRules(tenant_id=tenant_id, user_id=user_id)

# Validate domain structure
structure_result = mesh_rules.validate_domain_structure(domain, raise_on_error=False)
if not structure_result.is_valid:
    for error in structure_result.errors:
        logger.error(f"Domain structure error: {error}")

# Validate ownership transfer
transfer_result = mesh_rules.validate_ownership_transfer(
    domain=domain,
    new_owner_id=new_owner_id,
    raise_on_error=True
)

# Validate boundaries
boundaries_result = mesh_rules.validate_boundaries(domain.boundaries)
if not boundaries_result.is_valid:
    raise ValidationError(boundaries_result.errors)

# Full validation with context
context = DataMeshRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    domain=domain,
    asset=asset
)
result = mesh_rules.validate(context=context, validation_type='all')
```

##### PolicyBusinessRules

**Validation Methods**:
- **`validate_policy_application()`** - Policy application validation
  - Validates policy can be applied to domain/asset
  - Checks policy constraints
  - Ensures policy compatibility
  - Validates policy permissions

**Example Usage**:
```python
from hub.apps.mesh.business_rules import PolicyBusinessRules

policy_rules = PolicyBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = policy_rules.validate_policy_application(
    policy=policy,
    domain=domain,
    raise_on_error=True
)
```

##### TopologyBusinessRules

**Methods**:
- **Relationship calculation** - Calculates domain relationships
- **Health metrics calculation** - Calculates domain health metrics

**Integration Points**:
- Used by `DataMeshService` for domain validation before operations
- Integrated with `DataMeshWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

#### Virtualization Business Rules ✅ (Implemented - Phase 9.5.3)

**Location**: `hub/apps/virtualization/business_rules.py`
**Classes**: `VirtualizationBusinessRules`, `QueryExecutionBusinessRules`, `ResultBusinessRules`
**Registry Name**: `virtualization_dataset_validation`
**Phase**: 9.5.3

**Overview**:
The Virtualization business rules provide comprehensive validation for virtual datasets, including query syntax validation, schema alignment, source compatibility, and query execution validation.

##### VirtualizationBusinessRules

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all virtualization validation checks
   - Accepts `VirtualizationRuleExecutionContext` or standard context
   - Supports validation type filtering (`query_syntax`, `schema_alignment`, `source_compatibility`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_query_syntax()`** - Query syntax validation
   - Validates query is not empty
   - Validates query contains required keywords for query type
   - Ensures query does not contain forbidden keywords (write operations)
   - Validates query structure is valid for query type
   - Supports SQL, SPARQL, REST, GraphQL, and Federated query types

3. **`validate_source_configuration()`** - Source configuration validation
   - Validates source configuration structure
   - Ensures source connection parameters are valid
   - Validates source credentials (if applicable)
   - Checks source availability

4. **`validate_query_mapping()`** - Query mapping validation
   - Validates query-to-source mapping is correct
   - Ensures query fields map to source fields
   - Validates mapping consistency

5. **`validate_caching_configuration()`** - Caching configuration validation
   - Validates cache configuration structure
   - Ensures cache parameters are valid
   - Checks cache compatibility with query type

6. **`validate_virtual_dataset_schema()`** - Virtual dataset schema validation
   - Validates virtual dataset schema structure
   - Ensures schema is complete and consistent
   - Validates schema compatibility with sources

7. **`validate_schema_alignment()`** - Schema alignment validation
   - Validates schema alignment across sources
   - Checks field mappings are consistent
   - Ensures data type compatibility
   - Validates schema transformations

8. **`validate_source_compatibility()`** - Source compatibility validation
   - Validates source compatibility with query type
   - Checks source supports required query language
   - Ensures source capabilities match requirements

9. **`validate_cross_source_compatibility()`** - Cross-source compatibility validation
   - Validates multiple sources are compatible
   - Checks source schemas can be aligned
   - Ensures federated query feasibility

10. **`validate_cross_tenant_access()`** - Cross-tenant access validation
    - Validates cross-tenant access permissions
    - Ensures tenant isolation
    - Checks access policies

11. **`validate_query_language_compatibility()`** - Query language compatibility validation
    - Validates query language is compatible with sources
    - Checks language support per source
    - Ensures language consistency

12. **`validate_source_connections()`** - Source connection validation
    - Validates source connection configurations
    - Checks connection parameters
    - Ensures connection security

**Query Type Support**:
- **SQL**: PostgreSQL, MySQL, SQL Server, MSSQL sources
- **SPARQL**: SPARQL endpoints
- **REST**: REST API sources
- **GraphQL**: GraphQL API sources
- **FEDERATED**: Multiple source types combined

**Forbidden Keywords** (Write Operations):
- **SQL**: `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `CREATE TABLE`, `CREATE DATABASE`, `CREATE SCHEMA`, `DROP TABLE`, `DROP DATABASE`
- **SPARQL**: `INSERT`, `DELETE`, `DROP`, `CREATE`, `LOAD`, `CLEAR`

**Required Keywords**:
- **SQL**: At least one of `SELECT`, `WITH`, `INSERT`, `UPDATE`
- **SPARQL**: At least one of `SELECT`, `CONSTRUCT`, `ASK`, `DESCRIBE`, `PREFIX`

**Example Usage**:
```python
from hub.apps.virtualization.business_rules import VirtualizationBusinessRules
from hub.apps.virtualization.models import QueryType
from hub.apps.core.business_rules.base import RuleExecutionContext

# Initialize rules
rules = VirtualizationBusinessRules(tenant_id=tenant_id, user_id=user_id)

# Validate query syntax
query_result = rules.validate_query_syntax(
    query=query_string,
    query_type=QueryType.SQL,
    raise_on_error=False
)
if not query_result.is_valid:
    for error in query_result.errors:
        logger.error(f"Query syntax error: {error}")

# Validate schema alignment
schema_result = rules.validate_schema_alignment(
    virtual_dataset=virtual_dataset,
    sources=sources,
    raise_on_error=True
)

# Full validation with context
context = VirtualizationRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    virtual_dataset=virtual_dataset,
    query=query_string
)
result = rules.validate(context=context, validation_type='all')
```

##### QueryExecutionBusinessRules

**Methods**:
- **`validate_timeout()`** - Query timeout validation
  - Validates timeout configuration
  - Ensures timeout values are reasonable
  - Checks timeout compatibility with query type
- **Query optimization** - Optimizes query execution
- **Execution mode selection** - Selects SYNC vs ASYNC execution mode

**Example Usage**:
```python
from hub.apps.virtualization.business_rules import QueryExecutionBusinessRules

execution_rules = QueryExecutionBusinessRules()
timeout_result = execution_rules.validate_timeout(
    timeout_seconds=300,
    query_type=QueryType.SQL,
    raise_on_error=True
)
```

##### ResultBusinessRules

**Methods**:
- **`validate_result_caching()`** - Result caching validation
  - Validates cache configuration
  - Ensures cache parameters are valid
  - Checks cache compatibility
- **`validate_pagination()`** - Pagination validation
  - Validates pagination parameters
  - Ensures pagination is consistent
  - Checks pagination limits

**Example Usage**:
```python
from hub.apps.virtualization.business_rules import ResultBusinessRules

result_rules = ResultBusinessRules()
cache_result = result_rules.validate_result_caching(
    cache_config=cache_config,
    raise_on_error=True
)
```

**Integration Points**:
- Used by `VirtualizationService` for virtual dataset validation before operations
- Integrated with `VirtualizationWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

#### ODPS Business Rules ✅ (Implemented - ODPS Integration)

**Location**: `hub/apps/contracts/business_rules.py`
**Classes**: `ODPSBusinessRules`, `ODPSLinkingRules`, `ODPSExportRules`
**Registry Names**: `odps_document_validation`, `odps_linking_validation`, `odps_export_validation`
**Phase**: ODPS Integration

**Overview**:
The ODPS business rules provide comprehensive validation for ODPS documents, including document structure validation, version validation, linking validation, and export validation.

##### ODPSBusinessRules

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all ODPS validation checks
   - Accepts ODPS document and context
   - Supports validation type filtering (`structure`, `version`, `linking`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_odps_structure()`** - ODPS document structure validation
   - Validates ODPS document is valid JSON/YAML
   - Ensures required fields (`schema`, `version`, `product`) are present
   - Validates product structure (details, contract, pricing, access)
   - Checks for required product fields (productID, name)

3. **`validate_odps_version()`** - ODPS version validation
   - Validates ODPS version is supported (4.1, 4.0, 3.x, 2.x)
   - Checks version compatibility
   - Validates version-specific fields

4. **`validate_odps_contract_field()`** - Contract field validation
   - Validates `product.contract` field structure
   - Ensures contract spec is present (for Product-First flow)
   - Validates contract reference structure (for Link flow)

5. **`validate_odps_pricing()`** - Pricing validation
   - Validates pricing plans structure
   - Ensures pricing fields are valid
   - Checks pricing plan compatibility

6. **`validate_odps_access_methods()`** - Access methods validation
   - Validates access methods structure
   - Ensures access method fields are valid
   - Checks access method compatibility

**Example Usage**:
```python
from hub.apps.contracts.business_rules import ODPSBusinessRules

rules = ODPSBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = rules.validate_odps_structure(
    odps_document=odps_document,
    raise_on_error=False
)
if not result.is_valid:
    for error in result.errors:
        logger.error(f"ODPS structure error: {error}")
```

##### ODPSLinkingRules

**Validation Methods**:
- **`validate_linking()`** - Link validation
  - Validates ODPS can be linked to ODCS contract
  - Checks contract compatibility
  - Ensures tenant access permissions
  - Detects circular references

**Example Usage**:
```python
from hub.apps.contracts.business_rules import ODPSLinkingRules

linking_rules = ODPSLinkingRules(tenant_id=tenant_id, user_id=user_id)
result = linking_rules.validate_linking(
    odps_contract=odps_contract,
    odcs_contract=odcs_contract,
    raise_on_error=True
)
```

##### ODPSExportRules

**Validation Methods**:
- **`validate_export_format()`** - Export format validation
  - Validates export format (JSON, YAML)
  - Checks format compatibility
- **`validate_export_fidelity()`** - Export fidelity validation
  - Validates exported ODPS matches original
  - Checks field preservation

**Integration Points**:
- Used by `ODPSService` for ODPS validation before operations
- Integrated with `ProductCreationWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

### Rule Validation in Service Layer

Rules are validated in service layer:

```python
from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.business_rules import TransformationBusinessRules

class TransformationService(BaseService):
    def execute_pipeline(self, pipeline_id: str, asset_id: str):
        pipeline = self.get_resource_or_raise(Pipeline, pipeline_id)
        asset = self.get_resource_or_raise(Asset, asset_id)

        # Validate using business rules
        rules = TransformationBusinessRules(
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )
        validation = rules.validate_pipeline_compatibility(pipeline, asset, raise_on_error=True)

        # Execute pipeline
        # Publish events
        pass
```

### Common Patterns

#### 1. Initialization Pattern

All business rules accept `tenant_id` and `user_id` during initialization:

```python
rules = TransformationBusinessRules(
    tenant_id=tenant_id,
    user_id=user_id
)
```

#### 2. Validation Method Pattern

All validation methods:
- Return `ValidationResult`
- Support `raise_on_error` parameter (default: `False`)
- Collect errors and warnings in lists
- Provide detailed context in `details` dictionary
- Raise exceptions when `raise_on_error=True` and validation fails

```python
result = rules.validate_pipeline_structure(
    pipeline=pipeline,
    raise_on_error=False
)
if not result.is_valid:
    # Handle errors
    pass
```

#### 3. Error Handling Pattern

Consistent use of `ValidationError` from `hub.apps.core.services.base`:

```python
from hub.apps.core.services.base import ValidationError

if raise_on_error and not result.is_valid:
    raise ValidationError(
        "; ".join(result.errors),
        code="VALIDATION_FAILED",
        details=result.details
    )
```

#### 4. Error Message Pattern

Comprehensive context in error messages and `details` dictionary:

```python
errors.append(
    f"Pipeline structure validation failed: "
    f"pipeline_id={pipeline.id}, "
    f"missing_fields={missing_fields}, "
    f"validation_type='structure'"
)
details.update({
    "pipeline_id": str(pipeline.id),
    "pipeline_name": pipeline.name,
    "validation_checks": validation_checks,
    "missing_fields": missing_fields
})
```

#### 5. Context Pattern

Use `RuleExecutionContext` for complex validations:

```python
context = TransformationRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    pipeline=pipeline,
    source_asset=source_asset,
    target_asset=target_asset
)
result = rules.validate(context=context, validation_type='all')
```

#### 6. Registry Pattern

Register rules with metadata for discovery and metrics:

```python
@register_rule(
    rule_name="transformation_pipeline_validation",
    description="Validates transformation pipeline structure and compatibility",
    tags=["transformation", "pipeline", "validation"],
    priority=10
)
class TransformationBusinessRules(BusinessRules):
    pass
```

### Framework Benefits (Phase 9.7.2)

The framework standardization (Phase 9.7.2) provides:

1. **Consistency**: All business rules follow same patterns
2. **Maintainability**: Centralized base classes and utilities
3. **Discoverability**: Registry enables rule discovery
4. **Testability**: Standardized interfaces enable comprehensive testing
5. **Metrics**: Built-in metrics collection per rule
6. **Documentation**: Standardized patterns enable better documentation
7. **Extensibility**: Easy to add new business rules following patterns

### Framework Implementation Status

**Phase 9.7.2 Implementation**:
- ✅ Base class (`BusinessRules`) implemented
- ✅ `ValidationResult` standardized
- ✅ `RuleExecutionContext` implemented
- ✅ Common utilities created
- ✅ Registry implemented
- ✅ All existing business rules migrated to framework
- ✅ Framework documentation created
- ✅ Framework review completed

**Business Rules Using Framework**:
- ✅ TransformationBusinessRules (Phase 9.5.1)
- ✅ DataMeshBusinessRules (Phase 9.5.2)
- ✅ VirtualizationBusinessRules (Phase 9.5.3)
- ✅ ContractsBusinessRules (MVP)
- ✅ AssetsBusinessRules (MVP)
- ✅ DatasetsBusinessRules (MVP)
- ✅ MarketplaceBusinessRules (MVP)
- ✅ ODPSBusinessRules (ODPS Integration)
- ✅ ODPSLinkingRules (ODPS Integration)
- ✅ ODPSExportRules (ODPS Integration)
- ✅ And 20+ other business rules classes

### Documentation

- **Framework Review**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`
- **Integration Guide**: This document
- **Framework Base**: `hub/apps/core/business_rules/base.py`
- **Framework Registry**: `hub/apps/core/business_rules/registry.py`
- **Framework Utilities**: `hub/apps/core/business_rules/utils.py`

---

## Compensation Logic

### Compensation Pattern (Saga)

Workflows define compensation for rollback:

```json
{
  "version": "1.0.0",
  "compensation": {"enabled": true},
  "steps": [
    {
      "name": "create_resource",
      "type": "task",
      "task": "create_resource_task",
      "compensation": {
        "type": "task",
        "task": "delete_resource_task"
      }
    }
  ]
}
```

### Compensation Execution

Compensation is executed automatically on failure:

```python
# Workflow engine automatically executes compensation
# when a step fails and compensation is enabled
```

### ODPS Compensation Logic ✅ (Implemented - ODPS Integration)

**Location**: `hub/apps/contracts/odps_compensation.py`
**Status**: ✅ Implemented
**Phase**: ODPS Integration

**ODPSCreationCompensation**:
- **Purpose**: Handles rollback for ODPS creation operations
- **Compensation Steps**:
  - Rollback created ODPS contract
  - Rollback created ODCS contract (if created)
  - Remove bidirectional links
  - Cleanup search index entries
  - Rollback semantic mappings

**Compensation Triggers**:
- Normalization failure after contract creation
- Linking failure after contract creation
- Search indexing failure
- Semantic mapping failure

**Example**:
```python
from hub.apps.contracts.odps_compensation import ODPSCreationCompensation, ODPSCreationState

compensation = ODPSCreationCompensation(tenant_id=tenant_id, user_id=user_id)
state = ODPSCreationState(asset_id=asset_id)

try:
    # Create ODPS contract
    contract = service.create_odps(...)
    state.odps_contract_id = contract.id
except Exception as e:
    # Compensation automatically executed
    compensation.rollback(state)
    raise
```

**ProductCreationWorkflow Compensation**:
- Each workflow step has compensation handlers
- Compensation executed in reverse order on failure
- State tracked in workflow instance state_data
- Compensation handlers defined in workflow DSL

---

## Data Consistency

### Consistency Service

```python
from hub.apps.core.consistency.service import ConsistencyService

class ConsistencyService:
    def maintain_transformation_asset_consistency(self, pipeline_id: str, asset_id: str):
        # Sync pipeline results with asset
        # Validate consistency
        # Report inconsistencies
        pass
```

### Event-Driven Consistency

Consistency is maintained through event handlers:

```python
@event_handler("transformation.pipeline_completed")
def maintain_consistency(event):
    consistency_service = ConsistencyService()
    consistency_service.maintain_transformation_asset_consistency(
        event.data["pipeline_id"],
        event.data["asset_id"]
    )
```

### Scheduled Consistency Checks

```python
# Scheduled job runs consistency checks
@periodic_task(run_every=timedelta(hours=1))
def check_consistency():
    consistency_service = ConsistencyService()
    consistency_service.validate_all_consistency()
```

---

## Frontend Integration

### Workflow Progress Tracking

Frontend tracks workflow progress via React Query and WebSocket:

```typescript
import { useWorkflowProgress } from '@/hooks/useWorkflowProgress';

function TransformationPipelineProgress({ pipelineId }: { pipelineId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'transformation_pipeline',
    pipelineId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

### State Synchronization

Frontend state is synchronized with backend via WebSocket:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function useWorkflowUpdates(workflowName: string, instanceId: string) {
  const { data, queryClient } = useWebSocket(`workflow.${workflowName}.${instanceId}`);

  useEffect(() => {
    if (data) {
      queryClient.setQueryData(
        ['workflow', workflowName, instanceId],
        data
      );
    }
  }, [data, workflowName, instanceId, queryClient]);
}
```

---

## Service Integration Patterns ✅ (Implemented - Phase 9.7.3)

### Overview

Service integration patterns define standard approaches for service-to-service communication in the Data Interoperability Hub. These patterns ensure reliable, scalable, and maintainable inter-service coordination.

**Status**: ✅ Implemented (Phase 9.7.3)
**Documentation**: `docs/SERVICE_INTEGRATION_PATTERNS.md`

### Pattern 1: Direct Service Calls (Synchronous) ✅

**When to Use**:
- Simple operations requiring immediate response
- Real-time validation or data retrieval
- Low latency requirements (< 1 second)
- Strong consistency required
- Simple request-response interactions

**Implementation**:
- All service clients follow consistent pattern with:
  - HTTP client (httpx) with connection pooling
  - Retry logic with exponential backoff
  - Circuit breaker for fault tolerance
  - Distributed tracing support
  - Health check capabilities

**Service Clients**:
- `ComplianceServiceClient` (`hub/apps/compliance/service_client.py`)
- `DQServiceClient` (`hub/apps/dq/service_client.py`)
- `SemanticServiceClient` (`hub/apps/semantic/service_client.py`)
- `DataContractCLIClient` (`hub/apps/contracts/cli_client.py`)
- `WebhookDeliveryClient` (`hub/apps/webhooks/service_client.py`) ✅ New
- `ServiceHealthClient` (`hub/apps/core/services/health_client.py`) ✅ New

**Example**:
```python
from hub.apps.compliance.service_client import ComplianceServiceClient

client = ComplianceServiceClient()
result = client.scan_asset(asset_id=asset_id, tenant_id=tenant_id)
```

### Pattern 2: Event-Driven Coordination (Asynchronous) ✅

**When to Use**:
- Decoupled operations where immediate response not needed
- Eventual consistency acceptable
- High scalability requirements
- Multiple subscribers need to react to same event
- Long-running operations

**Implementation**:
- Redis Pub/Sub for real-time event delivery
- PostgreSQL for event persistence, replay, and audit
- Dead letter queue for failed events
- Event schema validation

**Event Publishers**:
- `TransformationEventPublisher` - Publishes `transformation.*` events
- `DataMeshEventPublisher` - Publishes `mesh.*` events
- `VirtualizationEventPublisher` - Publishes `virtualization.*` events
- `ContractEventPublisher` - Publishes `contract.*` events
- `AssetEventPublisher` - Publishes `asset.*` events

**Example**:
```python
from hub.apps.core.events import EventPublisher

publisher = EventPublisher(
    service_name="transformation_service",
    tenant_id=tenant_id,
    user_id=user_id
)
event_id = publisher.publish(
    event_type="transformation.pipeline.executed",
    data={"pipeline_id": pipeline_id, "result": result}
)
```

### Pattern 3: Workflow Orchestration (Multi-Step) ✅

**When to Use**:
- Complex multi-step operations
- Operations requiring compensation
- Long-running processes
- Operations with dependencies between steps
- Operations requiring state management

**Implementation**:
- Workflow Engine for orchestration
- Workflow DSL for definitions
- Compensation support (Saga pattern)
- State management
- Progress tracking

**Workflows**:
- `TransformationPipelineWorkflow` - Pipeline execution orchestration
- `DataMeshWorkflow` - Domain operations orchestration
- `VirtualizationWorkflow` - Virtual dataset operations orchestration
- `AssetCreationWorkflow` - Asset creation orchestration
- `ContractCreationWorkflow` - Contract creation orchestration

**Example**:
```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
instance = engine.create_instance(
    workflow_name="transformation_pipeline",
    input_data={"pipeline_id": pipeline_id, "asset_id": asset_id},
    tenant_id=tenant_id
)
engine.start_instance(instance.id)
```

### Pattern Selection Criteria

**Use Direct Service Calls when**:
- ✅ Immediate response required
- ✅ Strong consistency needed
- ✅ Simple request-response
- ✅ Low latency critical

**Use Event-Driven when**:
- ✅ Decoupled operations acceptable
- ✅ Eventual consistency acceptable
- ✅ High throughput needed
- ✅ Multiple subscribers

**Use Workflow Orchestration when**:
- ✅ Multi-step operations
- ✅ Compensation needed
- ✅ Long-running processes
- ✅ Complex dependencies

### Anti-Patterns to Avoid

1. **Direct HTTP calls outside service clients** ❌
   - Use service clients with circuit breakers and retry logic
   - Example: Use `WebhookDeliveryClient` instead of `requests.post()`

2. **Synchronous calls in event handlers** ❌
   - Event handlers should be fast and non-blocking
   - Use workflows for complex operations triggered by events

3. **Services not extending BaseService** ❌
   - All business logic services should extend `BaseService`
   - Provides consistent error handling, metrics, tenant scoping

4. **Missing circuit breakers** ❌
   - All service clients must have circuit breakers
   - Prevents cascading failures

5. **Missing retry logic** ❌
   - All service clients must have retry logic
   - Handles transient failures gracefully

### Documentation

- **Full Patterns Documentation**: `docs/SERVICE_INTEGRATION_PATTERNS.md`
- **Audit Report**: `docs/api-audit/SERVICE_INTEGRATION_AUDIT_REPORT.md`
- **Remediation Report**: `docs/api-audit/SERVICE_INTEGRATION_REMEDIATION_COMPLETE.md`

---

## Best Practices

### Service Layer

1. **Single Responsibility**: Each service has a clear responsibility
2. **Dependency Injection**: Services use dependency injection
3. **Event Publishing**: Services publish events for coordination
4. **Error Handling**: Services handle errors consistently
5. **Transaction Management**: Services manage transaction boundaries
6. **BaseService Extension**: All services extend `BaseService` ✅

### Workflow Integration

1. **Workflow DSL**: Use workflow DSL for workflow definitions
2. **Compensation**: Always define compensation for critical operations
3. **State Management**: Use workflow state for multi-step operations
4. **Error Handling**: Handle workflow failures gracefully
5. **Progress Tracking**: Track workflow progress for user experience

### Event-Driven Coordination

1. **Event Schema**: Define event schemas clearly
2. **Event Versioning**: Version events for backward compatibility
3. **Event Correlation**: Track event correlation for debugging
4. **Event Replay**: Support event replay for recovery
5. **Event Monitoring**: Monitor event processing

### Business Rules

1. **Centralized Rules**: Keep rules in centralized framework ✅
2. **Rule Testing**: Test rules independently
3. **Rule Configuration**: Make rules configurable per tenant
4. **Rule Documentation**: Document all business rules ✅
5. **Rule Validation**: Validate rules at service layer ✅
6. **ValidationResult Pattern**: Use standardized ValidationResult ✅

### Service Integration Patterns

1. **Use Service Clients**: Always use service clients for HTTP calls ✅
2. **Circuit Breakers**: All service clients must have circuit breakers ✅
3. **Retry Logic**: All service clients must have retry logic ✅
4. **Distributed Tracing**: Propagate trace headers across service calls ✅
5. **Health Checks**: All service clients must support health checks ✅

### Data Consistency

1. **Eventual Consistency**: Use eventual consistency model
2. **Consistency Validation**: Validate consistency regularly
3. **Consistency Metrics**: Track consistency metrics
4. **Consistency Monitoring**: Monitor consistency issues
5. **Consistency Recovery**: Recover from consistency issues

---

**Last Updated**: 2026-03-22
**Version**: 2.1.0


### Config Validation Design


**Document Version**: 1.0  
**Last Updated**: 2026-03-22  
**Task**: Phase 10 — Startup Configuration Validation (openspec/changes/testsfix1 tasks 10.1–10.4)

---

## 1. Overview

Configuration validation runs at startup so misconfiguration fails fast with a clear error instead of failing later in request handling or with opaque backend errors. This document defines required environment variables, format checks, and where validation runs.

**Principles**: No mocks; validation uses real settings and env; failures raise `django.core.exceptions.ImproperlyConfigured` with a clear message.

---

## 2. Required Environment Variables and Format Checks

### 2.1 Always validated (all environments)

| Variable | Check | Error if |
|----------|--------|----------|
| **Database** | `DATABASES['default']` present and has `ENGINE`, `NAME`, `HOST`, `PORT` (from `POSTGRES_*` or equivalent in settings). | Missing or empty required key. |
| **Redis** | At least one of `REDIS_URL` or `REDIS_CACHE_URL` (from settings) is set and matches `redis://[host][:port]/[db]`. | In production/staging: no Redis URL or invalid scheme. In development: warn only if missing. |
| **ALLOWED_HOSTS** | When `ENVIRONMENT` is `production`: list non-empty. | Production and ALLOWED_HOSTS is empty. |

### 2.2 Production-only (when `ENVIRONMENT=production`)

| Variable | Check | Error if |
|----------|--------|----------|
| **SECRET_KEY** | Set via env and not the dev default (`dev-secret-key-not-for-production`). | Missing, empty, or dev default. |
| **JWT_SECRET_KEY** | Set via env and not the dev default (`dev-jwt-secret-key-not-for-production`). | Missing, empty, or dev default. |

### 2.3 Optional / not validated at startup

- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — optional; validated when billing is used.
- `HUB_WORKER_API_KEY` — optional for worker auth.
- Feature flags, logging level, timeouts — no fail-fast validation.

### 2.4 Format rules

- **Redis URL**: Must start with `redis://` or `rediss://`; may contain host, port, path (db number). No strict regex; we check prefix and non-empty.
- **Database**: Validated via Django’s `DATABASES` structure; we do not parse `DATABASE_URL` if the project uses `POSTGRES_*` in settings.
- **ALLOWED_HOSTS**: Comma-separated list or list; in production must have at least one entry.

---

## 3. Where Validation Runs

### 3.1 Management command (primary)

```bash
python hub/manage.py validate_config
```

- **When**: Before starting the server in deployment (e.g. in container entrypoint or init step).
- **Behavior**: Loads Django settings, runs all checks, exits 0 if valid, exits 1 and prints `ImproperlyConfigured` message if invalid.
- **Use in containers**: Run this before `gunicorn` or `runserver` so the process fails fast and the orchestrator can restart or alert.

### 3.2 AppConfig.ready() (fail-fast on server start)

- **When**: During Django startup when the core app’s `ready()` runs.
- **Behavior**: Runs validation only when:
  - Not running management commands that skip it (`migrate`, `makemigrations`, `test`, `validate_config` itself), and
  - Not under pytest (so test runs do not require production env).
- **Purpose**: If someone starts the server without having run `validate_config` in the entrypoint, the process still fails fast on bad config (e.g. production with dev secrets).

### 3.3 Container entrypoint (recommended for production)

In production, run validation before starting the app server:

```bash
python hub/manage.py validate_config && exec gunicorn hub.wsgi:application ...
```

Or use an entrypoint script:

```bash
#!/bin/sh
set -e
python hub/manage.py validate_config
exec "$@"
```

See [RUNBOOKS.md](RUNBOOKS.md) and deployment docs for the exact command per environment.

### 3.4 When validation is skipped

- **Tests**: Pytest and `manage.py test` do not run validation in `ready()` so test env (e.g. SQLite, mock Redis) is not required to pass production checks.
- **Migrations**: `migrate` and `makemigrations` do not run validation in `ready()` so DB bootstrap does not depend on Redis or production secrets.
- **validate_config command**: The command itself runs validation; it is not skipped.

---

## 4. Implementation Layout

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Validation logic | `hub/apps/core/config_validation.py` | Functions that read `django.conf.settings` and raise `ImproperlyConfigured` on failure. |
| Management command | `hub/apps/core/management/commands/validate_config.py` | Calls validation, handles exit code. |
| AppConfig hook | `hub.apps/core/apps.py` | Calls validation in `ready()` when not in test/migrate. |
| Design and runbook | `docs/CONFIG_VALIDATION_DESIGN.md`, `docs/RUNBOOKS.md` | Document variables, checks, and where to run. |

---

## 5. Error Messages

Validation raises `ImproperlyConfigured` with messages that:

- Identify the variable or check that failed.
- State what is required (e.g. "SECRET_KEY must be set via environment in production").
- Point to this document or RUNBOOKS when useful.

Example:

```
django.core.exceptions.ImproperlyConfigured: In production, SECRET_KEY must be set via
environment and must not be the dev default. Set SECRET_KEY in env or use a secret manager.
See docs/CONFIG_VALIDATION_DESIGN.md and docs/SECURITY.md.
```

---

## 6. Optional: Connectivity Checks

By default, validation does **not** open connections to the database or Redis (so it works in environments where the network is not yet available). Optionally, a future flag such as `--check-connectivity` could:

- Open a DB connection and run a trivial query.
- Ping Redis.

That would be documented here and in the command help. Phase 10 does not require connectivity checks; format and presence are sufficient for fail-fast startup.

---

## 4. Event Bus & Event Types


### Event Bus


## Overview

The Event Bus provides event-driven communication infrastructure for the Data Interoperability Hub. It enables decoupled, asynchronous communication between services using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence, replay, and audit.

## Architecture

### Components

1. **Event Bus** (`hub/apps/core/events/bus.py`)
   - Redis Pub/Sub for real-time event delivery
   - PostgreSQL for event persistence
   - Dead letter queue for failed events
   - Event replay functionality

2. **Event Schema** (`hub/apps/core/events/schema.py`)
   - JSON Schema validation
   - Event building utilities
   - Type-specific schemas

3. **Event Publishers** (`hub/apps/core/events/publisher.py` and `hub/apps/core/events/service_publishers.py`)
   - Base `EventPublisher` class for direct event publishing
   - Service-specific event publisher mixins (23 publishers)
   - Decorator support for automatic event publishing
   - Event deduplication support

4. **Event Subscribers** (`hub/apps/core/events/subscriber.py`)
   - Subscription management
   - Handler wrapping with error handling
   - Transaction management

5. **Event Models** (`hub/apps/core/events/models.py`)
   - `Event`: Event persistence
   - `DeadLetterQueue`: Failed event storage
   - `EventSubscription`: Subscription tracking

## Event Schema

### Base Event Structure

```json
{
  "event_id": "uuid",
  "event_type": "contract.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "hub",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["tag1", "tag2"]
  }
}
```

### Event Type Format

Event types follow the pattern: `domain.entity.action` (e.g., `contract.created`, `asset.activated`).

## Usage

### Publishing Events

#### Using EventPublisher

```python
from hub.apps.core.events import EventPublisher

publisher = EventPublisher(
    service_name="contract_service",
    tenant_id=tenant_id,
    user_id=user_id
)

event_id = publisher.publish(
    event_type="contract.created",
    data={
        "contract_id": str(contract.id),
        "asset_id": str(asset.id)
    },
    correlation_id=correlation_id
)
```

#### Using publish_event Function

```python
from hub.apps.core.events import publish_event

event_id = publish_event(
    event_type="contract.created",
    data={"contract_id": str(contract.id)},
    tenant_id=tenant_id
)
```

#### Using Decorator

```python
from hub.apps.core.events import event_publisher

@event_publisher('contract.created', tenant_id=tenant_id)
def create_contract(...):
    contract = Contract.objects.create(...)
    return {"contract_id": str(contract.id)}
```

### Subscribing to Events

#### Using EventSubscriber

```python
from hub.apps.core.events import EventSubscriber

def handle_contract_events(event):
    contract_id = event["data"]["contract_id"]
    # Process event
    pass

subscriber = EventSubscriber("webhook_service")
subscriber.subscribe("contract.*", handle_contract_events)
```

#### Using Decorator

```python
from hub.apps.core.events import event_subscriber

@event_subscriber('webhook_service', 'contract.*')
def handle_contract_events(event):
    contract_id = event["data"]["contract_id"]
    # Process event
    pass
```

### Event Replay

Event replay allows administrators to reprocess events that were previously published. This is useful for:
- Recovering from subscriber failures
- Reprocessing events after fixing bugs
- Testing event handlers
- Data recovery scenarios

#### API Endpoint

The event replay API endpoint (`POST /api/v1/events/replay/`) provides programmatic access to replay events.

**Authentication**: Requires `PLATFORM_ADMIN` or `TENANT_ADMIN` role.

**Rate Limiting**: 10 replays per hour per tenant.

**Request Body**:
```json
{
  "event_type": "odps.created",  // Optional: filter by event type
  "tenant_id": "uuid",            // Optional: filter by tenant ID
  "start_time": "2025-01-01T00:00:00Z",  // Optional: start time (ISO 8601)
  "end_time": "2025-01-02T00:00:00Z",    // Optional: end time (ISO 8601)
  "limit": 100                    // Optional: max events (default: 100, max: 1000)
}
```

**Response**:
```json
{
  "success": true,
  "events_replayed": 5,
  "events_skipped": 2,
  "total_events_found": 7,
  "event_ids": ["uuid1", "uuid2", ...],
  "skipped_event_ids": ["uuid3", "uuid4"]
}
```

**Example**:
```bash
curl -X POST https://api.example.com/api/v1/events/replay/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "odps.created",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "start_time": "2025-01-01T00:00:00Z",
    "limit": 100
  }'
```

#### Management Command

The `replay_events` management command provides CLI access to replay events.

**Usage**:
```bash
python manage.py replay_events [options]
```

**Options**:
- `--event-type TYPE`: Filter by event type (e.g., "odps.created")
- `--tenant-id ID`: Filter by tenant ID
- `--start-time TIME`: Start time for replay (ISO 8601 format)
- `--end-time TIME`: End time for replay (ISO 8601 format)
- `--limit N`: Maximum number of events to replay (default: 1000, max: 10000)
- `--dry-run`: Show what would be replayed without actually replaying
- `--batch-size N`: Number of events to process per batch (default: 100)
- `--skip-duplicates`: Skip events that have already been replayed (default: True)

**Examples**:
```bash
# Dry run to see what would be replayed
python manage.py replay_events --event-type odps.created --tenant-id <uuid> --dry-run

# Replay events from last 24 hours
python manage.py replay_events \
  --tenant-id <uuid> \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --limit 1000

# Replay specific event type in batches
python manage.py replay_events \
  --event-type odps.created \
  --tenant-id <uuid> \
  --batch-size 50 \
  --limit 500
```

#### Idempotency

Event replay is **idempotent** by default. Events that have already been replayed within the last 24 hours are automatically skipped to prevent duplicate processing.

The idempotency check uses Redis to track replayed events:
- Each replayed event is marked with a key: `event_replay:event_id:<event_id>`
- Keys expire after 24 hours
- If Redis is unavailable, replay continues but duplicate detection is disabled (graceful degradation)

#### Best Practices

1. **Use Dry-Run First**: Always test with `--dry-run` before actual replay
2. **Filter Appropriately**: Use filters (event_type, tenant_id, time range) to limit scope
3. **Batch Processing**: Use `--batch-size` for large replays to avoid memory issues
4. **Monitor Results**: Check the response/command output for skipped events
5. **Idempotent Handlers**: Ensure event handlers are idempotent to handle replays safely
6. **Rate Limits**: Be aware of rate limits (10 replays/hour/tenant) when automating

#### Programmatic Usage

```python
from hub.apps.core.events import get_event_bus
from datetime import datetime, timedelta

event_bus = get_event_bus()

# Replay events from last hour
events = event_bus.replay_events(
    event_type="contract.created",
    start_time=datetime.utcnow() - timedelta(hours=1),
    limit=1000
)

# Republish events
for event in events:
    event_bus.publish(**event)
```

### Dead Letter Queue

Failed events are automatically sent to the dead letter queue after max retries.

```python
from hub.apps.core.events.models import DeadLetterQueue

# Get failed events
failed_events = DeadLetterQueue.objects.filter(
    subscriber="webhook_service",
    resolved_at__isnull=True
)

# Resolve failed event
dlq_entry.resolved_at = timezone.now()
dlq_entry.resolved_by = user_id
dlq_entry.save()
```

## Configuration

### Settings

```python
# Redis URL
REDIS_URL = 'redis://localhost:6379/0'

# Event bus settings
EVENT_BUS_CHANNEL_PREFIX = 'events'
EVENT_BUS_ENABLE_PERSISTENCE = True
EVENT_BUS_MAX_RETRIES = 3
```

## Publishers by service

Which services publish to the event bus (Redis Pub/Sub + PostgreSQL persistence):

| Service | Publishes to event bus? | Notes |
|--------|---------------------------|-------|
| **api-service** (Django) | **Yes** | All event publishing is done from the Hub Django app. Services (ContractService, AssetService, etc.) use publisher mixins from `hub/apps/core/events/service_publishers.py` and publish via `hub/apps/core/events` (bus, publisher). Event types include: `contract.*`, `asset.*`, `dataset.*`, `file.*`, `workflow.*`, `odps.*`, `marketplace.*`, `mesh.*`, `virtualization.*`, `ingestion.*`, `quality.*`, `compliance.*`, `version.*`, `access.*`, `lineage.*`, `search.*`, `payment.*`, `tenant.*`, `normalization.*`, `observability.*`, `integration.*`, `baas.*`, `ml.*`, and others. |
| **semantic-service** | **N/A** | Does not publish to the event bus. Invoked by api-service (e.g. semantic mapping); outcomes are published by api-service (e.g. `odps.semantic.mapped`). |
| **dq-service** | **Not yet** | Does not publish to the event bus. DQ runs are triggered from api-service/worker; results could be published from api-service when product requires it. |
| **compliance-service** | **Not yet** | Does not publish to the event bus. Compliance checks are triggered from api-service; results could be published from api-service when product requires it. |
| **webhook-service** | **N/A** | Consumes events (subscriber/delivery). Does not publish domain events to the bus; delivery status could be published from api-service if required. |

If product requirements later need events published directly from microservices (e.g. semantic-service or dq-service), add publishing to the same bus (Redis + schema) from those services and document in this section.

## Event Publishers

The Event Bus provides **25 service-specific event publisher mixins** that enable services to publish events in a standardized, type-safe manner. All publishers follow the same pattern and are located in `hub/apps/core/events/service_publishers.py`.

### Event Publisher Pattern

All event publishers follow this consistent pattern:

1. **Mixin Class**: Each publisher is a mixin class that can be added to service classes
2. **Initialization**: Publishers initialize an internal `EventPublisher` instance with service name and tenant/user context
3. **Publish Methods**: Each publisher provides typed `publish_*` methods for specific event types
4. **Deduplication**: All publishers support automatic event deduplication
5. **Error Handling**: Publishers handle errors gracefully with retry logic where appropriate

### Base EventPublisher

The base `EventPublisher` class (`hub/apps/core/events/publisher.py`) provides:

- **Service Context**: Tracks service name, tenant_id, and user_id
- **Publish Method**: Generic `publish()` method with deduplication support
- **Error Handling**: Graceful error handling with logging
- **Deduplication**: Automatic duplicate event detection using Redis

### Service Event Publishers

All service-specific publishers are mixins that extend services with event publishing capabilities:

#### 1. ContractEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ContractService`
**Events Published**:
- `contract.created` - Contract creation
- `contract.updated` - Contract updates
- `contract.deleted` - Contract deletion
- `contract.validated` - Contract validation completion
- `contract.normalized` - Contract normalization completion

**Usage**:
```python
class ContractService(BaseService, ContractEventPublisher):
    def create_contract(self, ...):
        contract = Contract.objects.create(...)
        self.publish_contract_created(
            contract_id=str(contract.id),
            status="ACTIVE"
        )
        return contract
```

#### 2. AssetEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `AssetService`
**Events Published**:
- `asset.created` - Asset creation
- `asset.updated` - Asset updates
- `asset.activated` - Asset activation
- `asset.published` - Asset published to marketplace
- `asset.retired` - Asset retirement

#### 3. DatasetEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `DatasetService`
**Events Published**:
- `dataset.created` - Dataset creation
- `dataset.updated` - Dataset updates
- `dataset.deleted` - Dataset deletion
- `dataset.uploaded` - Dataset file upload

#### 4. IngestionEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `IngestionService`
**Events Published**:
- `ingestion.started` - Ingestion process started
- `ingestion.completed` - Ingestion process completed
- `ingestion.failed` - Ingestion process failed
- `ingestion.file_processed` - Single file processed during ingestion

#### 5. QualityEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: Quality service
**Events Published**:
- `quality.check.started` - Quality check started
- `quality.check.completed` - Quality check completed
- `quality.check.failed` - Quality check failed
- `quality.anomaly.detected` - Quality anomaly detected

#### 6. ComplianceEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ComplianceService`
**Events Published**:
- `compliance.check.started` - Compliance check started
- `compliance.check.completed` - Compliance check completed
- `compliance.check.failed` - Compliance check failed
- `compliance.report.generated` - Compliance report generated

#### 7. VersionEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: Versioning service
**Events Published**:
- `version.created` - Version created
- `version.updated` - Version updated
- `version.rolled_back` - Version rolled back

#### 8. VersioningEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `VersioningService`
**Events Published**:
- `version.created` - Version created
- `version.updated` - Version updated
- `version.deleted` - Version deleted
- `version.promoted` - Version promoted

#### 9. AccessEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `GovernanceService`
**Events Published**:
- `access.requested` - Access request created
- `access.granted` - Access granted
- `access.revoked` - Access revoked
- `access.certified` - Access certified

#### 10. MarketplaceEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `MarketplaceService`
**Events Published**:
- `marketplace.listing.published` - Marketplace listing published
- `marketplace.listing.unpublished` - Marketplace listing unpublished
- `marketplace.order.created` - Marketplace order created
- `marketplace.order.approved` - Marketplace order approved
- `marketplace.order.rejected` - Marketplace order rejected
- `marketplace.order.fulfilled` - Marketplace order fulfilled
- `marketplace.entitlement.granted` - Marketplace entitlement granted
- `marketplace.entitlement.revoked` - Marketplace entitlement revoked

#### 11. WorkflowEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `WorkflowEngine`
**Events Published**:
- `workflow.created` - Workflow instance created
- `workflow.started` - Workflow instance started
- `workflow.completed` - Workflow instance completed
- `workflow.failed` - Workflow instance failed
- `workflow.cancelled` - Workflow instance cancelled
- `workflow.step.started` - Workflow step started
- `workflow.step.completed` - Workflow step completed
- `workflow.step.failed` - Workflow step failed

#### 12. ODPSEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ContractService`, `ODPSService`
**Events Published**:
- `odps.created` - ODPS contract created
- `odps.updated` - ODPS contract updated
- `odps.deleted` - ODPS contract deleted
- `odps.normalized` - ODPS contract normalized
- `odps.linked` - ODPS contract linked to ODCS
- `odps.unlinked` - ODPS contract unlinked from ODCS
- `odps.ref.resolved` - ODPS $ref resolution completed
- `odps.ref.failed` - ODPS $ref resolution failed
- `odps.export.started` - ODPS export started
- `odps.export.completed` - ODPS export completed
- `odps.export.failed` - ODPS export failed
- `odps.workflow.started` - ODPS workflow started
- `odps.workflow.completed` - ODPS workflow completed
- `odps.workflow.failed` - ODPS workflow failed
- `odps.workflow.step.completed` - ODPS workflow step completed
- `odps.workflow.step.failed` - ODPS workflow step failed
- `odps.workflow.progress` - ODPS workflow progress update
- `odps.creation.progress` - ODPS creation progress update
- `odps.normalization.progress` - ODPS normalization progress update
- `odps.ref.progress` - ODPS $ref resolution progress update
- `odps.linking.status` - ODPS linking status update
- `odps.export.progress` - ODPS export progress update
- `odps.semantic.mapping.progress` - ODPS semantic mapping progress update
- `odps.semantic.mapped` - ODPS semantic mapping completed

**Special Features**:
- Retry logic with exponential backoff for transient failures
- Graceful degradation on publish failures
- Progress event publishing for long-running operations

#### 14. DataMeshEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `DataMeshService`
**Events Published**:
- `domain.created` - Data mesh domain created
- `domain.updated` - Data mesh domain updated
- `domain.deleted` - Data mesh domain deleted
- `policy.applied` - Policy applied to domain
- `policy.revoked` - Policy revoked from domain
- `compliance.report.generated` - Compliance report generated
- `mesh.compliance.checked` - Mesh compliance checked
- `mesh.topology.updated` - Mesh topology updated
- `mesh.domain.created` - Mesh domain created (internal)
- `mesh.domain.updated` - Mesh domain updated (internal)
- `mesh.policy.applied` - Mesh policy applied (internal)
- `mesh.compliance.checked` - Mesh compliance checked (internal)
- `mesh.health.status_changed` - Mesh health status changed

**Special Features**:
- Webhook integration for mesh events
- Internal and external event type mapping

#### 15. VirtualizationEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `VirtualizationService`
**Events Published**:
- `virtualization.dataset.created` - Virtual dataset created
- `virtualization.dataset.updated` - Virtual dataset updated
- `virtualization.dataset.deleted` - Virtual dataset deleted
- `virtualization.query.execution.started` - Query execution started
- `virtualization.query.execution.progress` - Query execution progress
- `virtualization.query.execution.completed` - Query execution completed
- `virtualization.query.execution.failed` - Query execution failed
- `virtualization.query.execution.cancelled` - Query execution cancelled

**Special Features**:
- Webhook integration for virtualization events
- Progress event publishing for long-running queries

#### 16. FileEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `FileService`
**Events Published**:
- `file.created` - File created
- `file.updated` - File updated
- `file.deleted` - File deleted
- `file.uploaded` - File uploaded
- `file.downloaded` - File downloaded

#### 17. LineageEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `LineageService`
**Events Published**:
- `lineage.updated` - Lineage updated
- `lineage.relationship_added` - Lineage relationship added
- `lineage.relationship_removed` - Lineage relationship removed

#### 18. SearchEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `SearchService`
**Events Published**:
- `search.query` - Search query executed
- `search.index.updated` - Search index updated
- `search.index.rebuilt` - Search index rebuilt

#### 19. PaymentGatewayEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `PaymentGatewayService`
**Events Published**:
- `payment.gateway.linked` - Payment gateway linked
- `payment.gateway.unlinked` - Payment gateway unlinked
- `payment.gateway.webhook.received` - Payment gateway webhook received

#### 20. TenantEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `TenantService`
**Events Published**:
- `tenant.created` - Tenant created
- `tenant.updated` - Tenant updated
- `tenant.deleted` - Tenant deleted
- `tenant.quota.changed` - Tenant quota changed

#### 21. NormalizationEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `NormalizationService`
**Events Published**:
- `normalization.started` - Normalization started
- `normalization.completed` - Normalization completed
- `normalization.failed` - Normalization failed

#### 22. PaymentEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `PaymentService`
**Events Published**:
- `payment.initiated` - Payment initiated
- `payment.completed` - Payment completed
- `payment.failed` - Payment failed
- `payment.refunded` - Payment refunded

#### 23. ObservabilityEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ObservabilityService`
**Events Published**:
- `observability.metric.recorded` - Metric recorded
- `observability.trace.created` - Trace created
- `observability.log.created` - Log created
- `observability.alert.triggered` - Alert triggered

#### 24. IntegrationEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `IntegrationService`
**Events Published**: Integration and connector events (e.g. sync, harvest, marketplace integration).

#### 25. BaaSEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: BaaS platform services
**Events Published**: BaaS usage, tier, API key, and developer portal events.

#### 26. MLEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: ML/ODH services
**Events Published**: Training, inference, model registry events.

### Event Publisher Pattern Implementation

#### Creating a Service with Event Publishing

```python
from hub.apps.core.services.base import BaseService
from hub.apps.core.events.service_publishers import ContractEventPublisher

class ContractService(BaseService, ContractEventPublisher):
    """Service with event publishing capabilities."""

    def __init__(self, tenant_id=None, user_id=None):
        BaseService.__init__(self, tenant_id=tenant_id, user_id=user_id)
        ContractEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def create_contract(self, contract_data):
        """Create contract and publish event."""
        contract = Contract.objects.create(**contract_data)

        # Publish event
        self.publish_contract_created(
            contract_id=str(contract.id),
            status=contract.status,
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        return contract
```

#### Publisher Initialization Pattern

All publishers follow this initialization pattern:

```python
def __init__(self, *args, **kwargs):
    # Handle parent class initialization
    try:
        parent_init = super().__init__
        if parent_init is not object.__init__:
            parent_init(*args, **kwargs)
    except (TypeError, AttributeError):
        pass

    # Initialize internal EventPublisher
    self._event_publisher = EventPublisher(
        service_name="service_name",
        tenant_id=getattr(self, "tenant_id", None),
        user_id=getattr(self, "user_id", None),
    )
```

#### Publisher Method Pattern

All publisher methods follow this pattern:

```python
def publish_event_name(
    self,
    resource_id: str,
    optional_field: Optional[str] = None,
    **kwargs,
) -> str:
    """Publish event_name event."""
    return self._event_publisher.publish(
        event_type="domain.entity.action",
        data={
            "resource_id": resource_id,
            "optional_field": optional_field,
        },
        **kwargs,  # Pass through tenant_id, user_id, correlation_id, etc.
    )
```

#### Key Features

1. **Type Safety**: Each publisher method has typed parameters
2. **Deduplication**: Automatic duplicate event detection
3. **Error Handling**: Graceful error handling with logging
4. **Context Propagation**: Tenant and user context automatically included
5. **Extensibility**: Easy to add new event types via new methods

### Direct Event Publishing

For cases where a service-specific publisher doesn't exist, use the base `EventPublisher`:

```python
from hub.apps.core.events.publisher import EventPublisher

publisher = EventPublisher(
    service_name="my_service",
    tenant_id=tenant_id,
    user_id=user_id
)

event_id = publisher.publish(
    event_type="custom.event.type",
    data={"field": "value"},
    tags=["custom", "event"]
)
```

### Event Deduplication

All publishers support automatic event deduplication:

```python
# First publish
event_id_1 = service.publish_contract_created(contract_id="123")

# Duplicate publish (same event_type and data)
event_id_2 = service.publish_contract_created(contract_id="123")

# event_id_1 == event_id_2 (same event ID returned)
```

Deduplication uses Redis with configurable TTL (default: 24 hours).

### Event Publisher Pattern

The event publisher pattern provides a standardized way for services to publish events. This pattern ensures:

1. **Consistency**: All services publish events in the same way
2. **Type Safety**: Publisher methods have typed parameters
3. **Context Propagation**: Tenant and user context automatically included
4. **Error Handling**: Graceful error handling with logging
5. **Deduplication**: Automatic duplicate event detection
6. **Testability**: Easy to test event publishing

#### Pattern Components

1. **Mixin Class**: Each publisher is a mixin that can be added to service classes
2. **Internal EventPublisher**: Each publisher maintains an internal `EventPublisher` instance
3. **Typed Methods**: Each event type has a dedicated `publish_*` method
4. **Service Context**: Publishers automatically include service name, tenant_id, and user_id

#### Pattern Implementation Steps

1. **Create Publisher Mixin**:
```python
class MyServiceEventPublisher:
    """Event publisher mixin for MyService."""

    def __init__(self, *args, **kwargs):
        # Handle parent initialization
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass

        # Initialize internal EventPublisher
        self._event_publisher = EventPublisher(
            service_name="my_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )
```

2. **Add Publish Methods**:
```python
def publish_resource_created(
    self,
    resource_id: str,
    name: Optional[str] = None,
    **kwargs,
) -> str:
    """Publish resource.created event."""
    return self._event_publisher.publish(
        event_type="resource.created",
        data={
            "resource_id": resource_id,
            "name": name,
        },
        **kwargs,  # Pass through tenant_id, user_id, correlation_id, etc.
    )
```

3. **Use in Service**:
```python
class MyService(BaseService, MyServiceEventPublisher):
    def __init__(self, tenant_id=None, user_id=None):
        BaseService.__init__(self, tenant_id=tenant_id, user_id=user_id)
        MyServiceEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def create_resource(self, resource_data):
        resource = Resource.objects.create(**resource_data)
        self.publish_resource_created(
            resource_id=str(resource.id),
            name=resource.name
        )
        return resource
```

#### Pattern Benefits

1. **Separation of Concerns**: Event publishing logic is separated from business logic
2. **Reusability**: Publishers can be reused across multiple services
3. **Testability**: Easy to test event publishing independently
4. **Maintainability**: Changes to event publishing don't affect business logic
5. **Type Safety**: Typed methods prevent errors at development time

#### Pattern Best Practices

1. **One Publisher Per Service**: Create one publisher mixin per service
2. **One Method Per Event Type**: Each event type should have its own publish method
3. **Consistent Naming**: Use `publish_<event_type>` naming convention
4. **Documentation**: Document all events published by your service
5. **Error Handling**: Handle errors gracefully, don't block business logic
6. **Testing**: Write tests for event publishing (use real EventBus, no mocks)

### Best Practices for Event Publishers

1. **Use Service-Specific Publishers**: Prefer service-specific publishers over direct `EventPublisher`
2. **Include Context**: Always include tenant_id and user_id when available
3. **Handle Errors Gracefully**: Event publishing failures should not block business logic
4. **Use Tags**: Include relevant tags for event filtering and monitoring
5. **Document Events**: Document all events published by your service
6. **Test Publishing**: Write tests for event publishing (use real EventBus, no mocks)

## Event Types

For a complete reference of all event types, see **[Event Types Reference](EVENT_TYPES_REFERENCE.md)**.

**Total Event Types**: 120+ unique event types across 23 publishers

## ODPS Event Publishing Examples

### Publishing ODPS Events

#### Using ODPSEventPublisher

```python
from hub.apps.core.services.base import BaseService
from hub.apps.core.events.service_publishers import ODPSEventPublisher

class ODPSService(BaseService, ODPSEventPublisher):
    def __init__(self, tenant_id=None, user_id=None):
        BaseService.__init__(self, tenant_id=tenant_id, user_id=user_id)
        ODPSEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def create_odps_contract(self, odps_data):
        """Create ODPS contract and publish events."""
        contract = Contract.objects.create(**odps_data)
        
        # Publish ODPS created event
        self.publish_odps_created(
            contract_id=str(contract.id),
            odps_version="4.1",
            status="DRAFT",
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )
        
        return contract

    def normalize_odps_contract(self, contract_id):
        """Normalize ODPS contract and publish events."""
        contract = Contract.objects.get(id=contract_id)
        
        # Perform normalization...
        normalization_status = "NORMALIZED_OK"
        
        # Publish normalization completed event
        self.publish_odps_normalized(
            contract_id=str(contract_id),
            normalization_status=normalization_status,
            tenant_id=self.tenant_id
        )
        
        return contract

    def export_odps_contract(self, contract_id, export_format="JSON"):
        """Export ODPS contract and publish events."""
        # Publish export started event
        self.publish_odps_export_started(
            contract_id=str(contract_id),
            export_format=export_format,
            tenant_id=self.tenant_id
        )
        
        try:
            # Perform export...
            export_data = {...}
            
            # Publish export completed event
            self.publish_odps_export_completed(
                contract_id=str(contract_id),
                export_format=export_format,
                export_size=len(export_data),
                tenant_id=self.tenant_id
            )
            
            return export_data
        except Exception as e:
            # Publish export failed event
            self.publish_odps_export_failed(
                contract_id=str(contract_id),
                export_format=export_format,
                error_message=str(e),
                tenant_id=self.tenant_id
            )
            raise
```

#### Publishing ODPS Workflow Events

```python
from hub.apps.core.events.service_publishers import ODPSEventPublisher

class ODPSWorkflowService(ODPSEventPublisher):
    def execute_odps_creation_workflow(self, workflow_instance_id, contract_id):
        """Execute ODPS creation workflow and publish progress events."""
        
        # Publish workflow started event
        self.publish_odps_workflow_started(
            contract_id=str(contract_id),
            workflow_name="odps_creation",
            workflow_version="1.0.0",
            tenant_id=self.tenant_id
        )
        
        try:
            # Step 1: Parse ODPS document
            self.publish_odps_creation_progress(
                contract_id=str(contract_id),
                progress_percent=25,
                current_step="parse_document",
                tenant_id=self.tenant_id
            )
            
            # Step 2: Resolve external references
            self.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percent=50,
                resolved_refs_count=5,
                total_refs_count=10,
                tenant_id=self.tenant_id
            )
            
            # Step 3: Normalize contract
            self.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percent=75,
                current_step="normalize_contract",
                tenant_id=self.tenant_id
            )
            
            # Step 4: Complete workflow
            self.publish_odps_workflow_completed(
                contract_id=str(contract_id),
                workflow_name="odps_creation",
                duration_ms=5000,
                tenant_id=self.tenant_id
            )
            
        except Exception as e:
            # Publish workflow failed event
            self.publish_odps_workflow_failed(
                contract_id=str(contract_id),
                workflow_name="odps_creation",
                error_message=str(e),
                tenant_id=self.tenant_id
            )
            raise
```

## ODPS Event Subscription Examples

### Subscribing to ODPS Events

#### Using EventSubscriber

```python
from hub.apps.core.events.subscriber import EventSubscriber

def handle_odps_created(event):
    """Handle ODPS created event."""
    contract_id = event["data"]["contract_id"]
    odps_version = event["data"].get("odps_version")
    
    # Process ODPS creation...
    logger.info(f"ODPS contract {contract_id} created (version: {odps_version})")

def handle_odps_normalized(event):
    """Handle ODPS normalized event."""
    contract_id = event["data"]["contract_id"]
    normalization_status = event["data"]["normalization_status"]
    
    # Update search index, send notifications, etc.
    logger.info(f"ODPS contract {contract_id} normalized: {normalization_status}")

def handle_odps_export_completed(event):
    """Handle ODPS export completed event."""
    contract_id = event["data"]["contract_id"]
    export_format = event["data"]["export_format"]
    export_size = event["data"].get("export_size")
    
    # Process export completion...
    logger.info(f"ODPS contract {contract_id} exported as {export_format} ({export_size} bytes)")

# Create subscriber
subscriber = EventSubscriber("odps_service")

# Subscribe to ODPS lifecycle events
subscriber.subscribe("odps.created", handle_odps_created)
subscriber.subscribe("odps.normalized", handle_odps_normalized)
subscriber.subscribe("odps.export.completed", handle_odps_export_completed)

# Subscribe to all ODPS events using wildcard
subscriber.subscribe("odps.*", lambda event: logger.info(f"ODPS event: {event['event_type']}"))

# Start listening
subscriber.start()
```

#### Using Decorator-Based Subscribers

```python
from hub.apps.core.events.subscriber import event_subscriber

@event_subscriber("odps_service", "odps.created")
def handle_odps_created(event):
    """Handle ODPS created event."""
    contract_id = event["data"]["contract_id"]
    # Process creation...

@event_subscriber("odps_service", "odps.normalized")
def handle_odps_normalized(event):
    """Handle ODPS normalized event."""
    contract_id = event["data"]["contract_id"]
    # Process normalization...

@event_subscriber("odps_service", "odps.export.*")
def handle_odps_export_events(event):
    """Handle all ODPS export events."""
    event_type = event["event_type"]
    contract_id = event["data"]["contract_id"]
    
    if event_type == "odps.export.started":
        logger.info(f"ODPS export started for contract {contract_id}")
    elif event_type == "odps.export.completed":
        logger.info(f"ODPS export completed for contract {contract_id}")
    elif event_type == "odps.export.failed":
        error_message = event["data"]["error_message"]
        logger.error(f"ODPS export failed for contract {contract_id}: {error_message}")
```

## ODPS Event Replay Examples

### Replaying ODPS Events

#### Using API Endpoint

```bash
# Replay ODPS created events from last 24 hours
curl -X POST https://api.example.com/api/v1/events/replay/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "odps.created",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "start_time": "2025-01-14T00:00:00Z",
    "limit": 100
  }'

# Replay ODPS normalization events for specific contract
curl -X POST https://api.example.com/api/v1/events/replay/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "odps.normalized",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "start_time": "2025-01-15T00:00:00Z",
    "end_time": "2025-01-15T23:59:59Z",
    "limit": 50
  }'
```

#### Using Management Command

```bash
# Replay ODPS created events
python manage.py replay_events \
  --event-type odps.created \
  --tenant-id 550e8400-e29b-41d4-a716-446655440000 \
  --start-time 2025-01-14T00:00:00Z \
  --limit 100

# Dry run to see what would be replayed
python manage.py replay_events \
  --event-type odps.normalized \
  --tenant-id 550e8400-e29b-41d4-a716-446655440000 \
  --dry-run

# Replay ODPS export events in batches
python manage.py replay_events \
  --event-type odps.export.completed \
  --tenant-id 550e8400-e29b-41d4-a716-446655440000 \
  --batch-size 50 \
  --limit 500
```

#### Programmatic Event Replay

```python
from hub.apps.core.events import get_event_bus
from datetime import datetime, timedelta

event_bus = get_event_bus()

# Replay ODPS created events from last hour
events = event_bus.replay_events(
    event_type="odps.created",
    start_time=datetime.utcnow() - timedelta(hours=1),
    limit=1000
)

# Process replayed events
for event in events:
    contract_id = event["data"]["contract_id"]
    # Reprocess ODPS creation...
    print(f"Replayed ODPS creation for contract {contract_id}")

# Replay ODPS normalization events for specific time range
events = event_bus.replay_events(
    event_type="odps.normalized",
    start_time=datetime(2025, 1, 15, 0, 0, 0),
    end_time=datetime(2025, 1, 15, 23, 59, 59),
    limit=500
)

# Republish events
for event in events:
    event_bus.publish(**event)
```

## Best Practices

1. **Event Naming**: Use consistent naming convention (`domain.entity.action`)
2. **Event Versioning**: Include schema version for backward compatibility
3. **Error Handling**: Always handle event publishing errors gracefully
4. **Idempotency**: Make event handlers idempotent
5. **Transaction Management**: Use transactions for event handlers
6. **Monitoring**: Monitor dead letter queue regularly
7. **Replay Safety**: Ensure replay handlers are idempotent
8. **ODPS Progress Events**: Publish progress events for long-running ODPS operations (normalization, export, $ref resolution)
9. **ODPS Error Events**: Always publish error events when ODPS operations fail
10. **ODPS Workflow Events**: Publish workflow events at each step of ODPS creation/processing workflows

## Testing

See `hub/apps/core/events/tests/` for comprehensive test examples.

## Migration

Run migrations to create event tables:

```bash
python manage.py migrate events
```

## Performance Considerations

- Redis Pub/Sub provides low-latency event delivery
- PostgreSQL persistence adds minimal overhead (<5ms per event)
- Event replay queries are optimized with indexes
- Dead letter queue queries use indexes for fast lookups

## Troubleshooting

### Events Not Being Received

1. Check Redis connection
2. Verify subscription is active
3. Check event type pattern matching
4. Review dead letter queue for failures

### High Dead Letter Queue Volume

1. Review error messages
2. Check handler implementation
3. Verify event schema compatibility
4. Review retry configuration

### Performance Issues

1. Monitor Redis connection pool
2. Review PostgreSQL indexes
3. Consider event batching for high-volume scenarios
4. Monitor event persistence latency


### Event Bus Performance Analysis


**Date:** 2025-12-30
**Task:** 9.7.1.1.1 - Evaluate current event bus implementation

## Executive Summary

This document provides a comprehensive performance analysis of the current Event Bus implementation, including Redis Pub/Sub performance characteristics, PostgreSQL persistence performance, bottleneck identification, scalability limits, and architecture limitations.

## Architecture Overview

The Event Bus uses a dual-storage architecture:
- **Redis Pub/Sub**: Real-time event delivery (fire-and-forget messaging)
- **PostgreSQL**: Event persistence for replay, audit, and debugging

### Key Components

1. **EventBus** (`hub/apps/core/events/bus.py`)
   - Redis Pub/Sub for real-time delivery
   - PostgreSQL persistence via Django ORM
   - Dead letter queue for failed events
   - Event subscription management

2. **Connection Pooling**
   - Redis connection pool: 50 initial, 100 max connections
   - Socket timeout: 5 seconds
   - Health check interval: 30 seconds

3. **Persistence Flow**
   - Event validation (schema-based)
   - PostgreSQL write (synchronous, transactional)
   - Redis publish (asynchronous, fire-and-forget)

## Performance Test Results

### 1. Throughput Tests

#### Publish Throughput
- **Result**: ~1,580 events/sec (1,000 events in 0.63s)
- **Average Latency**: 0.63ms per event
- **Status**: ✅ Exceeds minimum threshold of 100 events/sec

#### High Volume Stress Test
- **Total Events**: 10,000 events
- **Total Time**: 5.91 seconds
- **Overall Throughput**: ~1,692 events/sec
- **Batch Performance**: Consistent ~1,650-1,740 events/sec per batch
- **Error Rate**: 0.00% (0 errors)
- **Persistence Rate**: 100% (10,000/10,000 events persisted)

**Key Finding**: The event bus maintains consistent throughput even under high volume, with zero errors and complete persistence.

### 2. Latency Tests

#### Individual Event Latency
- **Average Latency**: <100ms (meets requirement)
- **P50 (Median)**: <50ms
- **P95 Latency**: <200ms (meets requirement)
- **P99 Latency**: Measured but varies based on system load

**Key Finding**: Latency is well within acceptable ranges for real-time event delivery.

### 3. Redis Pub/Sub Performance

#### Pub/Sub Only (Without Persistence)
- **Average Latency**: <10ms
- **P95 Latency**: <20ms
- **Status**: ✅ Redis Pub/Sub is extremely fast

**Key Finding**: Redis Pub/Sub adds minimal overhead (~1-10ms), making it suitable for real-time delivery.

### 4. PostgreSQL Persistence Performance

#### Persistence Throughput
- **Throughput**: >50 events/sec (meets requirement)
- **Persistence Overhead**: Measured vs. Pub/Sub only
- **Status**: ✅ Persistence maintains acceptable performance

**Key Finding**: PostgreSQL persistence is the primary bottleneck but remains within acceptable limits.

### 5. Load Tests

#### Concurrent Subscribers
- **Subscribers**: 10 concurrent subscribers
- **Events per Subscriber**: 50 events
- **Delivery Rate**: >90% (allows for 10% loss tolerance)
- **Status**: ✅ Handles concurrent subscribers effectively

#### Subscriber Scalability
- **Tested Scales**: 1, 5, 10, 20 subscribers
- **Throughput Degradation**: <50% with 20 subscribers
- **Status**: ✅ Scales reasonably well with increasing subscribers

**Key Finding**: Redis Pub/Sub handles multiple subscribers efficiently, with minimal degradation.

### 6. Stress Tests

#### Sustained Load
- **Duration**: 30 seconds
- **Target Rate**: 100 events/sec
- **Actual Rate**: >80 events/sec (80% of target)
- **Error Rate**: <1%
- **Status**: ✅ Maintains sustained load

#### Burst Traffic
- **Burst Sizes Tested**: 100, 500, 1000, 2000 events
- **Error Rate**: <5% for all burst sizes
- **Status**: ✅ Handles burst traffic effectively

**Key Finding**: The event bus handles both sustained and burst traffic patterns effectively.

### 7. Bottleneck Analysis

#### Persistence vs. Pub/Sub Overhead
- **Persistence Overhead**: Measured and documented
- **Primary Bottleneck**: PostgreSQL write operations
- **Secondary Bottleneck**: Event validation (schema-based)

**Key Finding**: PostgreSQL persistence is the primary performance bottleneck, but remains acceptable.

#### Event Size Impact
- **Tested Sizes**: 100 bytes, 1KB, 10KB, 100KB
- **Throughput Degradation**: Measured and documented
- **Status**: ✅ Performance degrades gracefully with larger payloads

**Key Finding**: Larger event payloads reduce throughput but remain within acceptable limits.

## Identified Bottlenecks

### 1. PostgreSQL Persistence (Primary Bottleneck)

**Impact**: Medium-High
- **Description**: Synchronous database writes for every event
- **Current Performance**: ~50-100 events/sec per connection
- **Mitigation Options**:
  - Batch writes (bulk inserts)
  - Asynchronous persistence (background workers)
  - Write-behind caching
  - Connection pooling optimization

### 2. Event Validation (Secondary Bottleneck)

**Impact**: Low-Medium
- **Description**: Schema-based validation for every event
- **Current Performance**: Minimal overhead (~1-5ms)
- **Mitigation Options**:
  - Cached schema validation
  - Lazy validation (validate on consume, not publish)
  - Optimized validation logic

### 3. Redis Connection Pool Limits

**Impact**: Low
- **Description**: Connection pool size limits concurrent operations
- **Current Configuration**: 50 initial, 100 max connections
- **Mitigation Options**:
  - Increase pool size for high-load scenarios
  - Connection pooling optimization
  - Redis cluster support

## Scalability Limits

### Current Limits

1. **Throughput**: ~1,500-2,000 events/sec (single instance)
2. **Concurrent Subscribers**: Tested up to 20, scales reasonably
3. **Event Volume**: Tested up to 10,000 events, handles gracefully
4. **Payload Size**: Tested up to 100KB, degrades gracefully

### Projected Limits

1. **Single Instance**: ~2,000-3,000 events/sec (with optimizations)
2. **Multi-Instance**: Linear scaling with Redis cluster
3. **Subscribers**: Redis Pub/Sub supports unlimited subscribers
4. **Persistence**: PostgreSQL write capacity is the limiting factor

## Architecture Limitations

### 1. Synchronous Persistence

**Limitation**: Every event publish waits for PostgreSQL write
- **Impact**: Adds latency and reduces throughput
- **Recommendation**: Consider asynchronous persistence for high-throughput scenarios

### 2. Single Redis Instance

**Limitation**: No built-in high availability or clustering
- **Impact**: Single point of failure
- **Recommendation**: Consider Redis Sentinel or Cluster for production

### 3. No Message Ordering Guarantees

**Limitation**: Redis Pub/Sub does not guarantee message ordering
- **Impact**: Events may arrive out of order
- **Recommendation**: Implement ordering logic at application level if needed

### 4. No Backpressure Mechanism

**Limitation**: No built-in backpressure handling
- **Impact**: Publishers may overwhelm subscribers
- **Recommendation**: Implement rate limiting or backpressure at application level

### 5. Limited Replay Capabilities

**Limitation**: Replay requires querying PostgreSQL
- **Impact**: Replay may be slow for large event volumes
- **Recommendation**: Consider event sourcing patterns or dedicated replay service

## Recommendations

### Short-Term (Immediate)

1. **Monitor Performance Metrics**
   - Implement Prometheus metrics collection
   - Set up alerts for throughput degradation
   - Monitor persistence latency

2. **Optimize Database Writes**
   - Review database indexes
   - Consider bulk inserts for high-volume scenarios
   - Optimize connection pooling

3. **Document Performance Characteristics**
   - Document current throughput and latency baselines
   - Create performance runbooks
   - Establish SLAs

### Medium-Term (3-6 Months)

1. **Implement Asynchronous Persistence**
   - Background workers for persistence
   - Write-behind caching
   - Reduced publish latency

2. **Enhance Monitoring**
   - Real-time performance dashboards
   - Alerting for bottlenecks
   - Capacity planning tools

3. **Optimize Event Validation**
   - Cached schema validation
   - Lazy validation options
   - Performance profiling

### Long-Term (6-12 Months)

1. **Evaluate Redis Streams**
   - Compare performance vs. Pub/Sub
   - Evaluate migration complexity
   - Consider consumer groups and replay capabilities

2. **High Availability**
   - Redis Sentinel or Cluster
   - PostgreSQL read replicas
   - Multi-region support

3. **Advanced Features**
   - Event ordering guarantees
   - Backpressure mechanisms
   - Advanced replay capabilities

## Test Coverage

### Performance Tests Created

1. ✅ `test_publish_throughput` - Measures events/sec
2. ✅ `test_publish_latency` - Measures individual event latency
3. ✅ `test_persistence_performance` - Measures PostgreSQL write performance
4. ✅ `test_redis_pubsub_performance` - Measures Redis Pub/Sub latency
5. ✅ `test_concurrent_subscribers` - Tests multiple subscribers
6. ✅ `test_subscriber_scalability` - Tests scalability with increasing subscribers
7. ✅ `test_high_volume_stress` - Tests 10,000+ events
8. ✅ `test_sustained_load` - Tests sustained load over time
9. ✅ `test_burst_traffic` - Tests burst traffic patterns
10. ✅ `test_persistence_vs_pubsub_overhead` - Compares persistence overhead
11. ✅ `test_event_size_impact` - Tests impact of payload size

### Test Results Summary

- **Total Tests**: 11
- **Pass Rate**: 100% (11/11 passed)
- **Execution Time**: ~2 minutes for full suite
- **Coverage**: Comprehensive performance, load, and stress testing

## Conclusion

The current Event Bus implementation demonstrates:

1. **Strong Performance**: ~1,500-2,000 events/sec throughput
2. **Low Latency**: <100ms average latency
3. **High Reliability**: 0% error rate in stress tests
4. **Good Scalability**: Handles concurrent subscribers and high volumes

**Primary Bottleneck**: PostgreSQL persistence (synchronous writes)

**Recommendation**: Current implementation is suitable for production use, with optimizations recommended for high-throughput scenarios (asynchronous persistence, connection pooling, Redis clustering).

## Next Steps

1. ✅ Complete performance analysis (this document)
2. ⏭️ Evaluate Redis Streams as alternative (Task 9.7.1.1.2)
3. ⏭️ Evaluate Kafka as alternative (Task 9.7.1.1.3)
4. ⏭️ Make recommendation and plan migration (Task 9.7.1.1.4)


### Event Types Reference


## Overview

This document provides a comprehensive reference for all event types in the Data Interoperability Hub event system. All events follow a consistent schema structure and are validated before publishing.

## Event Schema Structure

All events follow this base structure:

```json
{
  "event_id": "uuid",
  "event_type": "domain.entity.action",
  "event_version": "1.0.0",
  "timestamp": "ISO 8601 datetime",
  "source": {
    "service": "service_name",
    "tenant_id": "uuid or null",
    "user_id": "uuid (optional)",
    "request_id": "string (optional)"
  },
  "data": {
    // Event-specific data
  },
  "metadata": {
    "correlation_id": "string (optional)",
    "causation_id": "uuid (optional)",
    "tags": ["string"] (optional)
  }
}
```

## Event Categories

### Contract Events

#### `contract.created`
Published when a contract is created.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `asset_id` (UUID)
- `status` (string)
- `original_format` (string)
- `original_spec_version` (string)

#### `contract.updated`
Published when a contract is updated.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `contract.deleted`
Published when a contract is deleted.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `contract.validated`
Published when a contract validation completes.

**Required Fields:**
- `contract_id` (UUID)
- `validation_result` (boolean)

**Optional Fields:**
- `validation_errors` (array of strings)
- `validation_warnings` (array of strings)

#### `contract.normalized`
Published when a contract normalization completes.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_status` (string)

**Optional Fields:**
- `normalization_errors` (array of strings or null)

### Asset Events

#### `asset.created`
Published when an asset is created.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `name` (string)
- `domain` (string)
- `status` (string)
- `contract_id` (UUID)

#### `asset.updated`
Published when an asset is updated.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `asset.activated`
Published when an asset is activated.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `activation_reason` (string)
- `dq_status` (string)
- `compliance_status` (string)

#### `asset.published`
Published when an asset is published to marketplace.

**Required Fields:**
- `asset_id` (UUID)
- `marketplace_listing_id` (UUID)

**Optional Fields:**
- `pricing_model` (string)
- `license_type` (string)

#### `asset.retired`
Published when an asset is retired.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `retirement_reason` (string)
- `retired_at` (ISO 8601 datetime)

### Dataset Events

#### `dataset.created`
Published when a dataset is created.

**Required Fields:**
- `dataset_id` (UUID)

**Optional Fields:**
- `asset_id` (UUID)
- `file_id` (UUID)
- `format` (string)
- `schema_inferred` (boolean)

#### `dataset.updated`
Published when a dataset is updated.

**Required Fields:**
- `dataset_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `file_id` (UUID)

#### `dataset.deleted`
Published when a dataset is deleted.

**Required Fields:**
- `dataset_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `dataset.uploaded`
Published when a dataset file is uploaded.

**Required Fields:**
- `dataset_id` (UUID)
- `file_id` (UUID)

**Optional Fields:**
- `file_size` (integer)
- `file_format` (string)
- `upload_duration_ms` (integer)

### Ingestion Events

#### `ingestion.started`
Published when an ingestion process starts.

**Required Fields:**
- `ingestion_id` (UUID)
- `source_type` (string)

**Optional Fields:**
- `source_config` (object)
- `scheduled_ingestion_id` (UUID)

#### `ingestion.completed`
Published when an ingestion process completes.

**Required Fields:**
- `ingestion_id` (UUID)
- `files_processed` (integer)

**Optional Fields:**
- `files_succeeded` (integer)
- `files_failed` (integer)
- `duration_ms` (integer)
- `datasets_created` (integer)

#### `ingestion.failed`
Published when an ingestion process fails.

**Required Fields:**
- `ingestion_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `retry_count` (integer)

#### `ingestion.file_processed`
Published when a single file is processed during ingestion.

**Required Fields:**
- `ingestion_id` (UUID)
- `file_id` (UUID)
- `status` (string)

**Optional Fields:**
- `dataset_id` (UUID)
- `error_message` (string)

#### `pipeline.started`
Published when a pipeline run (ingestion or data pipeline) starts.

**Required Fields:**
- `pipeline_id` (UUID) or `ingestion_id` (UUID)

**Optional Fields:**
- `source_type` (string)
- `started_at` (ISO 8601 datetime)

### Quality Events

#### `quality.check.started`
Published when a quality check starts.

**Required Fields:**
- `quality_check_id` (UUID)
- `target_type` (string)
- `target_id` (UUID)

**Optional Fields:**
- `rules_count` (integer)

#### `quality.check.completed`
Published when a quality check completes.

**Required Fields:**
- `quality_check_id` (UUID)
- `overall_score` (number)

**Optional Fields:**
- `rules_passed` (integer)
- `rules_failed` (integer)
- `duration_ms` (integer)

#### `quality.check.failed`
Published when a quality check fails.

**Required Fields:**
- `quality_check_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)

#### `quality.anomaly.detected`
Published when a quality anomaly is detected.

**Required Fields:**
- `quality_check_id` (UUID)
- `anomaly_type` (string)

**Optional Fields:**
- `anomaly_details` (object)
- `severity` (string)

### Compliance Events

#### `compliance.check.started`
Published when a compliance check starts.

**Required Fields:**
- `compliance_check_id` (UUID)
- `target_type` (string)
- `target_id` (UUID)

**Optional Fields:**
- `compliance_frameworks` (array of strings)

#### `compliance.check.completed`
Published when a compliance check completes.

**Required Fields:**
- `compliance_check_id` (UUID)
- `compliance_status` (string)

**Optional Fields:**
- `frameworks_passed` (array of strings)
- `frameworks_failed` (array of strings)
- `duration_ms` (integer)

#### `compliance.check.failed`
Published when a compliance check fails.

**Required Fields:**
- `compliance_check_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)

#### `compliance.report.generated`
Published when a compliance report is generated.

**Required Fields:**
- `report_id` (UUID)
- `report_type` (string)

**Optional Fields:**
- `compliance_framework` (string)
- `report_format` (string)
- `generated_at` (ISO 8601 datetime)

### Version Events

#### `version.created`
Published when a version is created.

**Required Fields:**
- `version_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `version_number` (string)
- `version_type` (string)

#### `version.updated`
Published when a version is updated.

**Required Fields:**
- `version_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_version` (string)
- `new_version` (string)

#### `version.rolled_back`
Published when a version is rolled back.

**Required Fields:**
- `version_id` (UUID)
- `target_version` (string)

**Optional Fields:**
- `rollback_reason` (string)

### Access Events

#### `access.requested`
Published when an access request is created.

**Required Fields:**
- `access_request_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `requester_id` (UUID)
- `request_reason` (string)

#### `access.granted`
Published when access is granted.

**Required Fields:**
- `access_request_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `granted_by` (UUID)
- `granted_at` (ISO 8601 datetime)

#### `access.revoked`
Published when access is revoked.

**Required Fields:**
- `access_request_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `revoked_by` (UUID)
- `revoked_at` (ISO 8601 datetime)
- `revocation_reason` (string)

#### `access.certified`
Published when access is certified.

**Required Fields:**
- `access_request_id` (UUID)
- `certification_type` (string)

**Optional Fields:**
- `certified_by` (UUID)
- `certified_at` (ISO 8601 datetime)

### Marketplace Events

#### `marketplace.listing.published`
Published when a marketplace listing is published.

**Required Fields:**
- `listing_id` (UUID)
- `asset_id` (UUID)

**Optional Fields:**
- `pricing_model` (string)
- `published_at` (ISO 8601 datetime)

#### `marketplace.listing.unpublished`
Published when a marketplace listing is unpublished.

**Required Fields:**
- `listing_id` (UUID)

**Optional Fields:**
- `unpublished_at` (ISO 8601 datetime)
- `reason` (string)

#### `marketplace.order.created`
Published when a marketplace order is created.

**Required Fields:**
- `order_id` (UUID)
- `listing_id` (UUID)
- `buyer_id` (UUID)

**Optional Fields:**
- `order_amount` (number)
- `currency` (string)

#### `marketplace.order.approved`
Published when a marketplace order is approved.

**Required Fields:**
- `order_id` (UUID)

**Optional Fields:**
- `approved_by` (UUID)
- `approved_at` (ISO 8601 datetime)

#### `marketplace.order.rejected`
Published when a marketplace order is rejected.

**Required Fields:**
- `order_id` (UUID)
- `rejected_by` (UUID)
- `rejection_reason` (string)

**Optional Fields:**
- `rejected_at` (ISO 8601 datetime)

#### `marketplace.order.fulfilled`
Published when a marketplace order is fulfilled.

**Required Fields:**
- `order_id` (UUID)

**Optional Fields:**
- `fulfilled_at` (ISO 8601 datetime)
- `entitlement_id` (UUID)

#### `marketplace.entitlement.granted`
Published when a marketplace entitlement is granted.

**Required Fields:**
- `entitlement_id` (UUID)
- `order_id` (UUID)
- `user_id` (UUID)

**Optional Fields:**
- `granted_at` (ISO 8601 datetime)
- `expires_at` (ISO 8601 datetime or null)

#### `marketplace.entitlement.revoked`
Published when a marketplace entitlement is revoked.

**Required Fields:**
- `entitlement_id` (UUID)
- `revoked_by` (UUID)

**Optional Fields:**
- `revoked_at` (ISO 8601 datetime)
- `revocation_reason` (string)

### Workflow Events

#### `workflow.started`
Published when a workflow instance starts.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `workflow_version` (string)
- `input_data` (object)

#### `workflow.completed`
Published when a workflow instance completes.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `workflow.failed`
Published when a workflow instance fails.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `failed_step_index` (integer or null)

#### `workflow.cancelled`
Published when a workflow instance is cancelled.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `cancelled_by` (UUID)
- `cancellation_reason` (string)

#### `workflow.step.completed`
Published when a workflow step completes.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `step_index` (integer)
- `step_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `workflow.step.failed`
Published when a workflow step fails.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `step_index` (integer)
- `step_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `retry_count` (integer)

### ODPS Events

#### `odps.created`
Published when an ODPS contract is created.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `odps_version` (string)
- `status` (string)
- `normalization_status` (string)

#### `odps.updated`
Published when an ODPS contract is updated.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `odps.deleted`
Published when an ODPS contract is deleted.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `odps.normalized`
Published when an ODPS contract normalization completes.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_status` (string)

**Optional Fields:**
- `normalization_errors` (array of strings or null)
- `spec_version` (string)

#### `odps.linked`
Published when an ODPS contract is linked to ODCS.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `odcs_reference` (string)
- `link_type` (string)

#### `odps.unlinked`
Published when an ODPS contract is unlinked from ODCS.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `odcs_reference` (string)
- `reason` (string)

#### `odps.ref.resolved`
Published when ODPS $ref resolution completes successfully.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `resolved_refs_count` (integer)
- `duration_ms` (integer)

#### `odps.ref.failed`
Published when ODPS $ref resolution fails.

**Required Fields:**
- `contract_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `failed_refs` (array of strings)
- `error_details` (object)

#### `odps.export.started`
Published when ODPS export starts.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)

**Optional Fields:**
- `export_options` (object)

#### `odps.export.completed`
Published when ODPS export completes successfully.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)

**Optional Fields:**
- `export_size` (integer)
- `duration_ms` (integer)
- `export_file_id` (UUID)

#### `odps.export.failed`
Published when ODPS export fails.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)

#### `odps.workflow.started`
Published when an ODPS workflow starts.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `workflow_version` (string)
- `input_data` (object)

#### `odps.workflow.completed`
Published when an ODPS workflow completes successfully.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `odps.workflow.failed`
Published when an ODPS workflow fails.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `failed_step_index` (integer or null)

#### `odps.workflow.step.completed`
Published when an ODPS workflow step completes.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `step_index` (integer)
- `step_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `odps.workflow.step.failed`
Published when an ODPS workflow step fails.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `step_index` (integer)
- `step_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `retry_count` (integer)

#### `odps.workflow.progress`
Published during ODPS workflow execution to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.creation.progress`
Published during ODPS contract creation to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.normalization.progress`
Published during ODPS normalization to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.ref.progress`
Published during ODPS $ref resolution to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `resolved_refs_count` (integer)
- `total_refs_count` (integer)

#### `odps.linking.status`
Published when ODPS linking status changes.

**Required Fields:**
- `contract_id` (UUID)
- `linking_status` (string)

**Optional Fields:**
- `linked_refs_count` (integer)

#### `odps.export.progress`
Published during ODPS export to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.semantic.mapping.progress`
Published during ODPS semantic mapping to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `mapped_entities_count` (integer)
- `total_entities_count` (integer)

#### `odps.semantic.mapped`
Published when ODPS semantic mapping completes.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `mapped_entities_count` (integer)
- `mapping_errors` (array of strings)

### Marketplace Integration Events

#### `marketplace.connection.created`
Published when a marketplace connection is created.

**Required Fields:**
- `connection_id` (UUID)
- `marketplace_type` (string)

**Optional Fields:**
- `name` (string)
- `created_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### `marketplace.connection.updated`
Published when a marketplace connection is updated.

**Required Fields:**
- `connection_id` (UUID)
- `changes` (object)

**Optional Fields:**
- `updated_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "changes": {
    "name": {
      "old": "Snowflake Production",
      "new": "Snowflake Production Updated"
    }
  },
  "updated_at": "2025-01-15T11:00:00Z"
}
```

#### `marketplace.connection.deleted`
Published when a marketplace connection is deleted.

**Required Fields:**
- `connection_id` (UUID)
- `marketplace_type` (string)
- `name` (string)

**Optional Fields:**
- `reason` (string)
- `deleted_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "reason": "User requested deletion",
  "deleted_at": "2025-01-15T12:00:00Z"
}
```

#### `marketplace.sync.started`
Published when a marketplace sync job starts.

**Required Fields:**
- `sync_job_id` (UUID)
- `connection_id` (UUID)
- `direction` (string)

**Optional Fields:**
- `started_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "sync_job_id": "660e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "started_at": "2025-01-15T10:00:00Z"
}
```

#### `marketplace.sync.completed`
Published when a marketplace sync job completes successfully.

**Required Fields:**
- `sync_job_id` (UUID)
- `connection_id` (UUID)
- `direction` (string)
- `status` (string)
- `items_synced` (integer)
- `items_failed` (integer)

**Optional Fields:**
- `completed_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "sync_job_id": "660e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "status": "COMPLETED",
  "items_synced": 100,
  "items_failed": 0,
  "completed_at": "2025-01-15T10:05:00Z"
}
```

#### `marketplace.sync.failed`
Published when a marketplace sync job fails.

**Required Fields:**
- `sync_job_id` (UUID)
- `connection_id` (UUID)
- `direction` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `failed_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "sync_job_id": "660e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "error_message": "Connection timeout",
  "error_details": {
    "error_code": "CONNECTION_TIMEOUT",
    "retry_count": 3
  },
  "failed_at": "2025-01-15T10:10:00Z"
}
```

#### `marketplace.sync.cancelled`
Published when a marketplace sync job is cancelled.

**Required Fields:**
- `sync_job_id` (UUID)
- `connection_id` (UUID)
- `direction` (string)

**Optional Fields:**
- `cancellation_reason` (string)
- `cancelled_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "sync_job_id": "660e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "cancellation_reason": "User requested cancellation",
  "cancelled_at": "2025-01-15T10:03:00Z"
}
```

#### `marketplace.mapping.created`
Published when a marketplace mapping is created.

**Required Fields:**
- `mapping_id` (UUID)
- `connection_id` (UUID)
- `hub_asset_id` (UUID)
- `external_listing_id` (string)

**Optional Fields:**
- `created_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "mapping_id": "770e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_asset_id": "880e8400-e29b-41d4-a716-446655440000",
  "external_listing_id": "SNOWFLAKE_LISTING_123",
  "created_at": "2025-01-15T10:00:00Z"
}
```

#### `marketplace.mapping.updated`
Published when a marketplace mapping is updated.

**Required Fields:**
- `mapping_id` (UUID)
- `connection_id` (UUID)
- `changes` (object)

**Optional Fields:**
- `updated_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "mapping_id": "770e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "changes": {
    "external_listing_id": {
      "old": "SNOWFLAKE_LISTING_123",
      "new": "SNOWFLAKE_LISTING_456"
    }
  },
  "updated_at": "2025-01-15T10:15:00Z"
}
```

#### `marketplace.mapping.deleted`
Published when a marketplace mapping is deleted.

**Required Fields:**
- `mapping_id` (UUID)
- `connection_id` (UUID)
- `hub_asset_id` (UUID)
- `external_listing_id` (string)

**Optional Fields:**
- `reason` (string)
- `deleted_at` (ISO 8601 datetime)

**Event Data Schema:**
```json
{
  "mapping_id": "770e8400-e29b-41d4-a716-446655440000",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_asset_id": "880e8400-e29b-41d4-a716-446655440000",
  "external_listing_id": "SNOWFLAKE_LISTING_123",
  "reason": "Asset deleted",
  "deleted_at": "2025-01-15T11:00:00Z"
}
```

### Data Mesh Events

#### `domain.created`
Published when a data mesh domain is created.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `name` (string)
- `status` (string)
- `owner_id` (UUID)

#### `domain.updated`
Published when a data mesh domain is updated.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `domain.deleted`
Published when a data mesh domain is deleted.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `policy.applied`
Published when a policy is applied to a domain.

**Required Fields:**
- `policy_application_id` (UUID)
- `domain_id` (UUID)

**Optional Fields:**
- `policy_id` (UUID)
- `status` (string)

#### `policy.revoked`
Published when a policy is revoked from a domain.

**Required Fields:**
- `policy_application_id` (UUID)
- `domain_id` (UUID)

**Optional Fields:**
- `policy_id` (UUID)
- `reason` (string)

#### `mesh.compliance.checked`
Published when mesh compliance is checked.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `compliance_status` (string)
- `violation_count` (integer)
- `checked_at` (ISO 8601 datetime)

#### `mesh.topology.updated`
Published when mesh topology is updated.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `relationship_count` (integer)
- `topology_changes` (object)

#### `mesh.domain.created`
Published when a mesh domain is created (internal event).

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `name` (string)
- `status` (string)
- `owner_id` (UUID)

#### `mesh.domain.updated`
Published when a mesh domain is updated (internal event).

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `mesh.policy.applied`
Published when a mesh policy is applied (internal event).

**Required Fields:**
- `policy_application_id` (UUID)
- `domain_id` (UUID)

**Optional Fields:**
- `policy_id` (UUID)
- `status` (string)

#### `mesh.compliance.checked`
Published when mesh compliance is checked (internal event).

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `compliance_status` (string)
- `violation_count` (integer)
- `checked_at` (ISO 8601 datetime)

#### `mesh.health.status_changed`
Published when mesh health status changes.

**Required Fields:**
- `domain_id` (UUID)
- `health_status` (string)

**Optional Fields:**
- `previous_status` (string)
- `health_metrics` (object)

### Virtualization Events

#### `virtualization.dataset.created`
Published when a virtual dataset is created.

**Required Fields:**
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `name` (string)
- `query_type` (string)
- `status` (string)
- `version` (string)

#### `virtualization.dataset.updated`
Published when a virtual dataset is updated.

**Required Fields:**
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `virtualization.dataset.deleted`
Published when a virtual dataset is deleted.

**Required Fields:**
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `virtualization.query.execution.started`
Published when a virtualization query execution starts.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `execution_mode` (string)
- `started_at` (ISO 8601 datetime)

#### `virtualization.query.execution.progress`
Published during virtualization query execution to report progress.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)
- `completed_steps` (integer)
- `total_steps` (integer)

#### `virtualization.query.execution.completed`
Published when a virtualization query execution completes successfully.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `result_count` (integer)
- `duration_ms` (integer)
- `completed_at` (ISO 8601 datetime)

#### `virtualization.query.execution.failed`
Published when a virtualization query execution fails.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `duration_ms` (integer)
- `failed_at` (ISO 8601 datetime)

#### `virtualization.query.execution.cancelled`
Published when a virtualization query execution is cancelled.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `cancelled_by` (UUID)
- `cancellation_reason` (string)
- `cancelled_at` (ISO 8601 datetime)

### File Events

#### `file.created`
Published when a file is created.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `name` (string)
- `content_type` (string)
- `size` (integer)
- `status` (string)
- `content_sha256` (string)

#### `file.updated`
Published when a file is updated.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `file.deleted`
Published when a file is deleted.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `file.uploaded`
Published when a file is uploaded.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `file_size` (integer)
- `content_type` (string)
- `upload_duration_ms` (integer)
- `content_sha256` (string)

#### `file.downloaded`
Published when a file is downloaded.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `download_duration_ms` (integer)
- `download_size` (integer)

### Lineage Events

#### `lineage.updated`
Published when lineage is updated.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `model_name` (string)
- `field_name` (string)
- `lineage_type` (string)
- `changes` (object)
- `relationship_count` (integer)

#### `lineage.relationship_added`
Published when a lineage relationship is added.

**Required Fields:**
- `contract_id` (UUID)
- `source_reference` (string)
- `target_reference` (string)

**Optional Fields:**
- `relationship_type` (string)
- `model_name` (string)
- `field_name` (string)

#### `lineage.relationship_removed`
Published when a lineage relationship is removed.

**Required Fields:**
- `contract_id` (UUID)
- `source_reference` (string)
- `target_reference` (string)

**Optional Fields:**
- `relationship_type` (string)
- `model_name` (string)
- `field_name` (string)

### Search Events

#### `search.query`
Published when a search query is executed.

**Required Fields:**
- `query` (string)

**Optional Fields:**
- `query_type` (string)
- `result_count` (integer)
- `duration_ms` (integer)

#### `search.index.updated`
Published when a search index is updated.

**Required Fields:**
- `index_name` (string)

**Optional Fields:**
- `document_count` (integer)
- `update_type` (string)

#### `search.index.rebuilt`
Published when a search index is rebuilt.

**Required Fields:**
- `index_name` (string)

**Optional Fields:**
- `document_count` (integer)
- `duration_ms` (integer)

### Payment Gateway Events

#### `payment.gateway.linked`
Published when a payment gateway is linked.

**Required Fields:**
- `gateway_id` (UUID)
- `gateway_type` (string)

**Optional Fields:**
- `linked_at` (ISO 8601 datetime)

#### `payment.gateway.unlinked`
Published when a payment gateway is unlinked.

**Required Fields:**
- `gateway_id` (UUID)

**Optional Fields:**
- `unlinked_at` (ISO 8601 datetime)
- `reason` (string)

#### `payment.gateway.webhook.received`
Published when a payment gateway webhook is received.

**Required Fields:**
- `gateway_id` (UUID)
- `webhook_type` (string)

**Optional Fields:**
- `webhook_data` (object)
- `received_at` (ISO 8601 datetime)

### Tenant Events

#### `tenant.created`
Published when a tenant is created.

**Required Fields:**
- `tenant_id` (UUID)

**Optional Fields:**
- `name` (string)
- `slug` (string)
- `status` (string)
- `kyc_status` (string)
- `region` (string)

#### `tenant.updated`
Published when a tenant is updated.

**Required Fields:**
- `tenant_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `tenant.deleted`
Published when a tenant is deleted.

**Required Fields:**
- `tenant_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `tenant.quota.changed`
Published when a tenant quota changes.

**Required Fields:**
- `tenant_id` (UUID)
- `quota_type` (string)
- `quota_field` (string)

**Optional Fields:**
- `previous_value` (any)
- `new_value` (any)

### Normalization Events

#### `normalization.started`
Published when normalization starts.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_type` (string)

**Optional Fields:**
- `spec_version` (string)
- `source_format` (string)

#### `normalization.completed`
Published when normalization completes successfully.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_status` (string)

**Optional Fields:**
- `normalization_errors` (array of strings)
- `normalization_warnings` (array of strings)
- `duration_ms` (integer)
- `spec_version` (string)

#### `normalization.failed`
Published when normalization fails.

**Required Fields:**
- `contract_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `normalization_errors` (array of strings)
- `retry_count` (integer)
- `spec_version` (string)

### Payment Events

#### `payment.initiated`
Published when a payment is initiated.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)

**Optional Fields:**
- `amount` (number)
- `currency` (string)
- `gateway` (string)
- `payment_method` (string)

#### `payment.completed`
Published when a payment completes successfully.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)
- `status` (string)

**Optional Fields:**
- `amount` (number)
- `currency` (string)
- `gateway` (string)
- `gateway_transaction_id` (string)
- `processed_at` (ISO 8601 datetime)

#### `payment.failed`
Published when a payment fails.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `amount` (number)
- `currency` (string)
- `gateway` (string)
- `failed_at` (ISO 8601 datetime)

#### `payment.refunded`
Published when a payment is refunded.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)

**Optional Fields:**
- `refund_amount` (number)
- `currency` (string)
- `gateway` (string)
- `gateway_refund_id` (string)
- `refund_reason` (string)
- `refunded_at` (ISO 8601 datetime)

### Observability Events

#### `observability.metric.recorded`
Published when a metric is recorded.

**Required Fields:**
- `metric_name` (string)

**Optional Fields:**
- `metric_value` (number)
- `metric_type` (string)
- `labels` (object)

#### `observability.trace.created`
Published when a trace is created.

**Required Fields:**
- `trace_id` (UUID)
- `span_id` (UUID)

**Optional Fields:**
- `operation_name` (string)
- `duration_ms` (number)
- `status` (string)
- `attributes` (object)

#### `observability.log.created`
Published when a log entry is created.

**Required Fields:**
- `message` (string)

**Optional Fields:**
- `log_level` (string)
- `logger_name` (string)
- `context` (object)

#### `observability.alert.triggered`
Published when an alert is triggered.

**Required Fields:**
- `alert_name` (string)
- `alert_severity` (string)

**Optional Fields:**
- `alert_message` (string)
- `metric_name` (string)
- `threshold_value` (number)
- `current_value` (number)

### Integration Events

Events for integrations, connectors, sync, and marketplace integration (e.g. `integration.sync.started`, `integration.sync.completed`).

### BaaS Events

Events for BaaS platform: usage, tier, API key, developer portal (e.g. `baas.usage.recorded`, `baas.tier.updated`).

### ML Events

Events for ML/ODH: training, inference, model registry (e.g. `ml.training.started`, `ml.inference.completed`).

## Event Schema Versioning

All events use semantic versioning (e.g., `1.0.0`). The current version is `1.0.0`.

### Version Management

- **Current Version**: `1.0.0`
- **Supported Versions**: `["1.0.0"]`
- **Migration**: Events can be migrated between versions using `EventSchemaVersionManager`

## Usage Examples

### Publishing Events from Services

```python
from hub.apps.core.services.base import BaseService
from hub.apps.core.events.service_publishers import ContractEventPublisher

class ContractService(BaseService, ContractEventPublisher):
    def create_contract(self, ...):
        # ... create contract ...
        contract_id = contract.id

        # Publish event
        self.publish_contract_created(
            contract_id=str(contract_id),
            status="ACTIVE",
            tenant_id=tenant_id,
            user_id=user_id
        )

        return contract
```

### Subscribing to Events

```python
from hub.apps.core.events.subscribers import WebhookSubscriber

# Create subscriber
subscriber = WebhookSubscriber(webhook_service=webhook_service)
subscriber.start()  # Start listening
```

### Using Decorator-Based Subscribers

```python
from hub.apps.core.events.subscriber import event_subscriber

@event_subscriber("contract.*")
def handle_contract_events(event):
    # Handle all contract events
    print(f"Received: {event['event_type']}")
```

## Event Validation

All events are validated before publishing:

1. **Base Schema Validation**: Validates event structure (event_id, event_type, timestamp, etc.)
2. **Event Type Schema Validation**: Validates event-specific data fields
3. **Type Validation**: Validates field types match schema

Invalid events are rejected with descriptive error messages.

## Best Practices

1. **Always include required fields**: Ensure all required fields are present in event data
2. **Use proper types**: Use correct data types (UUID strings, ISO 8601 datetimes, etc.)
3. **Include context**: Include tenant_id, user_id, and request_id when available
4. **Use correlation IDs**: Use correlation_id to track related events
5. **Handle failures gracefully**: Event publishing failures should not block business logic

## Event Flow

1. **Service publishes event** → Event data validated → Event persisted → Event published to Redis
2. **Subscribers receive event** → Event processed → Handler executed
3. **Failed events** → Retry logic → Dead letter queue if all retries fail

## Related Documentation

- [Event Bus Architecture](EVENT_BUS.md)
- [Event Bus Implementation Summary](EVENT_BUS_IMPLEMENTATION_SUMMARY.md)

### Phase 117+ Event Types (Added)

| Event | Source | Description |
|-------|--------|-------------|
| `ABAC_EVALUATION.FIELD_MASKING_APPLIED` | ABAC engine (G2) | Audit event when field-level masking is applied; includes masked fields, policy ID, strategies |
| `ACCESS_REQUEST.ACCESS_EXPIRED_REVOKED` | `revoke_expired_access` command (G3) | APPROVED requests past `expires_at` transitioned to REVOKED |
| `ML_MODEL.MODEL_DEPLOYED` | `deploy_model()` (ML-1) | Model status TRAINED→DEPLOYED, deployment_id stored |
| `ML_MODEL.DATASET_LINKED` | `link_model_to_dataset()` | Model linked to training/validation/test dataset |
| `BILLING.REFUND_PROCESSED` | RefundViewSet (B3) | Refund issued for subscription or marketplace order |
| `BILLING.USAGE_RECORDED` | `record_usage()` | ML inference requests/compute metered for billing |
| `COMPLIANCE.RUN_COMPLETED` | ComplianceRunViewSet | Compliance scan completed with risk level |
| `MARKETPLACE.LISTING_PUBLISHED` | `publish_model_to_marketplace()` (ML-13) | ML model published as marketplace listing |
| `ODPS.CONTRACT_NORMALIZED` | Normalization service | ODPS contract normalized to hub-contract format |
| `INGESTION.RUN_COMPLETED` | Scheduled ingestion worker | Ingestion run completed with row counts |
| `EXPORT.RUN_COMPLETED` | Scheduled export worker | Export run completed with item counts |

---

## 5. Workflow Orchestration


**Version:** 2.0.0
**Last Updated:** 2026-01-27
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Business Rules Integration](#business-rules-integration)
4. [Validation Behavior](#validation-behavior)
5. [Error Handling](#error-handling)
6. [Workflow Execution](#workflow-execution)
7. [Compensation and Rollback](#compensation-and-rollback)
8. [Observability](#observability)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Workflow Orchestration system provides a robust, production-grade framework for executing multi-step operations with comprehensive validation, error handling, compensation, and observability. All workflows integrate seamlessly with the Business Rules Framework to ensure consistent validation and business logic enforcement.

### Key Features

- **Business Rules Integration**: Automatic validation at every workflow step using the Business Rules Framework
- **Comprehensive Validation**: Pre-step, post-step, and workflow state validation
- **Error Handling**: Detailed error messages with validation context
- **Compensation**: Automatic rollback using Saga pattern with business rules validation
- **Observability**: Metrics, events, logs, and distributed tracing
- **Performance**: Validation caching with <5% overhead per step
- **Gateway Independence**: Workflow execution is completely independent of whether requests arrive via Traefik API Gateway or direct api-service access

### Workflow Engine

**Location**: `hub/apps/orchestration/workflow_engine.py`

The `WorkflowEngine` class orchestrates workflow execution with integrated business rules validation at every step.

---

## Architecture

### Gateway Independence

**Workflow execution is completely independent of request routing.**

Workflows can be triggered via:
- **Direct api-service access**: Frontend → api-service (Django)
- **Via Traefik API Gateway**: Frontend → Traefik → API Gateway (FastAPI) → api-service (Django)

**Key Points:**
- Workflow execution methods (`execute()`, `execute_start()`, etc.) take only workflow-specific parameters (tenant_id, user_id, workflow data)
- No request objects are passed to workflow execution methods
- No gateway headers (`X-Gateway-*`) are accessed in workflow code
- No URL building depends on request host
- Workflow execution is purely data-driven based on `WorkflowInstance` model

**Testing:**
- All workflow E2E and integration tests work identically whether triggered via gateway or direct access
- Tests explicitly verify gateway independence (see `hub/apps/orchestration/tests/test_workflow_gateway_independence.py`)
- Workflow execution results are identical regardless of request source

**Documentation:**
- See `openspec/changes/workflows1/artifacts/WORKFLOW_GATEWAY_REVIEW.md` for detailed review
- See `docs/API_GATEWAY_TRAEFIK.md` for API Gateway routing details

### Workflow Components

```
┌─────────────────────────────────────────────────────────┐
│                  Workflow Engine                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Workflow    │  │   Business   │  │  Validation  │ │
│  │   Execution   │  │    Rules     │  │    Layer     │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                  │                  │         │
│         └──────────────────┼──────────────────┘         │
│                            │                              │
│                   ┌────────▼────────┐                    │
│                   │  Step Execution  │                    │
│                   │   with Validation│                    │
│                   └─────────────────┘                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Metrics     │    │    Events    │    │    Logs     │
│  (Prometheus) │    │  (Event Bus) │    │ (Structured)│
└──────────────┘    └──────────────┘    └──────────────┘
```

### Workflow Lifecycle

1. **Create Instance**: Workflow instance created with input data
2. **Start Instance**: Workflow status set to RUNNING
3. **Execute Steps**: Each step executed with validation:
   - Pre-step validation (workflow state, step input)
   - Step execution
   - Post-step validation (step output, workflow state)
4. **Compensation**: On failure, rollback with validation
5. **Complete**: Workflow marked as COMPLETED or FAILED

---

## Business Rules Integration

### Integration Points

Business rules are integrated at three key points in workflow execution:

1. **Pre-Step Validation**: Before executing a workflow step
2. **Post-Step Validation**: After executing a workflow step
3. **Compensation Validation**: During workflow rollback

### OrchestrationBusinessRules

**Location**: `hub/apps/orchestration/business_rules.py`

The `OrchestrationBusinessRules` class provides workflow-specific validation methods:

- `validate_workflow_step_execution()`: Validates step can execute
- `validate_step_input()`: Validates step input data
- `validate_step_output()`: Validates step output data
- `validate_workflow_state()`: Validates workflow state consistency

### Integration in Workflow Engine

The `WorkflowEngine._execute_task_step()` method integrates business rules validation:

```python
def _execute_task_step(
    self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a task step with business rules validation"""

    # Get tenant and user for business rules validation
    tenant = instance.tenant
    user = instance.created_by

    # Create business rules instance with tenant/user context
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )

    # Pre-step validation: Validate workflow state
    workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
    if not workflow_state_result.is_valid:
        raise WorkflowExecutionError(...)

    # Pre-step validation: Validate step input
    step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)
    if not step_input_result.is_valid:
        raise WorkflowExecutionError(...)

    # Execute task
    result = task_func(task_input, instance, step)

    # Post-step validation: Validate step output
    step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
    if not step_output_result.is_valid:
        raise WorkflowExecutionError(...)

    # Post-step validation: Validate workflow state after step
    post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
    if not post_workflow_state_result.is_valid:
        raise WorkflowExecutionError(...)

    return result
```

### Service-Specific Business Rules

Workflows can also use service-specific business rules for domain validation:

```python
# Example: Using ODPSBusinessRules in ProductCreationWorkflow
from hub.apps.contracts.business_rules import ODPSBusinessRules

odps_rules = ODPSBusinessRules(
    tenant_id=str(tenant.id),
    user_id=str(user.id)
)

# Validate ODPS document before parsing
odps_result = odps_rules.validate_odps_document(odps_document)
if not odps_result.is_valid:
    raise ValueError(f"ODPS validation failed: {', '.join(odps_result.errors)}")
```

---

## Validation Behavior

### Validation Phases

Workflow execution includes validation at multiple phases:

#### 1. Pre-Step Validation

**Purpose**: Ensure workflow and step are ready for execution

**Validations**:
- **Workflow State**: Workflow status is RUNNING, state is consistent
- **Step Execution**: Step can execute in current workflow state
- **Step Input**: Input data structure and schema validation
- **Tenant Context**: Tenant consistency validation
- **User Permissions**: User has permission to execute step

**Example**:
```python
# Validate workflow state before step execution
workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
# Validates:
# - Workflow status is RUNNING
# - Workflow state_data is consistent
# - Step indices match workflow current_step_index
# - Completed steps are in correct order
```

#### 2. Step Input Validation

**Purpose**: Ensure step input data is valid

**Validations**:
- Input is a dictionary
- Input is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)

**Example**:
```python
# Validate step input data
step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)
# Validates:
# - task_input is a dict
# - task_input is JSON serializable
# - Input size is reasonable (<10MB)
```

#### 3. Step Output Validation

**Purpose**: Ensure step output data is valid

**Validations**:
- Output is a dictionary
- Output is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)

**Example**:
```python
# Validate step output data
step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
# Validates:
# - result is a dict
# - result is JSON serializable
# - Output size is reasonable (<10MB)
```

#### 4. Post-Step Validation

**Purpose**: Ensure workflow state is consistent after step execution

**Validations**:
- Workflow state is consistent
- Step status is COMPLETED
- State data is valid
- Step output merged correctly into state_data

**Example**:
```python
# Validate workflow state after step
post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
# Validates:
# - Workflow state_data includes step output
# - Step status transition is valid (PENDING → COMPLETED)
# - Workflow current_step_index is updated
```

### Validation Caching

Validation results are cached to improve performance:

- **Cache Key**: Generated from rule name, workflow ID, step index, and validation type
- **Cache TTL**: Configurable per rule (default: 300 seconds)
- **Cache Invalidation**: Automatic expiration, manual invalidation on state changes

**Performance**: Validation overhead is <5% per step with caching enabled.

---

## Error Handling

### Error Propagation

Validation errors from business rules are propagated to workflow execution errors:

```python
# Validation failure raises WorkflowExecutionError
if not workflow_state_result.is_valid:
    error_message = self._format_validation_error(
        "workflow state validation",
        workflow_state_result,
        instance,
        step
    )
    raise WorkflowExecutionError(error_message)
```

### Error Message Format

Error messages include comprehensive context:

```
Business rules validation failed (workflow state validation) |
Rule: OrchestrationBusinessRules |
Workflow: product_creation (id: 123e4567-e89b-12d3-a456-426614174000) |
Step: parse_odps (index: 0) |
Errors: Workflow step cannot execute: workflow status is DRAFT, expected RUNNING |
Warnings: Step index (0) does not match workflow current_step_index (1)
```

### Error Details

Workflow errors include detailed validation information:

```python
# Error details structure
{
    "validation_type": "workflow_state",
    "rule_name": "OrchestrationBusinessRules",
    "errors": ["Workflow step cannot execute: workflow status is DRAFT"],
    "warnings": ["Step index mismatch"],
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "step_id": "789e0123-e45f-67g8-h901-234567890123",
    "step_name": "parse_odps",
    "step_index": 0
}
```

### Structured Logging

All validation errors are logged with structured logging:

```python
logger.error(
    "Workflow validation failed",
    workflow_instance_id=str(instance.id),
    workflow_name=instance.workflow_name,
    workflow_version=instance.workflow_version,
    step_name=step.step_name,
    step_index=step.step_index,
    rule_name=rule_name,
    validation_type=validation_type,
    errors=validation_result.errors,
    warnings=validation_result.warnings,
    validation_details=validation_result.details,
    tenant_id=tenant_id_str,
)
```

### Error Recovery

Workflows support error recovery:

1. **Retry**: Workflow can be retried after fixing validation issues
2. **Compensation**: Automatic rollback on failure
3. **State Recovery**: Workflow state can be recovered from last successful step

---

## Workflow Execution

### Creating a Workflow Instance

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()

# Create workflow instance
instance = engine.create_instance(
    workflow_name="product_creation",
    input_data={
        "odps_document": {...},
        "asset_id": "asset-123"
    },
    tenant_id="tenant-123",
    created_by_id="user-456"
)
```

### Starting Workflow Execution

```python
# Start workflow execution
instance = engine.start_instance(str(instance.id))

# Execute workflow (synchronously or asynchronously)
engine.execute_instance(str(instance.id))
```

### Workflow DSL

Workflows are defined using a JSON/YAML DSL:

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "parse_odps",
      "type": "task",
      "task": "product_creation.parse_odps",
      "input": {
        "odps_document": "{{input.odps_document}}"
      }
    },
    {
      "name": "validate_odcs",
      "type": "task",
      "task": "product_creation.validate_odcs",
      "input": {
        "odcs_contract": "{{state.odcs_contract}}"
      }
    }
  ]
}
```

### Task Functions

Task functions receive workflow context and return step output:

```python
def parse_odps_task(
    input_data: Dict[str, Any],
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Parse ODPS document with business rules validation"""

    # Get tenant and user for business rules
    tenant = instance.tenant
    user = instance.created_by

    # Use service-specific business rules
    from hub.apps.contracts.business_rules import ODPSBusinessRules

    odps_rules = ODPSBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )

    # Validate ODPS document
    odps_document = input_data.get("odps_document")
    validation_result = odps_rules.validate_odps_document(odps_document)

    if not validation_result.is_valid:
        raise ValueError(f"ODPS validation failed: {', '.join(validation_result.errors)}")

    # Parse ODPS document
    parsed_odps = parse_odps_document(odps_document)

    # Return step output (merged into state_data)
    return {
        "parsed_odps": parsed_odps,
        "odps_version": parsed_odps.get("version")
    }
```

---

## Compensation and Rollback

### Compensation with Business Rules

Compensation validates using business rules but does not block rollback:

```python
def rollback_workflow(
    self,
    instance: WorkflowInstance,
    failed_step: WorkflowStep
) -> WorkflowInstance:
    """Rollback workflow using compensation logic (Saga pattern)"""

    # Create business rules instance
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )

    # Validate compensation can execute (warnings don't block)
    compensation_validation_result = business_rules.validate_workflow_state(instance, tenant, user)
    if not compensation_validation_result.is_valid:
        # Log validation errors but don't block compensation
        logger.warning(
            f"Compensation validation errors: {', '.join(compensation_validation_result.errors)}"
        )

    # Compensate each completed step
    for step in completed_steps:
        compensation_result = self._compensate_step(instance, step)
```

### Compensation Step Validation

Each compensation step is validated using business rules:

```python
def _compensate_step(
    self,
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Compensate a workflow step with business rules validation"""

    # Validate compensation step
    compensation_step_result = business_rules.validate_workflow_step_execution(
        instance, step, tenant, user
    )

    if compensation_step_result.warnings:
        # Log warnings but proceed with compensation
        logger.warning(
            f"Compensation step validation warnings: {', '.join(compensation_step_result.warnings)}"
        )

    # Execute compensation logic
    compensation_result = self._execute_compensation_task(instance, step, compensation_def)

    # Include validation results in compensation logs
    return {
        "status": "compensated",
        "result": compensation_result,
        "validation": {
            "is_valid": compensation_step_result.is_valid,
            "warnings": compensation_step_result.warnings
        }
    }
```

---

## Observability

### Metrics

Workflow validation metrics are recorded in Prometheus:

- **`workflow_business_rules_validations_total`** (Counter)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `result` (valid/invalid), `tenant_id`

- **`workflow_business_rules_validation_duration_seconds`** (Histogram)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `result`, `tenant_id`

- **`workflow_business_rules_validation_cache_hits_total`** (Counter)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `tenant_id`

- **`workflow_business_rules_validation_cache_misses_total`** (Counter)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `tenant_id`

### Events

Workflow events include validation results:

- **`workflow.step.started`**: Includes validation status
- **`workflow.step.completed`**: Includes validation results
- **`workflow.step.failed`**: Includes validation errors

**Example Event**:
```json
{
  "event_type": "workflow.step.completed",
  "workflow_instance_id": "123e4567-e89b-12d3-a456-426614174000",
  "workflow_name": "product_creation",
  "step_name": "parse_odps",
  "step_index": 0,
  "validation": {
    "workflow_state": {
      "is_valid": true,
      "duration_seconds": 0.002
    },
    "step_input": {
      "is_valid": true,
      "duration_seconds": 0.001
    },
    "step_output": {
      "is_valid": true,
      "duration_seconds": 0.001
    }
  }
}
```

### Structured Logging

All workflow operations are logged with structured logging:

```python
logger.info(
    "Workflow step validation completed",
    workflow_instance_id=str(instance.id),
    workflow_name=instance.workflow_name,
    step_name=step.step_name,
    step_index=step.step_index,
    validation_type="workflow_state",
    rule_name="OrchestrationBusinessRules",
    is_valid=True,
    duration_seconds=0.002,
    cached=False
)
```

### Distributed Tracing

Validation spans are created in OpenTelemetry traces:

```python
validation_span = tracer.start_span(
    name="workflow.validation.workflow_state",
    attributes={
        "workflow.instance_id": str(instance.id),
        "workflow.name": instance.workflow_name,
        "workflow.step.name": step.step_name,
        "workflow.step.index": step.step_index,
        "business_rules.rule_name": rule_name,
        "business_rules.validation_type": "workflow_state",
    },
)
```

---

## Best Practices

### 1. Always Use Business Rules for Validation

**Do**:
```python
# Use business rules for validation
business_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = business_rules.validate_workflow_state(instance, tenant, user)
if not result.is_valid:
    raise WorkflowExecutionError(...)
```

**Don't**:
```python
# Don't skip validation
if instance.status != WorkflowStatus.RUNNING:
    raise WorkflowExecutionError("Invalid status")
```

### 2. Use Service-Specific Business Rules in Task Functions

**Do**:
```python
def create_contract_task(input_data, instance, step):
    from hub.apps.contracts.business_rules import ContractsBusinessRules

    contract_rules = ContractsBusinessRules(tenant_id=tenant_id, user_id=user_id)
    validation_result = contract_rules.validate_contract_creation(contract_data)
    if not validation_result.is_valid:
        raise ValueError(f"Contract validation failed: {', '.join(validation_result.errors)}")
```

**Don't**:
```python
# Don't duplicate validation logic in task functions
def create_contract_task(input_data, instance, step):
    if not contract_data.get("name"):
        raise ValueError("Contract name is required")
```

### 3. Handle Validation Warnings Appropriately

**Do**:
```python
# Log warnings but don't block execution
if validation_result.warnings:
    logger.warning(f"Validation warnings: {', '.join(validation_result.warnings)}")
```

**Don't**:
```python
# Don't treat warnings as errors
if validation_result.warnings:
    raise WorkflowExecutionError("Validation warnings found")
```

### 4. Include Validation Context in Error Messages

**Do**:
```python
# Use _format_validation_error for consistent error messages
error_message = self._format_validation_error(
    "workflow state validation",
    validation_result,
    instance,
    step
)
raise WorkflowExecutionError(error_message)
```

**Don't**:
```python
# Don't create generic error messages
raise WorkflowExecutionError("Validation failed")
```

### 5. Use Structured Logging

**Do**:
```python
logger.error(
    "Workflow validation failed",
    workflow_instance_id=str(instance.id),
    step_name=step.step_name,
    errors=validation_result.errors,
    tenant_id=tenant_id_str,
)
```

**Don't**:
```python
logger.error(f"Validation failed for workflow {instance.id}")
```

---

## Troubleshooting

### Common Issues

#### 1. Validation Failures Blocking Workflow Execution

**Symptom**: Workflow fails with validation errors

**Root Cause**: Business rules validation is failing

**Solution**:
1. Check validation error messages in workflow error_details
2. Verify workflow state is consistent
3. Check tenant and user context
4. Review business rules validation logic

**Example**:
```python
# Check workflow error details
instance = WorkflowInstance.objects.get(id=workflow_id)
if instance.error_details:
    validation_errors = instance.error_details.get("validation_errors", [])
    for error in validation_errors:
        print(f"Validation error: {error}")
```

#### 2. Performance Degradation from Validation

**Symptom**: Workflow execution is slow

**Root Cause**: Validation overhead without caching

**Solution**:
1. Enable validation caching (default: enabled)
2. Check cache hit rates in metrics
3. Review validation logic for performance bottlenecks
4. Consider optimizing validation logic

**Example**:
```python
# Check cache hit rates
# Prometheus query:
# rate(workflow_business_rules_validation_cache_hits_total[5m]) /
# rate(workflow_business_rules_validations_total[5m])
```

#### 3. Compensation Validation Warnings

**Symptom**: Compensation logs show validation warnings

**Root Cause**: Workflow state may be inconsistent during rollback

**Solution**:
1. Review compensation validation warnings (warnings don't block compensation)
2. Verify compensation logic handles inconsistent state
3. Check workflow state after compensation

**Example**:
```python
# Check compensation validation warnings
compensation_logs = instance.error_details.get("compensation_results", [])
for result in compensation_logs:
    if result.get("validation", {}).get("warnings"):
        warnings = result["validation"]["warnings"]
        logger.warning(f"Compensation warnings: {warnings}")
```

#### 4. Validation Errors Not Propagating

**Symptom**: Validation errors not appearing in workflow error messages

**Root Cause**: Error formatting or propagation issue

**Solution**:
1. Check `_format_validation_error` method
2. Verify `WorkflowExecutionError` includes validation context
3. Check structured logs for validation errors

**Example**:
```python
# Check structured logs
# Search for: "Workflow validation failed"
# Should include: errors, warnings, validation_details
```

### Debugging Workflow Validation

1. **Enable Debug Logging**:
   ```python
   import logging
   logging.getLogger("hub.apps.orchestration").setLevel(logging.DEBUG)
   ```

2. **Check Validation Results**:
   ```python
   # In workflow execution, check validation results
   validation_results = instance.state_data.get("validation_results", {})
   for validation_type, result in validation_results.items():
       print(f"{validation_type}: is_valid={result['result'].is_valid}")
   ```

3. **Review Metrics**:
   ```python
   # Check Prometheus metrics
   # workflow_business_rules_validations_total
   # workflow_business_rules_validation_duration_seconds
   ```

4. **Inspect Traces**:
   ```python
   # Check OpenTelemetry traces
   # Look for spans: workflow.validation.*
   ```

---

## Related Documentation

- [Business Rules Framework Guide](BUSINESS_RULES_FRAMEWORK_GUIDE.md) - Complete guide to business rules
- [Business Logic Integration](BUSINESS_LOGIC_INTEGRATION.md) - Service layer coordination
- [Workflow Migration Guide](WORKFLOW_MIGRATION_GUIDE.md) - Migrating workflows to use business rules
- [Monitoring Guide](MONITORING.md) - Monitoring workflows and validation metrics

---

**Last Updated**: 2026-03-22
**Maintainer**: Platform Team

### Phase 117+ Architecture Flows (Added)

#### Data Classification Propagation (G5)

```
Dataset (PII classified)
  └─ link_model_to_dataset()
       └─ propagate_classification()
            ├─ Find highest classification on source dataset
            └─ update_or_create classification on target asset
                 └─ category=PII, provenance="propagated from DATASET:{id}"
```

When an ML model is linked to a training dataset, the highest data classification (e.g., PII, PHI) automatically propagates from the dataset to the model's asset.

#### ML Model Lineage Graph (ML-10)

```
DATASET ──TRAINS_TRAINING──→ ML_MODEL ──PRODUCES──→ ASSET
DATASET ──TRAINS_VALIDATION──→ ML_MODEL
DATASET ──TRAINS_TEST──→ ML_MODEL
```

`add_ml_model_lineage()` creates edge records from `ModelDatasetLink` relationships. Called automatically from `link_model_to_dataset()`.

#### ML Model Deployment Lifecycle (ML-1/ML-3)

```
TRAINING → TRAINED → DEPLOYED → TRAINED (undeploy)
                  ↗ (deploy_version: atomic undeploy v1 + deploy v2)
```

- `deploy_model()`: TRAINED→DEPLOYED, stores `deployment_id`
- `undeploy_model()`: DEPLOYED→TRAINED, clears `deployment_id`
- `deploy_version()`: atomic version switch (undeploy all current, deploy target)
- `rollback_deployment()`: delegates to `deploy_version(target_version)`

#### Transformation Pipeline (Phase 115)

```
Source Data → Wrangling Session → Preview → Pipeline Execution → Output Dataset
```

Transformation pipelines support node-based DAG operations with validation, preview, and execution phases.

---

## 6. Job Queue


## Overview

The Data Interoperability Hub uses a Redis-backed job queue system (django-rq) for processing asynchronous jobs. This document describes the job priority queue architecture, retry configuration, strategy, and monitoring.

## Job Priority Queue Architecture

### Priority Levels

The system supports three priority levels:
- **HIGH**: Critical long-running jobs (DQ runs, compliance runs)
- **NORMAL**: Standard jobs (semantic mapping, contract migration, scheduled ingestion, etc.)
- **LOW**: Quick validation jobs (contract validation)

### Priority Assignment Rules

Priority is assigned using the following rules (in order):
1. **Explicit Priority**: If priority is explicitly provided when creating a job, use it
2. **Job Type Rules**: If job_type has a priority rule in `JOB_PRIORITY_RULES`, use it
3. **Default Priority**: Otherwise, use `JOB_PRIORITY_DEFAULT` (default: NORMAL)

### Priority Queue Implementation

The priority queue system uses **separate physical Redis queues** per priority level:
- **job_critical**: HIGH priority jobs
- **job_default**: NORMAL priority jobs
- **job_low**: LOW priority jobs

This approach provides:
- **Simple implementation**: No complex priority sorting logic needed
- **Worker selection**: Workers poll queues in priority order (job_critical → job_default → job_low)
- **Concurrency control**: Reserved slots for HIGH priority jobs (50% of max concurrency by default)
- **Starvation prevention**: NORMAL priority jobs are elevated to HIGH after 5-minute wait threshold

### Priority Queue Configuration

Priority configuration is defined in `hub/settings.py`:

```python
# Default priority for jobs when not explicitly specified
JOB_PRIORITY_DEFAULT = "NORMAL"

# Priority assignment rules by job type
JOB_PRIORITY_RULES = {
    # HIGH priority: Critical long-running jobs
    "DQ_RUN": "HIGH",
    "COMPLIANCE_RUN": "HIGH",
    # NORMAL priority: Standard jobs (default)
    "SEMANTIC_MAPPING": "NORMAL",
    "CONTRACT_MIGRATION": "NORMAL",
    # ... other job types
    # LOW priority: Quick validation jobs
    "CONTRACT_VALIDATION": "LOW",
}
```

### Priority Queue Monitoring

The following Prometheus metrics track priority queue behavior:

- **`job_queue_length_by_priority`** (Gauge): Current number of jobs in queue by priority
  - Labels: `priority`, `job_type`
  - Example: `job_queue_length_by_priority{priority="HIGH", job_type="DQ_RUN"}`

- **`job_processing_rate_by_priority`** (Counter): Total number of jobs processed per second by priority
  - Labels: `priority`, `job_type`
  - Example: `job_processing_rate_by_priority{priority="HIGH", job_type="DQ_RUN"}`

### Using Priority in Job Creation

```python
from hub.apps.jobs.utils import create_job
from hub.apps.jobs.models import JobPriority

# Create job with explicit priority
job = create_job(
    job_type="DQ_RUN",
    resource_type="DATASET",
    resource_id=str(resource_id),
    priority=JobPriority.HIGH  # Explicit priority
)

# Create job with priority determined from job_type rules
job = create_job(
    job_type="DQ_RUN",  # Will use HIGH priority from JOB_PRIORITY_RULES
    resource_type="DATASET",
    resource_id=str(resource_id)
)
```

## Job Retry Strategy

### Exponential Backoff

The system uses an exponential backoff strategy for retrying failed jobs. The retry delay increases exponentially with each retry attempt:

**Formula**: `delay = base_delay * (2 ^ retry_count)`

**Example delays** (with base delay of 60 seconds):
- Retry 1: 60 seconds (1 minute)
- Retry 2: 120 seconds (2 minutes)
- Retry 3: 240 seconds (4 minutes)
- Retry 4: 480 seconds (8 minutes)

### Retry Configuration

Retry configuration is centralized in Django settings and can be customized per job type:

- **`JOB_RETRY_MAX_ATTEMPTS`**: Maximum number of retry attempts per job type (dict)
- **`JOB_RETRY_INITIAL_DELAY`**: Initial delay before first retry per job type (dict, in seconds)
- **`JOB_RETRY_MAX_DELAY`**: Maximum delay cap per job type (dict, in seconds)
- **`JOB_RETRY_BACKOFF_FACTOR`**: Exponential backoff factor per job type (dict, default: 2)

### Default Retry Configuration

Default retry settings (can be overridden in `settings.py`):

```python
JOB_RETRY_MAX_ATTEMPTS = {
    'DQ_RUN': 3,
    'COMPLIANCE_RUN': 3,
    'CONTRACT_VALIDATION': 2,
    'SEMANTIC_MAPPING': 2,
    'CONTRACT_MIGRATION': 1,
    'SCHEDULED_INGESTION': 2,
    'RETENTION_POLICY_ENFORCEMENT': 1,
    'SEARCH_INDEX_UPDATE': 2,
    'ODPS_NORMALIZATION': 2,
    'ODPS_REF_RESOLUTION': 2,
    'ODPS_EXPORT': 2,
    'ODPS_SEMANTIC_MAPPING': 2,
    'ODPS_LINKING': 2,
    'TRANSFORMATION_PIPELINE_EXECUTION': 2,
    'VIRTUAL_QUERY_EXECUTION': 2,
}

JOB_RETRY_INITIAL_DELAY = {
    'DQ_RUN': 60,  # 1 minute
    'COMPLIANCE_RUN': 60,  # 1 minute
    'CONTRACT_VALIDATION': 30,  # 30 seconds
    'SEMANTIC_MAPPING': 30,  # 30 seconds
    'CONTRACT_MIGRATION': 60,  # 1 minute
    'SCHEDULED_INGESTION': 120,  # 2 minutes
    'RETENTION_POLICY_ENFORCEMENT': 60,  # 1 minute
    'SEARCH_INDEX_UPDATE': 30,  # 30 seconds
    'ODPS_NORMALIZATION': 60,  # 1 minute
    'ODPS_REF_RESOLUTION': 60,  # 1 minute
    'ODPS_EXPORT': 30,  # 30 seconds
    'ODPS_SEMANTIC_MAPPING': 60,  # 1 minute
    'ODPS_LINKING': 30,  # 30 seconds
    'TRANSFORMATION_PIPELINE_EXECUTION': 60,  # 1 minute
    'VIRTUAL_QUERY_EXECUTION': 60,  # 1 minute
}

JOB_RETRY_MAX_DELAY = {
    'DQ_RUN': 3600,  # 1 hour
    'COMPLIANCE_RUN': 3600,  # 1 hour
    'CONTRACT_VALIDATION': 600,  # 10 minutes
    'SEMANTIC_MAPPING': 600,  # 10 minutes
    'CONTRACT_MIGRATION': 1800,  # 30 minutes
    'SCHEDULED_INGESTION': 3600,  # 1 hour
    'RETENTION_POLICY_ENFORCEMENT': 1800,  # 30 minutes
    'SEARCH_INDEX_UPDATE': 600,  # 10 minutes
    'ODPS_NORMALIZATION': 1800,  # 30 minutes
    'ODPS_REF_RESOLUTION': 1800,  # 30 minutes
    'ODPS_EXPORT': 600,  # 10 minutes
    'ODPS_SEMANTIC_MAPPING': 1800,  # 30 minutes
    'ODPS_LINKING': 600,  # 10 minutes
    'TRANSFORMATION_PIPELINE_EXECUTION': 1800,  # 30 minutes
    'VIRTUAL_QUERY_EXECUTION': 1800,  # 30 minutes
}

JOB_RETRY_BACKOFF_FACTOR = {
    'DQ_RUN': 2,
    'COMPLIANCE_RUN': 2,
    'CONTRACT_VALIDATION': 2,
    'SEMANTIC_MAPPING': 2,
    'CONTRACT_MIGRATION': 2,
    'SCHEDULED_INGESTION': 2,
    'RETENTION_POLICY_ENFORCEMENT': 2,
    'SEARCH_INDEX_UPDATE': 2,
    'ODPS_NORMALIZATION': 2,
    'ODPS_REF_RESOLUTION': 2,
    'ODPS_EXPORT': 2,
    'ODPS_SEMANTIC_MAPPING': 2,
    'ODPS_LINKING': 2,
    'TRANSFORMATION_PIPELINE_EXECUTION': 2,
    'VIRTUAL_QUERY_EXECUTION': 2,
}
```

### Retry Delay Calculation

The retry delay is calculated using exponential backoff with configurable factors:

```python
delay = initial_delay * (backoff_factor ^ retry_count)
delay = min(delay, max_delay)  # Cap at max_delay
```

**Example** (DQ_RUN with default config):
- Retry 1: `60 * (2 ^ 0) = 60` seconds (capped at 3600)
- Retry 2: `60 * (2 ^ 1) = 120` seconds (capped at 3600)
- Retry 3: `60 * (2 ^ 2) = 240` seconds (capped at 3600)

### Retry Timeout Configuration

Each job type has a maximum timeout that applies to both initial execution and retries:

- **`JOB_TIMEOUTS`**: Maximum execution time per job type (dict, in seconds)

See `hub/apps/jobs/utils.py` for default timeout values.

### Retry Failure Handling

#### Transient vs Non-Transient Failures

The system distinguishes between transient and non-transient failures:

**Transient failures** (will retry):
- `ConnectionError`: Service unavailable, network issues
- `TimeoutError`: Request timeout, service slow to respond
- Errors containing keywords: 'temporary', 'retry', 'service unavailable', '503', '502', '504'

**Non-transient failures** (will not retry):
- `ValueError`: Validation errors, invalid input
- `PermissionError`: Authorization failures
- `FileNotFoundError`: Missing files/resources
- Errors containing keywords: 'permission', 'not found', 'invalid', 'validation'

#### Retry Exhaustion

When retry attempts are exhausted:
1. Job status is set to `FAILED`
2. Error message is stored in `job.error_message`
3. Retry count and last retry timestamp are stored in `job.details_json`
4. Job is moved to dead letter queue (if configured)
5. Audit event is created for retry exhaustion

#### Retry State Tracking

Retry information is stored in `job.details_json`:
- `retry_count`: Current retry attempt number (0-indexed)
- `last_retry_error`: Error message from last retry attempt
- `last_retry_at`: ISO timestamp of last retry attempt

## Monitoring

### Retry Metrics

The following Prometheus metrics track job retry behavior:

- **`job_retry_count`** (Histogram): Number of retries for job processing
  - Labels: `job_type`, `queue_name`
  - Buckets: 0, 1, 2, 3, 5, 10

- **`job_retry_delay_seconds`** (Histogram): Retry delay duration in seconds
  - Labels: `job_type`
  - Buckets: 30, 60, 120, 300, 600, 1800, 3600

- **`job_retry_failures_total`** (Counter): Total number of jobs that failed after retries
  - Labels: `job_type`, `error_type`

### Retry Monitoring Dashboards

Job retry metrics are available in Grafana dashboards:
- **ODPS Job Queue Dashboard**: Shows retry count distribution for ODPS jobs
- **Job Processing Dashboard**: Shows retry metrics for all job types

## Configuration

### Environment Variables

Retry configuration can be overridden via environment variables (see `hub/settings.py`):

```bash
# Example: Override max retries for DQ_RUN
JOB_RETRY_MAX_ATTEMPTS_DQ_RUN=5

# Example: Override initial delay for ODPS_NORMALIZATION
JOB_RETRY_INITIAL_DELAY_ODPS_NORMALIZATION=120
```

### Django Settings

Retry configuration is defined in `hub/settings.py`:

```python
# Job Retry Configuration
JOB_RETRY_MAX_ATTEMPTS = {
    'DQ_RUN': 3,
    'COMPLIANCE_RUN': 3,
    # ... other job types
}

JOB_RETRY_INITIAL_DELAY = {
    'DQ_RUN': 60,
    'COMPLIANCE_RUN': 60,
    # ... other job types
}

JOB_RETRY_MAX_DELAY = {
    'DQ_RUN': 3600,
    'COMPLIANCE_RUN': 3600,
    # ... other job types
}

JOB_RETRY_BACKOFF_FACTOR = {
    'DQ_RUN': 2,
    'COMPLIANCE_RUN': 2,
    # ... other job types
}
```

## Usage

### Checking Retry Configuration

```python
from hub.apps.jobs.utils import get_job_max_retries, calculate_retry_delay

# Get max retries for a job type
max_retries = get_job_max_retries('DQ_RUN')  # Returns 3

# Calculate retry delay
delay = calculate_retry_delay(retry_count=1, base_delay=60)  # Returns 120
```

### Retrying a Job

The `retry_job()` function handles retry logic automatically:

```python
from hub.apps.jobs.utils import retry_job

# Retry a failed job
retried = retry_job(job_obj, job_type='DQ_RUN', exception=exception)
if retried:
    # Job was scheduled for retry
    pass
else:
    # No retries remaining or error is not transient
    pass
```

## Best Practices

1. **Configure appropriate retry limits**: Set max retries based on job criticality and expected failure rates
2. **Use exponential backoff**: Prevents overwhelming services during outages
3. **Monitor retry metrics**: Track retry rates and delays to identify issues
4. **Distinguish transient vs non-transient failures**: Only retry transient failures
5. **Set reasonable timeouts**: Ensure timeouts allow for retries without excessive delays
6. **Document custom retry logic**: If overriding defaults, document the rationale

## Troubleshooting

### High Retry Rates

If retry rates are high:
1. Check service health and availability
2. Review error types in `job_retry_failures_total` metric
3. Verify timeout configurations are appropriate
4. Consider increasing retry delays for overloaded services

### Retry Exhaustion

If many jobs exhaust retries:
1. Review `job_retry_failures_total` metric for error patterns
2. Check if failures are transient or non-transient
3. Consider increasing max retries for critical job types
4. Investigate root cause of persistent failures

### Retry Delays Too Long

If retry delays are causing issues:
1. Review `job_retry_delay_seconds` histogram
2. Consider reducing `JOB_RETRY_INITIAL_DELAY` for faster retries
3. Adjust `JOB_RETRY_BACKOFF_FACTOR` to reduce exponential growth
4. Set lower `JOB_RETRY_MAX_DELAY` to cap delays

## Related Documentation

- [Worker Service README](../services/worker/README.md)
- [Job Queue Monitoring Dashboards](../monitoring/grafana/dashboards/odps-job-queue.json)
- [Job Models](../hub/apps/jobs/models.py)
- [Job Utilities](../hub/apps/jobs/utils.py)


---

## 7. Caching Strategy


**Version:** 1.0.0
**Last Updated:** 2026-01-02
**Task:** 9.8.4.3 - Implement Cache Warming Strategy

---

## Overview

This document describes the cache warming strategy for ODPS external $ref resolution. Cache warming pre-populates the Redis cache with frequently accessed external references to improve response times and reduce external API calls.

## Cache Warming Strategy

### Objectives

1. **Improve Response Times**: Pre-populate cache with frequently accessed refs to reduce cache misses
2. **Reduce External API Calls**: Minimize requests to external URLs by ensuring popular refs are cached
3. **Optimize Resource Usage**: Focus warming efforts on refs that provide the most value

### Frequently Accessed Refs Identification

Frequently accessed refs are identified using Redis sorted sets that track access counts per URL:

- **Access Tracking**: Each external ref URL access increments a counter in Redis sorted set
- **Key Format**: `odps_ref_access:all` (sorted set with URL hash as member, access count as score)
- **URL Mapping**: `odps_ref_access:url:{url_hash}` stores the actual URL for hash lookup
- **TTL**: Access tracking data expires after 24 hours (same as cache stats)

### Cache Warming Triggers

Cache warming is performed in three scenarios:

#### 1. Application Startup

- **Trigger**: When Django application starts (via AppConfig.ready())
- **Scope**: Top 100 most frequently accessed refs
- **Timing**: Asynchronous background task to avoid blocking startup
- **Configuration**: Controlled by `ODPS_CACHE_WARMING_ENABLED` setting (default: True)

#### 2. Scheduled Warming

- **Trigger**: Daily scheduled job (via Django management command or cron)
- **Scope**: Top 1000 most frequently accessed refs
- **Timing**: Runs once per day during low-traffic hours (configurable)
- **Configuration**: Controlled by `ODPS_CACHE_WARMING_SCHEDULED_ENABLED` setting (default: True)

#### 3. On-Demand Warming

- **Trigger**: When a ref is accessed but not in cache (cache miss)
- **Scope**: Single ref being accessed
- **Timing**: Immediate, synchronous (non-blocking)
- **Configuration**: Always enabled (part of normal ref resolution flow)

### Cache Warming Batch Size

- **Startup**: 100 refs (configurable via `ODPS_CACHE_WARMING_STARTUP_LIMIT`)
- **Scheduled**: 1000 refs (configurable via `ODPS_CACHE_WARMING_SCHEDULED_LIMIT`)
- **On-Demand**: 1 ref (immediate warming on cache miss)

### Cache Warming Process

1. **Identify Frequently Accessed Refs**:
   - Query Redis sorted set `odps_ref_access:all`
   - Sort by access count (score) descending
   - Take top N refs based on batch size

2. **Resolve and Cache Refs**:
   - For each ref URL:
     - Check if already cached (skip if cached)
     - Resolve ref using RefResolver.resolve_external()
     - Cache result automatically via RefResolver._set_cache()
     - Handle errors gracefully (log and continue)

3. **Progress Reporting**:
   - Log progress every 10 refs
   - Report success/failure counts
   - Track total time taken

### Error Handling

- **Individual Ref Failures**: Log warning and continue with next ref
- **Redis Unavailable**: Skip warming gracefully (cache will populate naturally)
- **Rate Limit Exceeded**: Respect rate limits, skip refs that would exceed limits
- **Invalid URLs**: Skip invalid URLs, log warning

### Configuration

Settings in `hub/settings.py`:

```python
# Cache warming configuration
ODPS_CACHE_WARMING_ENABLED = True  # Enable cache warming
ODPS_CACHE_WARMING_STARTUP_ENABLED = True  # Enable startup warming
ODPS_CACHE_WARMING_SCHEDULED_ENABLED = True  # Enable scheduled warming
ODPS_CACHE_WARMING_STARTUP_LIMIT = 100  # Number of refs to warm on startup
ODPS_CACHE_WARMING_SCHEDULED_LIMIT = 1000  # Number of refs to warm in scheduled job
ODPS_CACHE_WARMING_BATCH_SIZE = 10  # Process refs in batches of N
```

### Management Command

Cache warming can be triggered manually via management command:

```bash
# Warm top 100 refs (default)
python manage.py warm_odps_ref_cache

# Warm top N refs
python manage.py warm_odps_ref_cache --limit 500

# Warm refs matching URL pattern
python manage.py warm_odps_ref_cache --url-pattern "https://example.com/*"

# Dry-run mode (no actual warming)
python manage.py warm_odps_ref_cache --dry-run

# Warm for specific tenant
python manage.py warm_odps_ref_cache --tenant-id <uuid>
```

### Monitoring

Cache warming effectiveness is monitored via:

- **Metrics**: `odps_ref_cache_hit_rate` gauge (should increase after warming)
- **Logs**: Structured logging for warming operations
- **Redis Stats**: Access counts in `odps_ref_access:all` sorted set

### Performance Considerations

- **Startup Warming**: Runs asynchronously to avoid blocking application startup
- **Scheduled Warming**: Runs during low-traffic hours to minimize impact
- **On-Demand Warming**: Immediate but non-blocking (part of normal flow)
- **Batch Processing**: Processes refs in configurable batches to avoid overwhelming Redis/network

### Future Enhancements

- **Predictive Warming**: Use ML to predict which refs will be accessed
- **Tenant-Specific Warming**: Warm refs per tenant based on tenant access patterns
- **Time-Based Warming**: Warm refs based on time-of-day access patterns
- **Cost-Aware Warming**: Prioritize warming based on external API costs

---

## Implementation Details

### Access Tracking

Per-URL access tracking is implemented in `RefResolver._track_ref_access()`:

- Tracks access count per URL using Redis sorted set
- Stores URL mapping for hash-to-URL lookup
- Expires after 24 hours (same as cache stats)

### Cache Warming Functions

Located in `hub/apps/contracts/ref_warming.py`:

- `get_frequently_accessed_refs(limit: int, min_access_count: int = 1) -> List[str]`: Get top N frequently accessed ref URLs
- `warm_ref_cache(ref_urls: List[str], tenant_id: Optional[str] = None) -> Dict[str, Any]`: Warm cache for list of ref URLs
- `warm_cache_on_startup()`: Startup cache warming (called from AppConfig.ready())

### Management Command

Located in `hub/apps/contracts/management/commands/warm_odps_ref_cache.py`:

- Supports multiple warming modes (limit, URL pattern, tenant-specific)
- Dry-run mode for testing
- Progress reporting and error handling

---

## References

- [ODPS $ref Resolution Rate Limiting Design](contracts/docs/ODPS_RATE_LIMITING_DESIGN.md)
- [ODPS Cache Performance Dashboard](../../monitoring/grafana/dashboards/odps-cache-performance.json)


---

## 8. Architecture Decision Records


### ADR: Event Bus Architecture


**Date:** 2025-12-30
**Task:** 9.7.1.1.4 - Make architecture decision
**Status:** ✅ **DECISION COMPLETE**

## Executive Summary

This document provides a comprehensive architecture decision for the Event Bus implementation, comparing all evaluated options (Redis Pub/Sub, Redis Streams, Apache Kafka, RabbitMQ) across multiple dimensions and providing a clear decision with rationale and migration plan.

## Decision

**Primary Decision: Continue with Redis Pub/Sub for current implementation, with a clear migration path to Redis Streams when requirements justify.**

**Rationale:**
- Current throughput (~1,500-2,000 events/sec) is sufficient for current needs
- Low operational complexity and infrastructure overhead
- Clear migration path to Redis Streams (same infrastructure, low migration effort)
- Kafka/RabbitMQ provide significant benefits but with high complexity/overhead that is not justified at current scale

## Comprehensive Comparison Matrix

### Performance Comparison

| Metric | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
|--------|---------------|--------------|--------------|----------|
| **Throughput** | ~1,500-2,000 events/sec | ~1,279 events/sec (-7%) | 100,000+ events/sec | 10,000-50,000 events/sec |
| **Average Latency** | <10ms (Pub/Sub only) | <150ms (+50ms) | 10-100ms | 1-10ms |
| **P95 Latency** | <20ms | <200ms | 50-200ms | 5-20ms |
| **Persistence** | PostgreSQL only | PostgreSQL + Redis | Built-in (disk) | Built-in (optional) |
| **Replay** | Limited (PostgreSQL) | Excellent (Redis Streams) | Excellent (offsets) | Limited (custom) |

### Scalability Comparison

| Metric | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
|--------|---------------|--------------|--------------|----------|
| **Horizontal Scaling** | Limited (single instance) | Limited (single instance) | Excellent (unlimited brokers) | Good (clustering, ~10 nodes) |
| **Partitioning** | None | None | Yes (partitions) | Limited (queue sharding) |
| **Consumer Groups** | None | Yes (built-in) | Yes (built-in) | Yes (queues) |
| **Message Ordering** | None | Per-stream | Per-partition | Per-queue |
| **Backpressure** | None | None | Built-in | Built-in |

### Feature Comparison

| Feature | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
|--------|---------------|--------------|--------------|----------|
| **Persistence** | PostgreSQL (separate) | PostgreSQL + Redis | Built-in (disk) | Built-in (optional) |
| **Consumer Groups** | ❌ | ✅ | ✅ | ✅ |
| **Message Replay** | Limited | ✅ Excellent | ✅ Excellent | Limited |
| **Message Acknowledgment** | ❌ | ✅ | ✅ | ✅ |
| **Pending Entries Tracking** | ❌ | ✅ | ✅ | ✅ |
| **Dead Letter Queue** | ✅ (PostgreSQL) | ✅ (Redis + PostgreSQL) | ✅ (custom) | ✅ (built-in) |
| **Routing** | Simple (channels) | Simple (streams) | Simple (topics) | Advanced (exchanges) |
| **Reliability** | Medium (single Redis) | Medium (single Redis) | High (replication) | High (quorum queues) |
| **Exactly-Once Semantics** | ❌ | ❌ | ✅ | ❌ |

### Complexity Comparison

| Aspect | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
|--------|---------------|--------------|--------------|----------|
| **Implementation Complexity** | Low | Low-Medium | High | Medium |
| **Configuration Complexity** | Low | Low-Medium | High | Medium |
| **Operational Complexity** | Low | Low-Medium | High | Medium |
| **Migration Complexity** | N/A | Low-Medium (10-20 hours) | High (7-11 days) | Medium (5-8 days) |
| **Learning Curve** | Low | Low-Medium | High | Medium |

### Infrastructure Overhead

| Aspect | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
|--------|---------------|--------------|--------------|----------|
| **Additional Services** | None (uses existing Redis) | None (uses existing Redis) | Kafka cluster (3+ brokers), Zookeeper/KRaft | RabbitMQ cluster (3+ nodes), Erlang runtime |
| **CPU Requirements** | Low (1 core) | Low-Medium (1-2 cores) | High (2-4 cores per broker) | Medium (1-2 cores per node) |
| **Memory Requirements** | Low (minimal) | Medium (persistence overhead) | High (4-8GB per broker) | Medium (2-4GB per node) |
| **Disk Requirements** | None (PostgreSQL handles) | Medium (Redis persistence) | High (100GB+ per broker) | Medium (10-50GB per node) |
| **Network Requirements** | Low | Low-Medium | High (replication) | Medium (clustering) |
| **Infrastructure Complexity** | Low | Low | High | Medium |

### Operational Complexity

| Aspect | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
|--------|---------------|--------------|--------------|----------|
| **Monitoring** | Low (Redis metrics) | Low-Medium (Redis + Streams metrics) | High (broker, topic, consumer lag, replication lag) | Medium (node, queue, exchange metrics) |
| **Maintenance** | Low (minimal) | Low-Medium (stream trimming) | High (disk usage, log cleanup, rebalancing) | Medium (queue cleanup, cluster health) |
| **Troubleshooting** | Low | Low-Medium | High (requires Kafka expertise) | Medium (good management UI) |
| **Deployment** | Low (single Redis) | Low (same Redis) | High (cluster deployment) | Medium (cluster deployment) |

## Detailed Factor Analysis

### 1. Performance

**Redis Pub/Sub:**
- ✅ Excellent latency (<10ms)
- ✅ Good throughput (~1,500-2,000 events/sec)
- ⚠️ Limited scalability (single instance)
- ⚠️ No message ordering guarantees

**Redis Streams:**
- ✅ Good latency (<150ms)
- ⚠️ Slightly lower throughput (~7% slower than Pub/Sub)
- ⚠️ Limited scalability (single instance)
- ✅ Message ordering per stream

**Apache Kafka:**
- ✅ Excellent throughput (100,000+ events/sec)
- ⚠️ Higher latency (10-100ms)
- ✅ Excellent scalability (horizontal)
- ✅ Message ordering per partition

**RabbitMQ:**
- ✅ Excellent latency (1-10ms)
- ✅ Good throughput (10,000-50,000 events/sec)
- ✅ Good scalability (clustering)
- ✅ Message ordering per queue

**Verdict:** Redis Pub/Sub sufficient for current needs. Kafka best for high throughput, RabbitMQ best for low latency.

### 2. Scalability

**Redis Pub/Sub:**
- ⚠️ Limited to single instance (can use Redis Cluster)
- ⚠️ No partitioning
- ⚠️ No consumer groups

**Redis Streams:**
- ⚠️ Limited to single instance (can use Redis Cluster)
- ⚠️ No partitioning
- ✅ Consumer groups support

**Apache Kafka:**
- ✅ Excellent horizontal scalability
- ✅ Partitioning support
- ✅ Consumer groups support

**RabbitMQ:**
- ✅ Good scalability (clustering)
- ⚠️ Limited partitioning (queue sharding)
- ✅ Consumer groups (queues)

**Verdict:** Kafka best for horizontal scalability. Redis Pub/Sub/Streams sufficient for current scale.

### 3. Complexity

**Redis Pub/Sub:**
- ✅ Lowest complexity
- ✅ Simple implementation
- ✅ Minimal configuration

**Redis Streams:**
- ✅ Low-Medium complexity
- ✅ Similar to Pub/Sub
- ✅ Minimal additional configuration

**Apache Kafka:**
- ⚠️ High complexity
- ⚠️ Complex implementation
- ⚠️ Many configuration options

**RabbitMQ:**
- ⚠️ Medium complexity
- ⚠️ Exchange/queue/binding concepts
- ⚠️ Moderate configuration

**Verdict:** Redis Pub/Sub/Streams simplest. Kafka most complex.

### 4. Infrastructure Overhead

**Redis Pub/Sub:**
- ✅ No additional services
- ✅ Uses existing Redis
- ✅ Minimal resource requirements

**Redis Streams:**
- ✅ No additional services
- ✅ Uses existing Redis
- ⚠️ Moderate memory overhead (persistence)

**Apache Kafka:**
- ⚠️ Requires Kafka cluster (3+ brokers)
- ⚠️ Requires Zookeeper/KRaft
- ⚠️ High resource requirements

**RabbitMQ:**
- ⚠️ Requires RabbitMQ cluster (3+ nodes)
- ⚠️ Requires Erlang runtime
- ⚠️ Moderate resource requirements

**Verdict:** Redis Pub/Sub/Streams lowest overhead. Kafka highest overhead.

### 5. Operational Complexity

**Redis Pub/Sub:**
- ✅ Low monitoring requirements
- ✅ Minimal maintenance
- ✅ Easy troubleshooting

**Redis Streams:**
- ✅ Low-Medium monitoring requirements
- ✅ Low-Medium maintenance (stream trimming)
- ✅ Easy troubleshooting

**Apache Kafka:**
- ⚠️ High monitoring requirements
- ⚠️ High maintenance (disk, rebalancing)
- ⚠️ Complex troubleshooting

**RabbitMQ:**
- ⚠️ Medium monitoring requirements
- ⚠️ Medium maintenance
- ✅ Good management UI

**Verdict:** Redis Pub/Sub/Streams simplest to operate. Kafka most complex.

## Decision Rationale

### Current State Assessment

**Current Requirements:**
- Throughput: ~1,500-2,000 events/sec (current implementation handles this)
- Latency: <100ms average (current: <10ms Pub/Sub only)
- Scalability: Single instance sufficient for current scale
- Replay: Limited needs (PostgreSQL-based replay sufficient)
- Consumer Groups: Not currently required
- Message Ordering: Not currently required

**Current Implementation Strengths:**
- ✅ Meets all current performance requirements
- ✅ Low operational complexity
- ✅ Minimal infrastructure overhead
- ✅ Simple to maintain and troubleshoot
- ✅ Proven reliability

**Current Implementation Limitations:**
- ⚠️ No consumer groups (load balancing)
- ⚠️ Limited replay capabilities (PostgreSQL only)
- ⚠️ No message acknowledgment
- ⚠️ Limited observability (pending entries tracking)

### Decision Factors

**1. Performance Requirements:**
- Current throughput (~1,500-2,000 events/sec) is sufficient
- No immediate need for higher throughput
- Latency requirements met (<10ms)

**2. Scalability Requirements:**
- Current scale does not require horizontal scaling
- Single instance sufficient
- Can scale vertically if needed

**3. Feature Requirements:**
- Consumer groups: Not currently required
- Message replay: Limited needs (PostgreSQL sufficient)
- Message acknowledgment: Not currently required
- Better observability: Would be beneficial but not critical

**4. Complexity Tolerance:**
- Prefer low complexity solutions
- Limited operational resources
- Prefer simple maintenance

**5. Infrastructure Constraints:**
- Prefer minimal infrastructure overhead
- Prefer using existing infrastructure (Redis)
- Limited budget for new services

**6. Migration Readiness:**
- Need clear migration path
- Prefer low-risk migrations
- Prefer gradual migration capability

### Decision Matrix Scoring

**Scoring Criteria (1-5 scale, 5 = best):**

| Factor | Weight | Redis Pub/Sub | Redis Streams | Kafka | RabbitMQ |
|--------|--------|---------------|---------------|-------|----------|
| **Performance** | 20% | 4 (meets requirements) | 4 (slightly slower) | 5 (excellent) | 4 (good) |
| **Scalability** | 15% | 3 (limited) | 3 (limited) | 5 (excellent) | 4 (good) |
| **Features** | 15% | 3 (basic) | 4 (good) | 5 (excellent) | 4 (good) |
| **Complexity** | 20% | 5 (lowest) | 4 (low-medium) | 2 (high) | 3 (medium) |
| **Infrastructure** | 15% | 5 (lowest) | 5 (lowest) | 2 (high) | 3 (medium) |
| **Operations** | 15% | 5 (lowest) | 4 (low-medium) | 2 (high) | 3 (medium) |
| **Total Score** | 100% | **4.15** | **4.10** | **3.50** | **3.60** |

**Decision:** Redis Pub/Sub scores highest (4.15), followed closely by Redis Streams (4.10). Kafka (3.50) and RabbitMQ (3.60) score lower due to complexity and infrastructure overhead.

## Migration Strategy

### Phase 1: Current State (Redis Pub/Sub)
**Duration:** Immediate (current state)
**Actions:**
- Continue using Redis Pub/Sub
- Monitor performance metrics
- Track throughput and latency trends
- Identify future requirements

**Success Criteria:**
- ✅ Throughput remains <2,000 events/sec
- ✅ Latency remains <100ms
- ✅ No consumer group requirements
- ✅ PostgreSQL replay sufficient

### Phase 2: Evaluation & Preparation (Redis Streams)
**Duration:** 3-6 months
**Trigger:** When any of the following occur:
- Consumer groups needed (load balancing)
- Better replay capabilities needed
- Message acknowledgment required
- Better observability needed
- Throughput approaching 2,000 events/sec

**Actions:**
- Monitor for trigger conditions
- Prepare Redis Streams implementation
- Create migration plan
- Allocate resources

**Success Criteria:**
- ✅ Trigger conditions identified
- ✅ Migration plan created
- ✅ Resources allocated
- ✅ Implementation ready

### Phase 3: Migration (Redis Streams)
**Duration:** 1-3 days (10-20 hours effort)
**Approach:** Gradual migration with dual mode operation

**Migration Steps:**
1. **Deploy Streams Implementation**
   - Deploy `EventStreamsBus` alongside `EventBus`
   - Use same Redis instance
   - Enable dual mode operation

2. **Migrate Publishers**
   - Update event publishers to use Streams
   - Maintain backward compatibility
   - Feature flag for gradual rollout

3. **Migrate Subscribers**
   - Migrate consumers one by one
   - Add consumer group configuration
   - Handle message acknowledgment

4. **Validation**
   - Monitor both systems
   - Validate performance
   - Validate functionality

5. **Completion**
   - Remove Pub/Sub implementation
   - Clean up old code
   - Update documentation

**Success Criteria:**
- ✅ All publishers migrated
- ✅ All subscribers migrated
- ✅ Performance maintained or improved
- ✅ No functionality regression
- ✅ Pub/Sub implementation removed

### Phase 4: Future Evaluation (Kafka/RabbitMQ)
**Duration:** 6-12 months
**Trigger:** When any of the following occur:
- Throughput requirements exceed 10,000 events/sec
- Horizontal scaling required
- Advanced replay capabilities critical
- Message ordering guarantees required

**Actions:**
- Re-evaluate Kafka/RabbitMQ
- Consider infrastructure investment
- Plan migration if justified

**Success Criteria:**
- ✅ Requirements justify complexity
- ✅ Infrastructure investment approved
- ✅ Migration plan created

## Risk Assessment

### Risks of Current Decision (Redis Pub/Sub)

**Risk 1: Scalability Limitations**
- **Probability:** Low (current scale sufficient)
- **Impact:** Medium (if scale increases rapidly)
- **Mitigation:** Monitor throughput trends, prepare Streams migration

**Risk 2: Missing Features**
- **Probability:** Medium (consumer groups may be needed)
- **Impact:** Low (Streams migration is low effort)
- **Mitigation:** Clear migration path to Streams

**Risk 3: Performance Bottlenecks**
- **Probability:** Low (current performance adequate)
- **Impact:** Medium (if throughput increases)
- **Mitigation:** Monitor performance, optimize PostgreSQL persistence

### Risks of Alternative Decisions

**Risk 1: Over-Engineering (Kafka/RabbitMQ)**
- **Probability:** High (complexity not justified)
- **Impact:** High (operational burden, resource waste)
- **Mitigation:** Current decision avoids this risk

**Risk 2: Migration Complexity (Kafka/RabbitMQ)**
- **Probability:** High (7-11 days effort)
- **Impact:** Medium (disruption, risk)
- **Mitigation:** Current decision avoids this risk

## Success Metrics

### Current State Metrics (Redis Pub/Sub)

**Performance Metrics:**
- Throughput: ~1,500-2,000 events/sec ✅
- Average Latency: <10ms ✅
- P95 Latency: <20ms ✅
- Error Rate: <1% ✅

**Operational Metrics:**
- Uptime: >99.9% ✅
- Mean Time to Recovery: <5 minutes ✅
- Operational Complexity: Low ✅

### Migration Readiness Metrics (Redis Streams)

**When to Migrate:**
- Throughput approaching 2,000 events/sec
- Consumer groups required
- Better replay capabilities needed
- Message acknowledgment required
- Better observability needed

**Migration Success Criteria:**
- All publishers migrated
- All subscribers migrated
- Performance maintained or improved
- No functionality regression
- Operational complexity acceptable

## Conclusion

**Decision:** Continue with Redis Pub/Sub for current implementation, with clear migration path to Redis Streams when requirements justify.

**Key Rationale:**
1. **Current Requirements Met:** Redis Pub/Sub meets all current performance and feature requirements
2. **Low Complexity:** Simplest solution with lowest operational overhead
3. **Clear Migration Path:** Redis Streams provides clear upgrade path with low migration effort
4. **Future Flexibility:** Can migrate to Kafka/RabbitMQ if requirements significantly increase

**Next Steps:**
1. ✅ Document decision (this document)
2. ✅ Update design.md with Decision: Event Bus Architecture
3. ✅ Create migration plan (included in this document)
4. ⏭️ Monitor performance metrics
5. ⏭️ Prepare Redis Streams implementation when triggers occur

**Decision Date:** 2025-12-30
**Decision Owner:** Architecture Team
**Review Date:** 2025-06-30 (6 months)

