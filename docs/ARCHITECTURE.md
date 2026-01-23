# System Architecture

**Last Updated**: 2025-01-15
**Version**: 1.0.0

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

```
┌─────────────────────────────────────────────────────────────┐
│                        API Gateway                           │
│                      (Traefik / Django)                      │
└───────────────────────┬─────────────────────────────────────┘
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

Event handlers subscribe to events and trigger workflows or update state.

### Business Rules Framework

Centralized business rules framework (`hub/apps/core/business_rules/`) enforces:

- **AIBusinessRules**: ML result validation, schema alignment
- **MarketplaceBusinessRules**: Publishing validation, pricing validation
- **SocialBusinessRules**: Review moderation, rating validation
- **DataMeshBusinessRules**: Domain ownership, policy compliance

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
- **Load Balancing**: Traefik for API gateway load balancing

## Deployment

- **Development**: Docker Compose (`docker-compose.dev.yml`)
- **Staging**: Docker Compose (`docker-compose.staging.yml`)
- **Production**: Kubernetes (see `KUBERNETES_DEPLOYMENT.md`)

## Related Documentation

- [Services Architecture](SERVICES_ARCHITECTURE.md) - Detailed service documentation
- [Docker Compose Deployment](DOCKER_COMPOSE_DEPLOYMENT.md) - Deployment guide
- [API Standards](API_STANDARDS.md) - API design standards
- [Event Bus Architecture](EVENT_BUS.md) - Event-driven patterns

