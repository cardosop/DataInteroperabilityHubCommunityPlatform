# API Integration Requirements Documentation

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-13  
**Task**: 0.4.6 - Document integration requirements

---

## Overview

This document provides comprehensive documentation of integration requirements for all API endpoints, including service dependencies, database requirements, external service dependencies, and event publishing requirements.

**Coverage**: All 8 missing API endpoints have complete integration requirements documentation in their OpenAPI 3.0 specifications.

---

## Integration Requirements Categories

### 1. Service Dependencies

Internal microservices that the API endpoint depends on for functionality.

### 2. Database Requirements

Database models and operations required by the endpoint.

### 3. External Service Dependencies

Third-party or external services (LLM, connectors, email, etc.) required by the endpoint.

### 4. Event Publishing Requirements

Events that the endpoint publishes for asynchronous coordination.

### 5. Infrastructure Dependencies

Infrastructure components (PostgreSQL, Redis, MinIO, etc.) required by the endpoint.

---

## Internal Service Dependencies

### DataContract Service

**URL**: `http://datacontract-service:8080`  
**Description**: Contract validation and conversion  
**Status**: MVP

**Endpoints**:
- `POST /validate` - Validate contract
- `POST /lint` - Lint contract
- `POST /convert` - Convert contract format

**Used By**: Contract management endpoints

---

### DQ Service

**URL**: `http://dq-service:8083`  
**Description**: Data quality checks using Great Expectations or Soda  
**Status**: MVP

**Endpoints**:
- `POST /run` - Run DQ check
- `GET /profiles` - List DQ profiles

**Used By**: 
- Marketplace preview endpoint (for quality metrics)
- Asset onboarding workflows

---

### Compliance Service

**URL**: `http://compliance-service:8082`  
**Description**: Compliance scanning and PII detection  
**Status**: MVP

**Endpoints**:
- `POST /run` - Run compliance scan
- `GET /regulations` - List supported regulations

**Used By**: Compliance scanning endpoints

---

### Semantic Service

**URL**: `http://semantic-service:8081`  
**Description**: RDF mapping and SPARQL queries  
**Status**: MVP

**Endpoints**:
- `POST /map/contract` - Map contract to RDF
- `POST /map/asset` - Map asset to RDF
- `POST /sparql` - Execute SPARQL query

**Used By**: Semantic mapping endpoints

---

### Search Service

**URL**: `http://search-service:8085`  
**Description**: Full-text search  
**Status**: Post-MVP

**Endpoints**:
- `POST /search` - Execute search
- `POST /suggest` - Get search suggestions

**Used By**: 
- Natural language search endpoint
- General search endpoints

---

### Observability Service

**URL**: `http://observability-service:8086`  
**Description**: Data observability and monitoring  
**Status**: Post-MVP

**Endpoints**:
- `GET /freshness` - Get freshness metrics
- `GET /volume` - Get volume metrics
- `GET /schema-drift` - Get schema drift metrics

**Used By**: Observability endpoints

---

## External Service Dependencies

### LLM Service

**Description**: Large Language Model service for natural language processing  
**Providers**: OpenAI, Anthropic, Self-hosted  
**Timeout**: 30 seconds

**Used By**:
- `POST /api/v1/ai/natural-language-search/` - Natural language query understanding

**Configuration**:
- API key required
- Rate limiting: Per-provider limits
- Cost tracking: Required

---

### AI Service

**Description**: AI service for schema matching and classification  
**Providers**: OpenAI, Anthropic, Self-hosted  
**Timeout**: 15 seconds

**Used By**:
- `POST /api/v1/ai/schema-matching/` - AI-powered schema matching

**Configuration**:
- API key required
- Model selection: Configurable
- Confidence thresholds: Configurable

---

### Connector Services

**Description**: Data source connectors (S3, GCS, Azure Blob, Database, FTP, SFTP, etc.)  
**Timeout**: 5-30 seconds (depending on connector type)

