# System Architecture

**Last Updated**: 2026-01-26
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

