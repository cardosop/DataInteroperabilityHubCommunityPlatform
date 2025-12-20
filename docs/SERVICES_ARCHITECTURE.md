# Services Architecture

**Last Updated**: 2025-01-15  
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

1. **API Service** (`api-service`) - Main Django backend
2. **Worker Service** (`worker-service`) - Background job processing
3. **DataContract Service** (`datacontract-service`) - Contract validation and conversion
4. **DQ Service** (`dq-service`) - Data quality checks
5. **Compliance Service** (`compliance-service`) - Compliance scanning
6. **Semantic Service** (`semantic-service`) - RDF mapping and SPARQL

### Supporting Services (Post-MVP)

7. **Prefect Integration Service** (`prefect-integration-service`) - Prefect workflow sync
8. **Search Service** (`search-service`) - Full-text search
9. **Observability Service** (`observability-service`) - Data observability
10. **Webhook Service** (`webhook-service`) - Webhook delivery

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
- `POST /sync` - Sync with Prefect
- `GET /deployments` - List Prefect deployments
- `GET /health` - Health check

**Dependencies**:
- Prefect Server
- PostgreSQL (scheduled ingestions)

**Scaling**: Horizontal scaling

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

**Technology**: HTTP/REST, httpx (Python)

---

### Asynchronous Communication

**Pattern**: Job Queue (Redis/RQ)  
**Use Cases**:
- API Service → Worker Service (background jobs)
- Worker Service → External services (long-running operations)

**Technology**: Redis Queue (RQ), Redis pub/sub (future)

---

### Event-Driven Communication (Future)

**Pattern**: Event bus / Message queue  
**Use Cases**:
- Contract created → Semantic mapping
- Asset updated → Search index update
- Compliance scan completed → Notifications

**Technology**: Kafka, RabbitMQ, or Redis Streams (future)

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

---

## Service Layer Coordination

### Service Layer Pattern

All business logic is coordinated through service layer classes that extend `BaseService`:

#### TransformationService
- **Location**: `hub/apps/transformation/services.py`
- **Responsibilities**:
  - Coordinate pipeline execution with asset lifecycle
  - Manage pipeline-to-asset relationships
  - Handle pipeline result synchronization
  - Validate pipeline compatibility with assets
- **Integration**: Integrates with AssetCreationWorkflow, TransformationPipelineWorkflow

#### AIService
- **Location**: `hub/apps/ai/services.py`
- **Responsibilities**:
  - Coordinate ML operations with workflows
  - Manage ML model lifecycle
  - Handle ML result validation
  - Coordinate schema matching with contract creation
- **Integration**: Integrates with AssetCreationWorkflow, ContractCreationWorkflow

#### SocialService
- **Location**: `hub/apps/social/services.py`
- **Responsibilities**:
  - Coordinate ratings/reviews with asset updates
  - Manage review moderation workflows
  - Handle social feature events
  - Coordinate activity feeds with asset operations
- **Integration**: Integrates with SocialFeatureWorkflow, AssetUpdateWorkflow

#### MarketplaceService (Enhanced)
- **Location**: `hub/apps/marketplace/services.py`
- **Responsibilities**:
  - Coordinate publishing with transformation/quality
  - Manage purchase workflows
  - Handle pricing model validation
  - Coordinate marketplace events with asset updates
- **Integration**: Integrates with MarketplacePublishingWorkflow, TransformationPipelineWorkflow

#### DataMeshService
- **Location**: `hub/apps/mesh/services.py`
- **Responsibilities**:
  - Coordinate domain operations
  - Manage domain-to-asset relationships
  - Handle federated governance
  - Coordinate mesh topology updates
- **Integration**: Integrates with DataMeshWorkflow, AssetUpdateWorkflow

### Service Communication Patterns

Services communicate through:
1. **Direct Service Calls**: For synchronous coordination
2. **Event Bus**: For asynchronous coordination
3. **Workflow Engine**: For multi-step orchestration

### Service Dependencies

```
TransformationService
  ├── AssetService (for asset updates)
  ├── WorkflowEngine (for pipeline orchestration)
  └── EventBus (for event publishing)

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
  ├── TransformationService (for pipeline validation)
  ├── AssetService (for asset updates)
  ├── WorkflowEngine (for publishing orchestration)
  └── EventBus (for event publishing)

DataMeshService
  ├── AssetService (for ownership updates)
  ├── GovernanceService (for policy application)
  ├── WorkflowEngine (for domain orchestration)
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

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