**Used By**:
- `POST /api/v1/scheduled-ingestions/{id}/credentials/test/` - Test connection

**Connector Types**:
- **S3**: AWS S3, MinIO
- **GCS**: Google Cloud Storage
- **Azure Blob**: Azure Blob Storage
- **Database**: PostgreSQL, MySQL, SQL Server, Oracle
- **FTP/SFTP**: File transfer protocols
- **HTTP/HTTPS**: REST API endpoints

**Configuration**:
- Credentials: Encrypted storage
- Connection pooling: Per connector type
- Retry logic: Configurable

---

### Email Service

**Description**: Email delivery service for notifications  
**Providers**: SMTP, SendGrid, AWS SES  
**Timeout**: 5 seconds

**Used By**:
- `POST /api/v1/auth/register/` - Welcome email (optional)

**Configuration**:
- SMTP server: Configurable
- Templates: Email templates for different scenarios
- Rate limiting: Per-tenant limits

---

## Database Requirements

### User Model

**Operations**: `read`, `write`

**Used By**:
- `POST /api/v1/auth/register/` - Create user
- `GET /api/v1/auth/me/` - Read user
- `POST /api/v1/social/communities/` - Read user

**Indexes**:
- `tenant_id`, `email` (unique)
- `tenant_id`, `created_at`

---

### Tenant Model

**Operations**: `read`

**Used By**:
- `POST /api/v1/auth/register/` - Validate tenant
- `GET /api/v1/auth/me/` - Get tenant information

**Indexes**:
- `id` (primary key)
- `name` (unique)

---

### ScheduledIngestion Model

**Operations**: `read`

**Used By**:
- `GET /api/v1/scheduled-ingestions/{id}/credentials/` - Read scheduled ingestion
- `POST /api/v1/scheduled-ingestions/{id}/credentials/test/` - Read scheduled ingestion

**Indexes**:
- `id` (primary key)
- `tenant_id`, `status`
- `tenant_id`, `created_at`

---

### Asset Model

**Operations**: `read`, `write`

**Used By**:
- `POST /api/v1/ai/natural-language-search/` - Search assets
- `POST /api/v1/ai/schema-matching/` - Read asset schema
- `POST /api/v1/social/ratings/` - Read/update asset
- `POST /api/v1/social/reviews/` - Read asset
- `POST /api/v1/social/comments/` - Read asset
- `GET /api/v1/marketplace/listings/{id}/preview/` - Read asset

**Indexes**:
- `id` (primary key)
- `tenant_id`, `status`
- `tenant_id`, `name`
- `tenant_id`, `created_at`

---

### Contract Model

**Operations**: `read`

**Used By**:
- `POST /api/v1/ai/natural-language-search/` - Search contracts
- `POST /api/v1/ai/schema-matching/` - Read contract schema

**Indexes**:
- `id` (primary key)
- `tenant_id`, `asset_id`
- `tenant_id`, `status`

---

### Rating Model

**Operations**: `write`

**Used By**:
- `POST /api/v1/social/ratings/` - Create rating

**Indexes**:
- `id` (primary key)
- `asset_id`, `user_id` (unique)
- `asset_id`, `created_at`

---

### Review Model

**Operations**: `write`

**Used By**:
- `POST /api/v1/social/reviews/` - Create review

**Indexes**:
- `id` (primary key)
- `asset_id`, `created_at`
- `user_id`, `created_at`

---

### Comment Model

**Operations**: `write`

**Used By**:
- `POST /api/v1/social/comments/` - Create comment

**Indexes**:
- `id` (primary key)
- `asset_id`, `created_at`
- `parent_comment_id` (for threading)

---

### Community Model

**Operations**: `write`

**Used By**:
- `POST /api/v1/social/communities/` - Create or join community

**Indexes**:
- `id` (primary key)
- `tenant_id`, `name` (unique)
- `tenant_id`, `created_at`

---

### MarketplaceListing Model

**Operations**: `read`

**Used By**:
- `GET /api/v1/marketplace/listings/{id}/preview/` - Read listing

**Indexes**:
- `id` (primary key)
- `asset_id`
- `status`, `created_at`

---

### Dataset Model

**Operations**: `read`

**Used By**:
- `GET /api/v1/marketplace/listings/{id}/preview/` - Read dataset for preview

**Indexes**:
- `id` (primary key)
- `asset_id`
- `tenant_id`, `created_at`

---

### Plugin Model

**Operations**: `read`

**Used By**:
- `GET /api/v1/developer/plugins/` - List plugins

**Indexes**:
- `id` (primary key)
- `name` (unique)
- `status`, `created_at`

---

### SDKDocumentation Model

**Operations**: `read`

**Used By**:
- `GET /api/v1/developer/sdk/` - Get SDK documentation

**Indexes**:
- `id` (primary key)
- `sdk_name`, `version` (unique)

---

## Event Publishing Requirements

### User Events

#### `user.created`

**Published By**: `POST /api/v1/auth/register/`  
**Event Data**:
```json
{
  "user_id": "uuid",
  "email": "string",
  "tenant_id": "uuid",
  "created_at": "ISO 8601"
}
```

**Subscribers**:
- Email service (welcome email)
- Analytics service (user tracking)
- Audit service (audit logging)

---

### AI/ML Events

#### `ai.schema_matching.completed`

**Published By**: `POST /api/v1/ai/schema-matching/`  
**Event Data**:
```json
{
  "matching_id": "uuid",
  "source_schema_id": "uuid",
  "target_schema_id": "uuid",
  "confidence": "float",
  "mappings": [
    {
      "source_field": "string",
      "target_field": "string",
      "confidence": "float"
    }
  ]
}
```

**Subscribers**:
- Contract service (update contract with mappings)
- Asset service (update asset metadata)
- Analytics service (track matching performance)

---

### Social Feature Events

#### `social.rating.created`

**Published By**: `POST /api/v1/social/ratings/`  
**Event Data**:
```json
{
  "rating_id": "uuid",
  "asset_id": "uuid",
  "user_id": "uuid",
  "rating": "integer (1-5)",
  "created_at": "ISO 8601"
}
```

**Subscribers**:
- Asset service (update asset quality score)
- Analytics service (track rating trends)
- Notification service (notify asset owners)

---

#### `social.review.created`

**Published By**: `POST /api/v1/social/reviews/`  
**Event Data**:
```json
{
  "review_id": "uuid",
  "asset_id": "uuid",
  "user_id": "uuid",
  "review_text": "string",
  "created_at": "ISO 8601"
}
```

**Subscribers**:
- Moderation service (review moderation)
- Asset service (update asset metadata)
- Notification service (notify asset owners)

---

#### `social.comment.created`

**Published By**: `POST /api/v1/social/comments/`  
**Event Data**:
```json
{
  "comment_id": "uuid",
  "asset_id": "uuid",
  "user_id": "uuid",
  "parent_comment_id": "uuid (optional)",
  "comment_text": "string",
  "created_at": "ISO 8601"
}
```

**Subscribers**:
- Moderation service (comment moderation)
- Notification service (notify @mentioned users)
- Activity feed service (update activity feed)

---

#### `social.community.created`

**Published By**: `POST /api/v1/social/communities/`  
**Event Data**:
```json
{
  "community_id": "uuid",
  "name": "string",
  "tenant_id": "uuid",
  "created_by": "uuid",
  "created_at": "ISO 8601"
}
```

**Subscribers**:
- Search service (index community)
- Notification service (notify interested users)

---

#### `social.community.joined`

**Published By**: `POST /api/v1/social/communities/` (when joining existing)  
**Event Data**:
```json
{
  "community_id": "uuid",
  "user_id": "uuid",
  "joined_at": "ISO 8601"
}
```

**Subscribers**:
- Activity feed service (update activity feed)
- Notification service (notify community members)

---

## Infrastructure Dependencies

### PostgreSQL

**Description**: Primary database for all data persistence  
**Required**: Yes (all endpoints)

**Usage**:
- All CRUD operations
- Transaction management
- Data consistency
- Audit logging

**Configuration**:
- Connection pooling: Required
- Read replicas: Optional (for read-heavy endpoints)
- Backup: Required (daily backups)

---

### Redis

**Description**: Job queue, caching, and event bus  
**Required**: Yes (most endpoints)

**Usage**:
- Job queue: Background job processing
- Caching: Response caching (e.g., `/api/v1/auth/me/`)
- Event bus: Redis Pub/Sub for event delivery
- Rate limiting: Rate limit tracking

**Configuration**:
- Memory limits: Per-environment
- Persistence: Optional (AOF or RDB)
- Clustering: Optional (for high availability)

---

### MinIO

**Description**: S3-compatible object storage for files and datasets  
**Required**: Yes (for file/dataset endpoints)

**Usage**:
- File storage: Uploaded files
- Dataset storage: Dataset files
- Preview data: Sample data for previews

**Configuration**:
- Bucket policies: Per-tenant isolation
- Lifecycle policies: Data retention
- Versioning: Optional

---

### Apache Jena Fuseki

**Description**: RDF triple store for semantic data  
**Required**: No (only for semantic endpoints)

**Usage**:
- RDF storage: Semantic mappings
- SPARQL queries: Semantic queries

**Configuration**:
- Dataset configuration: Per-tenant datasets
- Query timeout: Configurable

---

## Integration Requirements by Endpoint

### Authentication Endpoints

#### POST `/api/v1/auth/register/`

**Service Dependencies**: None

**Database Requirements**:
- User model: `write` - Create new user account
- Tenant model: `read` - Validate tenant if provided
- APIKey model: `read` - Check for existing API keys

**External Services**:
- Email service: Send welcome email (optional, timeout: 5s)

**Event Publishing**:
- `user.created` - User registration event (required)

**Infrastructure**:
- PostgreSQL: User and tenant data persistence
- Redis: Job queue for email sending

---

#### GET `/api/v1/auth/me/`

**Service Dependencies**: None

**Database Requirements**:
- User model: `read` - Get current user information
- Tenant model: `read` - Get tenant information

**External Services**: None

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: User and tenant data
- Redis: Response caching (5-minute TTL)

---

### Credential Management Endpoints

#### GET `/api/v1/scheduled-ingestions/{id}/credentials/`

**Service Dependencies**: None

**Database Requirements**:
- ScheduledIngestion model: `read` - Get scheduled ingestion

**External Services**: None

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: Scheduled ingestion data

---

#### POST `/api/v1/scheduled-ingestions/{id}/credentials/test/`

**Service Dependencies**: None

**Database Requirements**:
- ScheduledIngestion model: `read` - Get scheduled ingestion and credentials

**External Services**:
- Connector services: Test connection to data source (timeout: 30s)

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: Scheduled ingestion data

---

### AI/ML Endpoints

#### POST `/api/v1/ai/natural-language-search/`

**Service Dependencies**:
- Search service: Execute search query (timeout: 5s)

**Database Requirements**:
- Asset model: `read` - Search assets
- Contract model: `read` - Search contracts

**External Services**:
- LLM service: Natural language query understanding (timeout: 30s)

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: Asset and contract data
- Redis: Query caching (1-hour TTL)

---

#### POST `/api/v1/ai/schema-matching/`

**Service Dependencies**: None

**Database Requirements**:
- Contract model: `read` - Get target contract schema
- Asset model: `read` - Get source asset schema

**External Services**:
- AI service: AI-powered schema matching (timeout: 15s)

**Event Publishing**:
- `ai.schema_matching.completed` - Schema matching completion event (required)

**Infrastructure**:
- PostgreSQL: Contract and asset data
- Redis: Event bus for event publishing

---

### Social Feature Endpoints

#### POST `/api/v1/social/ratings/`

**Service Dependencies**: None

**Database Requirements**:
- Rating model: `write` - Create rating
- Asset model: `read`, `write` - Update asset quality score

**External Services**: None

**Event Publishing**:
- `social.rating.created` - Rating creation event (required)

**Infrastructure**:
- PostgreSQL: Rating and asset data
- Redis: Event bus for event publishing

---

#### POST `/api/v1/social/reviews/`

**Service Dependencies**: None

**Database Requirements**:
- Review model: `write` - Create review
- Asset model: `read` - Get asset information

**External Services**: None

**Event Publishing**:
- `social.review.created` - Review creation event (required)

**Infrastructure**:
- PostgreSQL: Review and asset data
- Redis: Event bus for event publishing

---

#### POST `/api/v1/social/comments/`

**Service Dependencies**: None

**Database Requirements**:
- Comment model: `write` - Create comment
- Asset model: `read` - Get asset information

**External Services**: None

**Event Publishing**:
- `social.comment.created` - Comment creation event (required)

**Infrastructure**:
- PostgreSQL: Comment and asset data
- Redis: Event bus for event publishing

---

#### POST `/api/v1/social/communities/`

**Service Dependencies**: None

**Database Requirements**:
- Community model: `write` - Create or join community
- User model: `read` - Get user information

**External Services**: None

**Event Publishing**:
- `social.community.created` - Community creation event (required)
- `social.community.joined` - Community join event (required)

**Infrastructure**:
- PostgreSQL: Community and user data
- Redis: Event bus for event publishing

---

### Marketplace Endpoints

#### GET `/api/v1/marketplace/listings/{id}/preview/`

**Service Dependencies**:
- DQ service: Get data quality metrics for preview (optional, timeout: 5s)

**Database Requirements**:
- MarketplaceListing model: `read` - Get marketplace listing
- Asset model: `read` - Get asset information
- Dataset model: `read` - Get dataset for preview

**External Services**: None

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: Listing, asset, and dataset metadata
- MinIO: Dataset file access

---

### Developer Experience Endpoints

#### GET `/api/v1/developer/plugins/`

**Service Dependencies**: None

**Database Requirements**:
- Plugin model: `read` - List available plugins

**External Services**: None

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: Plugin data

---

#### GET `/api/v1/developer/sdk/`

**Service Dependencies**: None

**Database Requirements**:
- SDKDocumentation model: `read` - Get SDK documentation

**External Services**: None

**Event Publishing**: None

**Infrastructure**:
- PostgreSQL: SDK documentation data

---

## Service Communication Patterns

### Synchronous Communication

**Pattern**: Direct HTTP calls to internal services  
**Use Cases**:
- Contract validation (DataContract Service)
- Data quality checks (DQ Service)
- Search queries (Search Service)

**Timeout Handling**:
- Default timeout: 5 seconds
- Long-running operations: 30 seconds (connection testing)
- AI/ML operations: 15-30 seconds

**Retry Strategy**:
- Transient errors: 3 retries with exponential backoff
- Non-transient errors: No retry

---

### Asynchronous Communication

**Pattern**: Event bus (Redis Pub/Sub)  
**Use Cases**:
- User registration events
- Social feature events
- AI/ML completion events

**Event Delivery**:
- Real-time: Redis Pub/Sub
- Persistence: PostgreSQL
- Replay: Event replay functionality

**Error Handling**:
- Dead letter queue: Failed events
- Retry: Configurable retry attempts

---

## Database Transaction Requirements

### Transaction Boundaries

**Single Model Operations**: No explicit transaction needed (Django auto-commit)

**Multi-Model Operations**: Explicit transaction required
- User registration: User + Tenant validation
- Rating creation: Rating + Asset quality score update
- Review creation: Review + Asset metadata update

**Transaction Isolation**:
- Default: READ COMMITTED
- Critical operations: SERIALIZABLE (if needed)

---

## Error Handling for Dependencies

### Service Dependency Failures

**Internal Services**:
- Retry: 3 attempts with exponential backoff
- Fallback: Return cached data if available
- Error Response: 503 Service Unavailable

**External Services**:
- Retry: 2 attempts with exponential backoff
- Fallback: Return error with service unavailable message
- Error Response: 503 Service Unavailable

### Database Failures

**Connection Failures**:
- Retry: 3 attempts
- Error Response: 503 Service Unavailable

**Query Timeouts**:
- Timeout: 30 seconds
- Error Response: 504 Gateway Timeout

### Infrastructure Failures

**Redis Failures**:
- Caching: Graceful degradation (no cache)
- Event Bus: Queue events for later delivery
- Job Queue: Jobs queued in database fallback

**MinIO Failures**:
- File Operations: 503 Service Unavailable
- Preview Operations: Return error with retry suggestion

---

## Performance Considerations

### Service Dependency Timeouts

| Service | Default Timeout | Long Operations |
|---------|----------------|----------------|
| DataContract Service | 5s | 10s |
| DQ Service | 5s | 30s |
| Compliance Service | 5s | 30s |
| Semantic Service | 5s | 10s |
| Search Service | 5s | 10s |
| LLM Service | 30s | 60s |
| AI Service | 15s | 30s |
| Connector Services | 5s | 30s |
| Email Service | 5s | 10s |

### Database Query Optimization

**Indexes**: All foreign keys and frequently queried fields are indexed

**Query Optimization**:
- Use `select_related()` for foreign key relationships
- Use `prefetch_related()` for many-to-many relationships
- Limit query results with pagination

**Connection Pooling**:
- Default pool size: 20 connections
- Max pool size: 50 connections

---

## Security Considerations

### Service Authentication

**Internal Services**:
- Service-to-service authentication: API keys or mTLS
- Tenant isolation: Tenant ID in request headers

**External Services**:
- API keys: Stored in encrypted configuration
- Credentials: Encrypted in database (for connectors)

### Data Isolation

**Tenant Isolation**:
- All database queries filtered by tenant_id
- All service calls include tenant_id
- All events include tenant_id

**User Isolation**:
- User-scoped data filtered by user_id
- Permission checks for user-scoped operations

---

## Monitoring and Observability

### Service Dependency Monitoring

**Metrics**:
- Request count per service
- Response time per service
- Error rate per service
- Timeout rate per service

**Alerts**:
- High error rate (> 5%)
- High timeout rate (> 10%)
- Service unavailable

### Database Monitoring

**Metrics**:
- Query count per model
- Query time per model
- Connection pool usage
- Transaction rollback rate

**Alerts**:
- High query time (> 1s)
- Connection pool exhaustion
- High rollback rate

### Event Publishing Monitoring

**Metrics**:
- Events published per type
- Event delivery latency
- Event failure rate
- Dead letter queue size

**Alerts**:
- High event failure rate (> 1%)
- Dead letter queue size (> 100)
- Event delivery latency (> 5s)

---

## Summary

- **Total Endpoints Documented**: 13 endpoints (across 8 OpenAPI spec files)
- **Service Dependencies**: 6 internal services
- **External Services**: 4 external service types
- **Database Models**: 12 models
- **Event Types**: 7 event types
- **Infrastructure Components**: 4 components

All integration requirements are documented in OpenAPI 3.0 specifications using:
1. **Description Extensions**: Integration requirements in operation descriptions
2. **x-integration-requirements Extension**: Structured integration requirements data
3. **Comprehensive Documentation**: This document provides detailed reference

All specifications are ready for implementation with complete integration requirements.

