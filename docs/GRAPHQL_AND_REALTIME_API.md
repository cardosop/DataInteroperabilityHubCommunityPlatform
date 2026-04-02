# GraphQL & Realtime API

> Consolidated reference for GraphQL, WebSocket, and Webhook APIs.
>
> **Source**: Merged from 4 API docs during Phase 120D documentation consolidation.

---


---

# GraphQL API Documentation

Complete documentation for the GraphQL API implementation using Graphene-Django.

## Table of Contents

1. [Overview](#overview)
2. [GraphQL Need Evaluation](#graphql-need-evaluation)
3. [Schema Design](#schema-design)
4. [Authentication and Authorization](#authentication-and-authorization)
5. [Query Examples](#query-examples)
6. [Error Handling](#error-handling)
7. [Query Complexity Limits](#query-complexity-limits)
8. [Best Practices](#best-practices)

---

## Overview

The GraphQL API provides a flexible, efficient way to query and interact with the Data Interoperability Hub. It is implemented using **Graphene-Django** and provides:

- **Query capabilities**: Read data from assets, contracts, datasets, tenants, users, and jobs
- **Tenant scoping**: Automatic tenant isolation for all queries
- **Filtering and pagination**: Built-in filtering and Relay-style pagination
- **Authentication**: JWT and API key authentication support
- **Query complexity limits**: Protection against overly complex queries

**Endpoint**: `/graphql-graphene/`

**GraphiQL Interface**: Available at `/graphql-graphene/` (when `DEBUG=True`)

---

## GraphQL Need Evaluation

### Why GraphQL?

GraphQL provides several advantages over REST APIs:

1. **Flexible Queries**: Clients request exactly the data they need
2. **Reduced Over-fetching**: No need to fetch entire resources when only specific fields are needed
3. **Single Endpoint**: One endpoint for all queries instead of multiple REST endpoints
4. **Strongly Typed**: Schema provides clear contract and validation
5. **Relationships**: Easy to query related objects in a single request

### Use Cases

- **UI Aggregation**: Frontend applications can fetch all needed data in one request
- **Mobile Applications**: Reduced payload size by requesting only required fields
- **Third-party Integrations**: Flexible API for external systems with varying data needs
- **Real-time Dashboards**: Efficient queries for dashboard data aggregation

### When to Use GraphQL vs REST

- **Use GraphQL for**:
  - UI components that need flexible data fetching
  - Mobile apps with bandwidth constraints
  - Complex queries with multiple related objects
  - Real-time dashboards and analytics

- **Use REST for**:
  - Simple CRUD operations
  - File uploads/downloads
  - Operations that don't fit GraphQL patterns
  - Legacy integrations requiring REST

---

## Schema Design

### Core Types

#### TenantType
```graphql
type Tenant {
  id: ID!
  name: String!
  slug: String!
  status: TenantStatusEnum!
  kycStatus: KYCStatusEnum!
  region: String
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

#### UserType
```graphql
type User {
  id: ID!
  email: String!
  displayName: String
  tenant: TenantType!
  roles: [String!]!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

#### AssetType
```graphql
type Asset {
  id: ID!
  key: String!
  name: String!
  description: String
  domain: String
  status: AssetStatusEnum!
  visibility: AssetVisibilityEnum!
  dqStatus: DQStatusEnum!
  complianceStatus: ComplianceStatusEnum!
  version: Int!
  tenant: TenantType!
  createdBy: UserType
  contracts: [ContractType!]!
  datasets: [DatasetType!]!
  healthScore: Float
  popularityScore: Float
  viewCount: Int!
  downloadCount: Int!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

#### ContractType
```graphql
type Contract {
  id: ID!
  tenant: TenantType!
  asset: AssetType
  version: Int!
  status: ContractStatusEnum!
  originalSpecType: String!
  originalSpecVersion: String!
  originalFormat: String!
  hubContractVersion: String
  hubContractJson: JSON
  normalizationStatus: String
  validationStatus: String
  createdBy: UserType
  createdAt: DateTime!
  updatedAt: DateTime!

  # ODPS-specific fields (only available for ODPS contracts)
  odpsVersion: String                    # ODPS version (e.g., "4.1")
  odcsLink: String                       # Linked ODCS contract ID (for ODPS contracts)
  odpsLink: String                       # Linked ODPS contract ID (for ODCS contracts)
  pricingPlans: [PricingPlan!]           # Pricing plans (for ODPS contracts)
  accessMethods: [AccessMethod!]         # Access methods (for ODPS contracts)
  paymentGateways: [PaymentGateway!]     # Payment gateways (for ODPS contracts)
  productStrategy: ProductStrategy       # Product strategy (for ODPS contracts)
  productDetails(lang: String = "en"): ProductDetails  # Product details for specific language
}

# ODPS-specific types
type PricingPlan {
  planId: String
  name: String
  description: String
  price: Float
  currency: String
  billingPeriod: String
  billingUnit: String
  isDefault: Boolean
  features: [String!]
}

type AccessMethod {
  methodId: String
  type: String
  name: String
  description: String
  endpoint: String
  url: String
  authenticationType: String
  authenticationConfig: JSON
  rateLimit: JSON
  format: String
  maxSize: String
  version: String
}

type PaymentGateway {
  gatewayId: String
  name: String
  type: String
  enabled: Boolean
  config: JSON
  webhookUrl: String
}

type ProductStrategy {
  objectives: JSON
  strategicAlignment: JSON
  productKpis: JSON
  targetAudience: JSON
  valueProposition: JSON
}

type ProductDetails {
  productId: String
  name: String
  description: String
  productVersion: String
  category: String
  tags: [String!]
}
```

#### DatasetType
```graphql
type Dataset {
  id: ID!
  tenant: TenantType!
  asset: AssetType
  file: FileType!
  schemaJson: JSON
  sampleDataJson: JSON
  rowCount: BigInt
  format: String!
  version: Int!
  parentVersion: DatasetType
  versionHash: String
  isCurrent: Boolean!
  semanticVersion: String
  versionTags: [String!]!
  createdBy: UserType
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

#### JobType
```graphql
type Job {
  id: ID!
  tenant: TenantType
  type: JobTypeEnum!
  status: JobStatusEnum!
  resourceType: String!
  resourceId: ID!
  createdBy: UserType
  startedAt: DateTime
  completedAt: DateTime
  errorMessage: String
  resultJson: JSON
  detailsJson: JSON
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

### Enums

- **AssetStatusEnum**: `DRAFT`, `ACTIVE`, `PUBLIC`, `RETIRED`
- **AssetVisibilityEnum**: `INTERNAL`, `PUBLIC`
- **DQStatusEnum**: `UNKNOWN`, `PASS`, `WARN`, `FAIL`
- **ComplianceStatusEnum**: `UNKNOWN`, `PASS`, `WARN`, `FAIL`
- **ContractStatusEnum**: `DRAFT`, `ACTIVE`, `RETIRED`
- **TenantStatusEnum**: `ACTIVE`, `SUSPENDED`, `DELETED`
- **KYCStatusEnum**: `UNVERIFIED`, `VERIFIED`
- **JobTypeEnum**: `DQ_RUN`, `COMPLIANCE_RUN`, `CONTRACT_VALIDATION`, `SEMANTIC_MAPPING`, etc.
- **JobStatusEnum**: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`

---

## Authentication and Authorization

### Authentication Methods

The GraphQL API supports the same authentication methods as the REST API:

1. **JWT Bearer Token**: `Authorization: Bearer <token>`
2. **API Key**: `Authorization: ApiKey <key>`

### Authorization

- **Tenant Scoping**: All queries are automatically scoped to the authenticated user's tenant
- **User Isolation**: Users can only see resources from their own tenant
- **Role-based Access**: User roles are available in the `me` query

### Example: Authenticated Request

```bash
curl -X POST http://localhost:8000/graphql-graphene/ \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ me { id email displayName } }"
  }'
```

---

## Query Examples

### Current User

```graphql
query {
  me {
    id
    email
    displayName
    tenant {
      id
      name
      slug
    }
    roles
  }
}
```

### List Assets

```graphql
query {
  assets {
    edges {
      node {
        id
        name
        key
        status
        dqStatus
        complianceStatus
      }
    }
  }
}
```

### Filter Assets by Status

```graphql
query {
  assets(status: ACTIVE) {
    edges {
      node {
        id
        name
        status
      }
    }
  }
}
```

### Search Assets

```graphql
query {
  assets(search: "customer") {
    edges {
      node {
        id
        name
        description
      }
    }
  }
}
```

### Get Asset with Related Objects

```graphql
query {
  asset(id: "asset-uuid") {
    id
    name
    contracts {
      id
      status
      hubContractJson
    }
    datasets {
      id
      format
      rowCount
    }
  }
}
```

### List Contracts

```graphql
query {
  contracts(status: ACTIVE) {
    edges {
      node {
        id
        status
        asset {
          id
          name
        }
        hubContractVersion
      }
    }
  }
}
```

### List ODPS Contracts

```graphql
query {
  odpsContracts {
    edges {
      node {
        id
        odpsVersion
        status
        asset {
          id
          name
        }
        odcsLink
        pricingPlans {
          planId
          name
          price
          currency
        }
      }
    }
  }
}
```

### Filter ODPS Contracts by Version

```graphql
query {
  odpsContracts(filter: { version: "4.1" }) {
    edges {
      node {
        id
        odpsVersion
        status
      }
    }
  }
}
```

### Filter ODPS Contracts with Linked ODCS

```graphql
query {
  odpsContracts(filter: { hasOdcsLink: true }) {
    edges {
      node {
        id
        odpsVersion
        odcsLink
        asset {
          id
          name
        }
      }
    }
  }
}
```

### Get Linked Contracts (ODPS-ODCS Relationships)

```graphql
query {
  linkedContracts(contractId: "contract-uuid") {
    edges {
      node {
        id
        originalSpecType
        originalSpecVersion
        status
        odpsLink
        odcsLink
      }
    }
  }
}
```

### Get ODPS Contract with Full Details

```graphql
query {
  contract(id: "odps-contract-uuid") {
    id
    odpsVersion
    status
    asset {
      id
      name
    }
    pricingPlans {
      planId
      name
      description
      price
      currency
      billingPeriod
      isDefault
      features
    }
    accessMethods {
      methodId
      type
      name
      endpoint
      authenticationType
      format
    }
    paymentGateways {
      gatewayId
      name
      type
      enabled
    }
    productStrategy {
      objectives
      strategicAlignment
      productKpis
    }
    productDetails(lang: "en") {
      productId
      name
      description
      category
      tags
    }
  }
}
```

### List Jobs

```graphql
query {
  jobs(type: DQ_RUN, status: COMPLETED) {
    edges {
      node {
        id
        type
        status
        resourceType
        resourceId
        completedAt
      }
    }
  }
}
```

### Pagination (Relay-style)

```graphql
query {
  assets(first: 10, after: "cursor") {
    edges {
      node {
        id
        name
      }
      cursor
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
  }
}
```

---

## Mutation Examples

### Create ODPS Contract

```graphql
mutation {
  createODPS(input: {
    originalRaw: """
    {
      "product": {
        "productID": "product-123",
        "name": "Sample Product",
        "version": "1.0.0"
      }
    }
    """
    originalFormat: "JSON"
    assetId: "asset-uuid"
    extractOdcs: false
    resolveExternalRefs: true
  }) {
    contract {
      id
      odpsVersion
      status
      normalizationStatus
    }
    errors
  }
}
```

### Create ODPS Contract with ODCS Extraction (Product-First Flow)

```graphql
mutation {
  createODPS(input: {
    originalRaw: """
    {
      "product": {
        "productID": "product-123",
        "name": "Sample Product",
        "contract": {
          "contractID": "contract-123",
          "name": "Sample Contract"
        }
      }
    }
    """
    originalFormat: "JSON"
    extractOdcs: true
    resolveExternalRefs: true
  }) {
    contract {
      id
      odpsVersion
      status
    }
    errors
  }
}
```

### Link ODPS to ODCS Contract

```graphql
mutation {
  linkODPS(
    odcsId: "odcs-contract-uuid"
    odpsId: "odps-contract-uuid"
    resolveExternalRefs: true
  ) {
    odpsContract {
      id
      odpsVersion
      odcsLink
    }
    odcsContract {
      id
      odpsLink
    }
    errors
  }
}
```

### Link ODPS to ODCS (Create New ODPS)

```graphql
mutation {
  linkODPS(
    odcsId: "odcs-contract-uuid"
    odpsRaw: """
    {
      "product": {
        "productID": "product-123",
        "name": "New Product"
      }
    }
    """
    odpsFormat: "JSON"
    resolveExternalRefs: true
  ) {
    odpsContract {
      id
      odpsVersion
      odcsLink
    }
    odcsContract {
      id
      odpsLink
    }
    errors
  }
}
```

### Unlink ODPS from ODCS Contract

```graphql
mutation {
  unlinkODPS(odcsId: "odcs-contract-uuid") {
    success
    errors
  }
}
```

### Export ODPS Contract

```graphql
mutation {
  exportODPS(
    contractId: "odps-contract-uuid"
    options: {
      version: "4.1"
      format: "json"
    }
  ) {
    content
    format
    errors
  }
}
```

### Export ODPS Contract as YAML

```graphql
mutation {
  exportODPS(
    contractId: "odps-contract-uuid"
    options: {
      version: "4.1"
      format: "yaml"
    }
  ) {
    content
    format
    errors
  }
}
```

---

## Error Handling

### Error Format

GraphQL errors follow the standard GraphQL error format:

```json
{
  "errors": [
    {
      "message": "Authentication required",
      "extensions": {
        "code": "AUTHENTICATION_ERROR",
        "request_id": "request-uuid"
      },
      "path": ["me"]
    }
  ]
}
```

### Common Error Codes

- `AUTHENTICATION_ERROR`: User is not authenticated
- `TENANT_SCOPE_ERROR`: Tenant context required
- `QUERY_COMPLEXITY_EXCEEDED`: Query complexity exceeds limit
- `GRAPHQL_ERROR`: General GraphQL execution error

### Error Handling in Clients

```javascript
const response = await fetch('/graphql-graphene/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ query })
});

const data = await response.json();

if (data.errors) {
  data.errors.forEach(error => {
    console.error(`Error: ${error.message}`, error.extensions);
  });
}
```

---

## Query Complexity Limits

### Complexity Calculation

The GraphQL API enforces query complexity limits to prevent:

- **Resource exhaustion**: Overly complex queries that consume too many resources
- **DoS attacks**: Malicious queries designed to overload the server
- **Performance degradation**: Queries that impact other users

### Default Limit

**Default complexity limit**: 1000

Can be configured via `GRAPHQL_QUERY_COMPLEXITY_LIMIT` setting.

### Complexity Factors

- **Base cost**: 1 per field
- **Nested fields**: Multiplier based on depth
- **List fields**: Additional cost (10x multiplier)

### Example: Complex Query

```graphql
query {
  assets {
    edges {
      node {
        id
        name
        contracts {        # Nested: +depth cost
          id
          status
          asset {          # Deeply nested: +depth cost
            id
            name
          }
        }
        datasets {         # List field: +10 cost
          id
          format
        }
      }
    }
  }
}
```

### Handling Complexity Errors

If a query exceeds the complexity limit, the API returns:

```json
{
  "errors": [
    {
      "message": "Query complexity (1200) exceeds limit (1000)",
      "extensions": {
        "code": "QUERY_COMPLEXITY_EXCEEDED",
        "complexity": 1200,
        "limit": 1000
      }
    }
  ]
}
```

**Solution**: Simplify the query by:
- Reducing nesting depth
- Requesting fewer fields
- Using pagination for large lists
- Splitting into multiple queries

---

## Best Practices

### 1. Request Only Needed Fields

**Bad**:
```graphql
query {
  assets {
    edges {
      node {
        id
        name
        description
        domain
        status
        visibility
        dqStatus
        complianceStatus
        version
        healthScore
        popularityScore
        viewCount
        downloadCount
        createdAt
        updatedAt
        # ... but only need name and status
      }
    }
  }
}
```

**Good**:
```graphql
query {
  assets {
    edges {
      node {
        id
        name
        status
      }
    }
  }
}
```

### 2. Use Pagination for Large Lists

**Bad**:
```graphql
query {
  assets {
    edges {
      node {
        id
        name
      }
    }
  }
}
```

**Good**:
```graphql
query {
  assets(first: 20) {
    edges {
      node {
        id
        name
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

### 3. Leverage Filtering

**Bad**:
```graphql
query {
  assets {
    edges {
      node {
        id
        name
        status
      }
    }
  }
}
# Then filter in client
```

**Good**:
```graphql
query {
  assets(status: ACTIVE) {
    edges {
      node {
        id
        name
        status
      }
    }
  }
}
```

### 4. Batch Related Queries

**Bad**:
```graphql
# Multiple separate queries
query { asset(id: "1") { name } }
query { asset(id: "2") { name } }
query { asset(id: "3") { name } }
```

**Good**:
```graphql
query {
  asset1: asset(id: "1") { name }
  asset2: asset(id: "2") { name }
  asset3: asset(id: "3") { name }
}
```

### 5. Handle Errors Gracefully

```javascript
try {
  const response = await graphqlQuery(query);
  if (response.errors) {
    // Handle GraphQL errors
    response.errors.forEach(error => {
      if (error.extensions.code === 'AUTHENTICATION_ERROR') {
        // Redirect to login
      } else if (error.extensions.code === 'QUERY_COMPLEXITY_EXCEEDED') {
        // Simplify query
      }
    });
  }
  return response.data;
} catch (error) {
  // Handle network errors
  console.error('Network error:', error);
}
```

---

## Implementation Details

### File Structure

```
hub/apps/graphql_graphene/
├── __init__.py
├── apps.py
├── schema.py          # GraphQL schema definition
├── views.py           # GraphQL view with complexity checking
├── urls.py            # URL configuration
└── tests/
    ├── __init__.py
    └── test_graphql_queries.py  # Comprehensive test suite
```

### Key Components

1. **Schema** (`schema.py`): Defines all GraphQL types, queries, and enums
2. **View** (`views.py`): Handles request processing, complexity checking, and error handling
3. **URLs** (`urls.py`): Maps `/graphql-graphene/` to the GraphQL view

### Configuration

**Settings** (`hub/settings.py`):
```python
INSTALLED_APPS = [
    # ...
    "graphene_django",
    "hub.apps.graphql_graphene",
    # ...
]

GRAPHQL_QUERY_COMPLEXITY_LIMIT = 1000
```

**URLs** (`hub/urls.py`):
```python
urlpatterns = [
    # ...
    path('graphql-graphene/', include('hub.apps.graphql_graphene.urls')),
    # ...
]
```

---

## Testing

### Running Tests

```bash
# Run all GraphQL tests
pytest hub/apps/graphql_graphene/tests/ -v

# Run specific test
pytest hub/apps/graphql_graphene/tests/test_graphql_queries.py::GraphQLQueryTest::test_me_query -v
```

### Test Coverage

The test suite covers:
- ✅ Authentication and authorization
- ✅ Tenant scoping and isolation
- ✅ All query types (me, assets, contracts, datasets, jobs, tenants, users)
- ✅ Filtering and search
- ✅ Related object queries
- ✅ Error handling
- ✅ Query complexity limits

**Target Coverage**: 100%

---

## Comparison with REST API

| Feature | REST API | GraphQL API |
|---------|----------|-------------|
| **Endpoint** | Multiple endpoints (`/api/v1/assets/`, etc.) | Single endpoint (`/graphql-graphene/`) |
| **Data Fetching** | Fixed response structure | Flexible field selection |
| **Over-fetching** | Common (fetch entire resource) | Avoided (request only needed fields) |
| **Under-fetching** | Common (multiple requests needed) | Avoided (single query for related data) |
| **Caching** | HTTP caching (GET requests) | More complex (query-based) |
| **File Uploads** | Native support | Not supported (use REST) |
| **Mutations** | Native support | ✅ ODPS mutations implemented (createODPS, linkODPS, unlinkODPS, exportODPS) |

---

---

## ODPS-Specific Features

The GraphQL API includes comprehensive support for ODPS (Open Data Product Specification) contracts:

### ODPS Queries

- **`odpsContracts`**: Query ODPS contracts with filtering by version and link status
- **`linkedContracts`**: Get contracts linked to a specific contract (ODPS-ODCS relationships)

### ODPS Mutations

- **`createODPS`**: Create a new ODPS contract from JSON or YAML
- **`linkODPS`**: Link an ODPS contract to an ODCS contract
- **`unlinkODPS`**: Unlink an ODPS contract from an ODCS contract
- **`exportODPS`**: Export an ODPS contract in JSON or YAML format

### ODPS Contract Fields

ODPS contracts include additional fields accessible via GraphQL:

- **`odpsVersion`**: The ODPS specification version (e.g., "4.1")
- **`odcsLink`**: Linked ODCS contract ID (for ODPS contracts)
- **`odpsLink`**: Linked ODPS contract ID (for ODCS contracts)
- **`pricingPlans`**: List of pricing plans with details
- **`accessMethods`**: List of access methods (APIs, downloads, etc.)
- **`paymentGateways`**: List of payment gateways
- **`productStrategy`**: Product strategy information
- **`productDetails(lang)`**: Product details for a specific language

### ODPS Filter Options

The `odpsContracts` query supports filtering via `ODPSFilter`:

- **`version`**: Filter by ODPS version (e.g., "4.1", "4.0")
- **`hasOdcsLink`**: Filter ODPS contracts that have linked ODCS contracts
- **`hasNoOdcsLink`**: Filter ODPS contracts that do not have linked ODCS contracts

---

**Last Updated**: 2026-03-22
**Maintainer**: Engineering Team
**Status**: ✅ Complete (with ODPS support)

---

# WebSocket API Documentation

## Overview

The WebSocket API provides real-time event updates for the Data Interoperability Hub. It enables clients to subscribe to event streams and receive real-time notifications for jobs, workflows, assets, contracts, datasets, and other system events.

## Features

- **Real-time Event Delivery**: Receive events as they occur in the system
- **Selective Subscription**: Subscribe to specific event types or patterns
- **Authentication**: JWT token or API key authentication
- **Tenant Isolation**: Automatic tenant scoping for all events
- **Filtering**: Filter events by tenant, resource type, and other criteria

## Connection

### Endpoint

```
ws://api.example.com/ws/events/
```

### Authentication

WebSocket connections support two authentication methods:

#### JWT Token Authentication

```
ws://api.example.com/ws/events/?token=<jwt_token>
```

or

```
ws://api.example.com/ws/events/?access_token=<jwt_token>
```

#### API Key Authentication

```
ws://api.example.com/ws/events/?api_key=<api_key>
```

or

```
ws://api.example.com/ws/events/?X-API-Key=<api_key>
```

### Connection Flow

1. Client initiates WebSocket connection with authentication
2. Server validates authentication and tenant membership
3. Server accepts connection and sends confirmation
4. Client subscribes to event types
5. Server sends events as they occur

## Message Protocol

### Message Format

All messages follow a standard JSON format:

```json
{
  "type": "message_type",
  "data": {},
  "error": "error_message",
  "request_id": "uuid",
  "timestamp": "2025-01-15T10:00:00Z"
}
```

### Message Types

#### Client to Server

- `subscribe`: Subscribe to event types
- `unsubscribe`: Unsubscribe from event types
- `ping`: Keep-alive ping

#### Server to Client

- `event`: Event notification
- `subscription_confirmed`: Subscription confirmation
- `subscription_error`: Subscription error
- `error`: Error message
- `pong`: Ping response

## Subscribing to Events

### Subscribe Message

```json
{
  "type": "subscribe",
  "data": {
    "event_types": [
      "contract.created",
      "asset.activated",
      "job.completed"
    ],
    "filters": {
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

### Subscribe Response

```json
{
  "type": "subscription_confirmed",
  "data": {
    "event_types": [
      "contract.created",
      "asset.activated",
      "job.completed"
    ],
    "filters": {
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

## Event Messages

### Event Format

```json
{
  "type": "event",
  "data": {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_type": "contract.created",
    "event_version": "1.0.0",
    "timestamp": "2025-01-15T10:00:00Z",
    "source": {
      "service": "hub",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "request_id": "req-1234567890"
    },
    "data": {
      "contract_id": "550e8400-e29b-41d4-a716-446655440002"
    },
    "metadata": {
      "correlation_id": "corr-1234567890",
      "tags": ["contract", "creation"]
    }
  }
}
```

## Available Event Types

### Contract Events

- `contract.created`
- `contract.updated`
- `contract.deleted`
- `contract.validated`
- `contract.normalized`

### Asset Events

- `asset.created`
- `asset.updated`
- `asset.activated`
- `asset.published`
- `asset.retired`

### Dataset Events

- `dataset.created`
- `dataset.updated`
- `dataset.deleted`
- `dataset.uploaded`

### Job Events

- `job.started`
- `job.completed`
- `job.failed`
- `job.cancelled`

### Workflow Events

- `workflow.started`
- `workflow.completed`
- `workflow.failed`
- `workflow.cancelled`
- `workflow.step.completed`
- `workflow.step.failed`

### Quality Events

- `quality.check.started`
- `quality.check.completed`
- `quality.check.failed`
- `quality.anomaly.detected`

### Compliance Events

- `compliance.check.started`
- `compliance.check.completed`
- `compliance.check.failed`
- `compliance.report.generated`

### ODPS Events

#### Lifecycle Events
- `odps.created` - ODPS contract created
- `odps.updated` - ODPS contract updated
- `odps.deleted` - ODPS contract deleted
- `odps.normalized` - ODPS contract normalized
- `odps.linked` - ODPS contract linked to ODCS
- `odps.unlinked` - ODPS contract unlinked from ODCS

#### Processing Events
- `odps.ref.resolved` - ODPS $ref resolution completed
- `odps.ref.failed` - ODPS $ref resolution failed
- `odps.export.started` - ODPS export started
- `odps.export.completed` - ODPS export completed
- `odps.export.failed` - ODPS export failed

#### Workflow Events
- `odps.workflow.started` - ODPS workflow started
- `odps.workflow.completed` - ODPS workflow completed
- `odps.workflow.failed` - ODPS workflow failed
- `odps.workflow.step.completed` - ODPS workflow step completed
- `odps.workflow.step.failed` - ODPS workflow step failed

#### Progress Events
- `odps.creation.progress` - ODPS creation progress update
- `odps.normalization.progress` - ODPS normalization progress update
- `odps.ref.progress` - ODPS $ref resolution progress update
- `odps.export.progress` - ODPS export progress update
- `odps.workflow.progress` - ODPS workflow progress update

## Error Handling

### Error Message Format

```json
{
  "type": "error",
  "error": "Error message",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Common Errors

- **4001**: Unauthorized - Invalid or missing authentication
- **4003**: Forbidden - User does not belong to a tenant
- **4000**: Bad Request - Invalid message format

## Usage Examples

### JavaScript Example

```javascript
const ws = new WebSocket('ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  // Subscribe to events
  ws.send(JSON.stringify({
    type: 'subscribe',
    data: {
      event_types: ['contract.created', 'asset.activated']
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'event') {
    console.log('Received event:', message.data);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

### JavaScript Example - ODPS Events

```javascript
const ws = new WebSocket('ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  // Subscribe to ODPS events
  ws.send(JSON.stringify({
    type: 'subscribe',
    data: {
      event_types: [
        'odps.created',
        'odps.normalized',
        'odps.export.completed',
        'odps.creation.progress',
        'odps.normalization.progress',
        'odps.export.progress'
      ]
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'event') {
    const eventData = message.data;
    const eventType = eventData.event_type;

    switch (eventType) {
      case 'odps.created':
        console.log('ODPS contract created:', eventData.data.contract_id);
        break;

      case 'odps.normalized':
        console.log('ODPS contract normalized:', {
          contract_id: eventData.data.contract_id,
          status: eventData.data.normalization_status
        });
        break;

      case 'odps.export.completed':
        console.log('ODPS export completed:', {
          contract_id: eventData.data.contract_id,
          format: eventData.data.export_format,
          size: eventData.data.export_size
        });
        break;

      case 'odps.creation.progress':
        console.log('ODPS creation progress:', {
          contract_id: eventData.data.contract_id,
          progress: eventData.data.progress_percent + '%',
          step: eventData.data.current_step
        });
        updateProgressBar(eventData.data.progress_percent);
        break;

      case 'odps.normalization.progress':
        console.log('ODPS normalization progress:', {
          contract_id: eventData.data.contract_id,
          progress: eventData.data.progress_percent + '%'
        });
        updateNormalizationProgress(eventData.data.progress_percent);
        break;

      case 'odps.export.progress':
        console.log('ODPS export progress:', {
          contract_id: eventData.data.contract_id,
          progress: eventData.data.progress_percent + '%'
        });
        updateExportProgress(eventData.data.progress_percent);
        break;

      default:
        console.log('Received ODPS event:', eventType);
    }
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

### Python Example

```python
import asyncio
import websockets
import json

async def connect_websocket():
    uri = "ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN"

    async with websockets.connect(uri) as websocket:
        # Subscribe to events
        subscribe_message = {
            "type": "subscribe",
            "data": {
                "event_types": ["contract.created", "asset.activated"]
            }
        }
        await websocket.send(json.dumps(subscribe_message))

        # Listen for events
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "event":
                print(f"Received event: {data['data']}")

asyncio.run(connect_websocket())
```

### Python Example - ODPS Events

```python
import asyncio
import websockets
import json

async def handle_odps_event(event_data):
    """Handle ODPS events."""
    event_type = event_data.get("event_type")
    data = event_data.get("data", {})

    if event_type == "odps.created":
        print(f"ODPS contract created: {data.get('contract_id')}")

    elif event_type == "odps.normalized":
        print(f"ODPS contract normalized: {data.get('contract_id')} - {data.get('normalization_status')}")

    elif event_type == "odps.export.completed":
        print(f"ODPS export completed: {data.get('contract_id')} - {data.get('export_format')}")

    elif event_type == "odps.creation.progress":
        progress = data.get("progress_percent", 0)
        step = data.get("current_step", "unknown")
        print(f"ODPS creation progress: {progress}% - {step}")

    elif event_type == "odps.normalization.progress":
        progress = data.get("progress_percent", 0)
        print(f"ODPS normalization progress: {progress}%")

    elif event_type == "odps.export.progress":
        progress = data.get("progress_percent", 0)
        print(f"ODPS export progress: {progress}%")

async def connect_odps_websocket():
    """Connect to WebSocket and subscribe to ODPS events."""
    uri = "ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN"

    async with websockets.connect(uri) as websocket:
        # Subscribe to ODPS events
        subscribe_message = {
            "type": "subscribe",
            "data": {
                "event_types": [
                    "odps.created",
                    "odps.normalized",
                    "odps.export.completed",
                    "odps.creation.progress",
                    "odps.normalization.progress",
                    "odps.export.progress",
                    "odps.ref.progress"
                ]
            }
        }
        await websocket.send(json.dumps(subscribe_message))

        # Listen for events
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "event":
                handle_odps_event(data["data"])

asyncio.run(connect_odps_websocket())
```

### Real-Time ODPS Workflow Progress Example

```javascript
// Subscribe to ODPS workflow progress events
const ws = new WebSocket('ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    data: {
      event_types: [
        'odps.workflow.started',
        'odps.workflow.progress',
        'odps.workflow.completed',
        'odps.workflow.failed',
        'odps.creation.progress',
        'odps.normalization.progress',
        'odps.ref.progress'
      ],
      filters: {
        contract_id: '550e8400-e29b-41d4-a716-446655440000'  // Filter by specific contract
      }
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'event') {
    const eventData = message.data;
    const eventType = eventData.event_type;
    const data = eventData.data;

    // Update UI based on event type
    switch (eventType) {
      case 'odps.workflow.started':
        showWorkflowStatus('ODPS workflow started');
        break;

      case 'odps.creation.progress':
        updateProgressBar('Creation', data.progress_percent);
        updateStatusText(data.current_step);
        break;

      case 'odps.normalization.progress':
        updateProgressBar('Normalization', data.progress_percent);
        break;

      case 'odps.ref.progress':
        updateProgressBar('Reference Resolution', data.progress_percent);
        updateRefCount(data.resolved_refs_count, data.total_refs_count);
        break;

      case 'odps.workflow.completed':
        showWorkflowStatus('ODPS workflow completed successfully');
        hideProgressBars();
        break;

      case 'odps.workflow.failed':
        showWorkflowStatus(`ODPS workflow failed: ${data.error_message}`);
        hideProgressBars();
        break;
    }
  }
};
```

## Best Practices

1. **Reconnection**: Implement automatic reconnection with exponential backoff
2. **Heartbeat**: Send ping messages periodically to keep connection alive
3. **Error Handling**: Handle all error types and implement appropriate recovery
4. **Subscription Management**: Unsubscribe from unused event types to reduce load
5. **Rate Limiting**: Be mindful of message rate limits

## Security

- All connections require authentication
- Events are automatically filtered by tenant
- Connections are validated against allowed hosts
- Messages are validated for format and content

## Limitations

- Maximum message size: 1MB
- Maximum concurrent connections per user: 10
- Message buffer capacity: 1000 messages
- Message expiry: 10 seconds

## Troubleshooting

### Connection Refused

- Verify authentication token is valid
- Check user belongs to a tenant
- Ensure WebSocket endpoint is accessible

### No Events Received

- Verify subscription message was sent correctly
- Check event types are valid
- Ensure filters match your tenant

### Connection Drops

- Implement reconnection logic
- Check network stability
- Verify server is not overloaded


---

# WebSocket Reconnection Logic Documentation

## Overview

This document describes the WebSocket reconnection logic for both client-side and server-side implementations. The system provides robust connection management with automatic reconnection, health checks, and connection cleanup.

## Server-Side Implementation

### Ping/Pong Heartbeat Mechanism

The server implements a periodic ping/pong heartbeat mechanism to keep connections alive and detect stale connections.

**Features:**
- **Periodic Server Pings**: Server sends ping messages at configurable intervals (default: 30 seconds)
- **Pong Response Tracking**: Server tracks pong responses to detect unresponsive clients
- **Automatic Cleanup**: Connections that don't respond to pings are automatically closed

**Configuration:**
```python
# settings.py
WEBSOCKET_PING_INTERVAL = 30  # seconds between pings
WEBSOCKET_PONG_TIMEOUT = 10   # seconds to wait for pong response
WEBSOCKET_CONNECTION_TIMEOUT = 300  # seconds of inactivity before timeout
```

**How It Works:**
1. When a WebSocket connection is established, the server starts two background tasks:
   - `_ping_loop()`: Sends periodic ping messages
   - `_health_check_loop()`: Monitors connection health

2. The server sends ping messages at the configured interval
3. Clients should respond with pong messages
4. If no pong is received within `WEBSOCKET_PONG_TIMEOUT`, the connection is closed
5. If no activity occurs within `WEBSOCKET_CONNECTION_TIMEOUT`, the connection is closed

### Connection Timeout Detection

The server tracks connection activity and automatically closes stale connections:

- **Last Activity Tracking**: Every message sent or received updates the `last_activity` timestamp
- **Inactivity Timeout**: Connections inactive for more than `WEBSOCKET_CONNECTION_TIMEOUT` are closed
- **Pong Timeout**: Connections that don't respond to pings within `WEBSOCKET_PONG_TIMEOUT` are closed

### Automatic Connection Cleanup

The server automatically cleans up connections in the following scenarios:

1. **Pong Timeout**: Client doesn't respond to ping within timeout period
2. **Inactivity Timeout**: No activity for configured timeout period
3. **Connection Errors**: Errors during ping/health check operations

When a connection is closed due to timeout, the server sends a close code `4000` (Normal Closure).

## Client-Side Reconnection Logic

### Exponential Backoff for Reconnection Attempts

The client implements exponential backoff to prevent overwhelming the server during reconnection attempts.

**Algorithm:**
```typescript
// Base delay: 1 second
// Max delay: 30 seconds
// Backoff multiplier: 2

delay = min(baseDelay * (2 ^ attemptNumber), maxDelay)
```

**Example:**
- Attempt 1: 1 second delay
- Attempt 2: 2 seconds delay
- Attempt 3: 4 seconds delay
- Attempt 4: 8 seconds delay
- Attempt 5: 16 seconds delay
- Attempt 6+: 30 seconds delay (capped)

### Max Reconnection Attempts

The client limits the number of reconnection attempts to prevent infinite reconnection loops.

**Configuration:**
```typescript
maxReconnectAttempts: 10  // Default: 10 attempts
```

**Behavior:**
- After `maxReconnectAttempts` failed attempts, reconnection stops
- Client enters `DISCONNECTED` state
- Manual reconnection required via `connect()` method

### Reconnection State Management

The client manages reconnection state through the following states:

1. **CONNECTING**: Initial connection attempt
2. **CONNECTED**: Successfully connected
3. **RECONNECTING**: Attempting to reconnect after disconnection
4. **DISCONNECTED**: Connection closed, not attempting to reconnect

**State Transitions:**
```
DISCONNECTED → CONNECTING → CONNECTED
CONNECTED → RECONNECTING (on disconnect)
RECONNECTING → CONNECTED (on successful reconnect)
RECONNECTING → DISCONNECTED (after max attempts)
```

### Implementation Example

```typescript
import { WebSocketClient } from '@/lib/api/websocket'

const client = new WebSocketClient({
  url: 'ws://localhost:8000/ws/events/',
  reconnectDelay: 1000,           // Base delay: 1 second
  maxReconnectAttempts: 10,       // Max 10 attempts
  pingInterval: 30000,             // Send ping every 30 seconds
  connectionTimeout: 10000,       // Connection timeout: 10 seconds
  autoReconnect: true              // Enable automatic reconnection
})

// Connect
client.connect()

// Listen for state changes
client.on('state_change', ({ newState }) => {
  console.log('Connection state:', newState)
})

// Listen for reconnection events
client.on('reconnecting', ({ attemptNumber, delay }) => {
  console.log(`Reconnecting (attempt ${attemptNumber}) in ${delay}ms`)
})
```

### Best Practices

1. **Handle Reconnection Events**: Listen for `state_change` events to update UI
2. **Resubscribe on Reconnect**: Re-subscribe to event types after reconnection
3. **Exponential Backoff**: Use exponential backoff to prevent server overload
4. **Max Attempts**: Set reasonable max attempts to prevent infinite loops
5. **User Feedback**: Inform users when connection is lost and when reconnecting

### Error Handling

The client handles various error scenarios:

- **Connection Errors**: Automatically attempts reconnection
- **Network Errors**: Uses exponential backoff for retries
- **Authentication Errors**: Stops reconnection (requires user action)
- **Server Errors**: Attempts reconnection with backoff

### Configuration Options

```typescript
interface WebSocketClientOptions {
  url?: string                    // WebSocket URL
  reconnectDelay?: number         // Base reconnection delay (ms)
  maxReconnectAttempts?: number  // Maximum reconnection attempts
  pingInterval?: number          // Ping interval (ms)
  connectionTimeout?: number     // Connection timeout (ms)
  autoReconnect?: boolean        // Enable automatic reconnection
}
```

## Testing

### Server-Side Tests

Test cases cover:
- Ping/pong heartbeat mechanism
- Connection timeout detection
- Automatic connection cleanup
- Health check loop functionality
- Background task cancellation

### Client-Side Tests

Test cases cover:
- Exponential backoff calculation
- Max reconnection attempts
- State management
- Reconnection event handling
- Error scenarios

## Monitoring

### Metrics

The following metrics are logged for monitoring:

- `websocket_ping_sent`: Server ping sent
- `websocket_pong_received`: Client pong received
- `websocket_pong_timeout`: Pong timeout detected
- `websocket_connection_timeout`: Connection timeout detected
- `websocket_connection_inactive_timeout`: Inactivity timeout detected

### Logging

All connection health events are logged with structured logging:
- Connection state changes
- Ping/pong events
- Timeout events
- Cleanup events

## Troubleshooting

### Common Issues

1. **Frequent Disconnections**
   - Check network stability
   - Verify ping/pong intervals are appropriate
   - Review connection timeout settings

2. **Reconnection Loops**
   - Check max reconnection attempts
   - Verify exponential backoff is working
   - Review server logs for errors

3. **Connection Timeouts**
   - Increase `WEBSOCKET_CONNECTION_TIMEOUT` if needed
   - Check for network issues
   - Verify client is responding to pings

## References

- [WebSocket API Documentation](WEBSOCKET_API.md)
- [Django Channels Documentation](https://channels.readthedocs.io/)
- [WebSocket Protocol RFC 6455](https://tools.ietf.org/html/rfc6455)


---

# Webhook API Documentation

Complete guide for webhook subscriptions, delivery, and retry logic, including ODPS (Open Data Product Standard) event support.

## Table of Contents

1. [Overview](#overview)
2. [Webhook Subscriptions](#webhook-subscriptions)
3. [Event Types](#event-types)
4. [ODPS Events](#odps-events)
5. [Delivery and Retry](#delivery-and-retry)
6. [Authentication](#authentication)
7. [API Reference](#api-reference)
8. [Payload Examples](#payload-examples)
9. [Configuration Examples](#configuration-examples)
10. [Best Practices](#best-practices)

---

## Overview

The webhook system provides:

- **Event Subscriptions**: Subscribe to specific event types including ODPS events
- **Automatic Delivery**: Deliver webhooks asynchronously when events occur
- **Retry Logic**: Exponential backoff retry (1s, 5s, 30s, 5m, 30m)
- **Authentication**: HMAC-SHA256 signature for webhook authentication
- **Delivery Tracking**: Complete delivery history and status tracking
- **ODPS Support**: Full support for Open Data Product Standard events

---

## Webhook Subscriptions

### Creating a Webhook

Webhooks can be created via the REST API or programmatically. Each webhook subscribes to one or more event types and will receive notifications when those events occur.

### Webhook Configuration

- **URL**: Endpoint to receive webhooks (must be HTTPS in production)
- **Secret**: Shared secret for HMAC signature generation
- **Event Types**: List of event types to subscribe to
- **Status**: ACTIVE, PAUSED, or DISABLED
- **Max Retries**: Maximum number of delivery retries (default: 5)
- **Retry Intervals**: Retry intervals in seconds (default: [1, 5, 30, 300, 1800])

---

## Event Types

### Contract Events

- `contract.created`: Contract created
- `contract.updated`: Contract updated
- `contract.deleted`: Contract deleted

### Asset Events

- `asset.created`: Asset created
- `asset.updated`: Asset updated
- `asset.activated`: Asset activated

### Ingestion Events

- `ingestion.completed`: Scheduled ingestion completed
- `ingestion.failed`: Scheduled ingestion failed

### Quality Events

- `quality.check.completed`: Data quality check completed
- `compliance.check.completed`: Compliance check completed

### Version Events

- `version.created`: Dataset version created
- `version.updated`: Dataset version updated

---

## ODPS Events

The webhook system provides comprehensive support for Open Data Product Standard (ODPS) events. These events are triggered when ODPS contracts are created, updated, normalized, linked, or exported.

### ODPS Event Types

#### Lifecycle Events

- **`odps.created`**: ODPS contract created
  - Triggered when a new ODPS contract is created or generated from an ODCS contract
  - Contains contract metadata, ODPS version, and status information

- **`odps.updated`**: ODPS contract updated
  - Triggered when an existing ODPS contract is modified
  - Contains information about what changed

- **`odps.deleted`**: ODPS contract deleted
  - Triggered when an ODPS contract is deleted
  - Contains contract identification information

#### Processing Events

- **`odps.normalized`**: ODPS contract normalized
  - Triggered when an ODPS contract is successfully normalized
  - Contains normalization status and metadata

#### Linking Events

- **`odps.linked`**: ODPS contract linked to another contract
  - Triggered when an ODPS contract is linked to an ODCS contract or another ODPS contract
  - Contains source and target contract IDs

- **`odps.unlinked`**: ODPS contract unlinked from another contract
  - Triggered when a link between ODPS contracts is removed
  - Contains source and target contract IDs

#### Export Events

- **`odps.export.started`**: ODPS export operation started
  - Triggered when an ODPS contract export begins
  - Contains export format and target information

- **`odps.export.completed`**: ODPS export operation completed successfully
  - Triggered when an ODPS contract export finishes successfully
  - Contains export format and result information

- **`odps.export.failed`**: ODPS export operation failed
  - Triggered when an ODPS contract export fails
  - Contains error information and export format

### Subscribing to ODPS Events

You can subscribe to individual ODPS events or all ODPS events:

```json
{
  "name": "ODPS Lifecycle Webhook",
  "url": "https://example.com/webhooks/odps",
  "event_types": [
    "odps.created",
    "odps.updated",
    "odps.deleted"
  ],
  "status": "ACTIVE"
}
```

Or subscribe to all ODPS events:

```json
{
  "name": "All ODPS Events Webhook",
  "url": "https://example.com/webhooks/odps-all",
  "event_types": [
    "odps.created",
    "odps.updated",
    "odps.deleted",
    "odps.normalized",
    "odps.linked",
    "odps.unlinked",
    "odps.export.started",
    "odps.export.completed",
    "odps.export.failed"
  ],
  "status": "ACTIVE"
}
```

---

## Delivery and Retry

### Delivery Process

1. **Event Triggered**: ODPS event occurs in the system
2. **Webhook Matching**: Find active webhooks subscribed to the event type
3. **Payload Creation**: Build webhook payload with event data
4. **Payload Validation**: Validate ODPS webhook payload structure and data
5. **Signature Generation**: Generate HMAC-SHA256 signature
6. **HTTP Delivery**: POST payload to webhook URL
7. **Status Tracking**: Track delivery status and response

### Retry Logic

Exponential backoff retry with configurable intervals:

- **Attempt 1**: 1 second delay
- **Attempt 2**: 5 seconds delay
- **Attempt 3**: 30 seconds delay
- **Attempt 4**: 5 minutes delay
- **Attempt 5**: 30 minutes delay

After max retries, delivery moves to dead letter queue.

### Dead Letter Queue

Permanently failed deliveries (after max retries) are marked as `DEAD_LETTER` and can be manually retried via API.

### Webhook Hardening (Phase 120J)

#### SSRF Guard

Webhook URLs are validated before registration and before each delivery to prevent Server-Side Request Forgery:

- **Blocked destinations**: Private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, ::1, fd00::/8), link-local (169.254.x), cloud metadata endpoints (169.254.169.254)
- **Scheme enforcement**: Only `https://` URLs accepted in production. `http://` allowed in development/staging for local testing.
- **DNS resolution**: Target hostname is resolved before connection to prevent DNS rebinding. The resolved IP is checked against the blocklist.
- **Redirect following**: Disabled — webhooks do not follow HTTP redirects to prevent redirect-to-internal attacks.

#### Async Delivery via Job Queue

Webhook deliveries are dispatched asynchronously via the RQ job queue to avoid blocking the request path:

1. **Event emitted** → webhook delivery job enqueued to `job_default` queue
2. **Worker picks up** job and performs HTTP POST with timeout (10s connect, 30s read)
3. **Circuit breaker** per webhook URL: after 5 consecutive delivery failures, the webhook is temporarily paused (circuit OPEN for 5 minutes) to prevent flooding a down endpoint
4. **DLQ integration**: Failed deliveries after max retries are written to the dead letter queue with full payload for manual retry

#### Delivery Guarantees

- **At-least-once**: Events may be delivered more than once (consumer must be idempotent). Each delivery includes `X-Webhook-Delivery-ID` for deduplication.
- **Ordering**: Not guaranteed across webhooks. Events for the same resource are delivered in order within a single webhook subscription.
- **Timeout**: Webhook endpoints must respond within 30 seconds or the delivery is marked as failed and retried.

---

## Authentication

### HMAC Signature

All webhooks include an HMAC-SHA256 signature in the `X-Webhook-Signature` header. The signature is computed from the JSON payload using the webhook secret.

**Signature Generation**:

```python
import hmac
import hashlib
import json

# Sort keys for consistent signature
payload_json = json.dumps(payload, sort_keys=True)

# Generate signature
signature = hmac.new(
    secret.encode('utf-8'),
    payload_json.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

**HTTP Headers**:

- `Content-Type: application/json`
- `X-Webhook-Signature: <64-character hex string>`
- `X-Webhook-Event-Type: <event_type>`
- `User-Agent: DataInteroperabilityHub/1.0`

### Verification

```python
import hmac
import hashlib

# In webhook receiver
received_signature = request.headers.get('X-Webhook-Signature')
payload_json = request.body.decode('utf-8')

expected_signature = hmac.new(
    secret.encode('utf-8'),
    payload_json.encode('utf-8'),
    hashlib.sha256
).hexdigest()

if hmac.compare_digest(received_signature, expected_signature):
    # Valid webhook
    process_webhook(payload)
else:
    # Invalid signature - reject
    return 401, "Invalid signature"
```

**Security Note**: Always use `hmac.compare_digest()` to prevent timing attacks.

---

## API Reference

### Webhook CRUD API

#### `POST /api/v1/webhooks/`

Create webhook subscription.

**Request Body**:
```json
{
  "name": "ODPS Created Webhook",
  "url": "https://example.com/webhooks/odps-created",
  "event_types": ["odps.created"],
  "status": "ACTIVE",
  "max_retries": 5,
  "retry_intervals": [1, 5, 30, 300, 1800]
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "ODPS Created Webhook",
  "url": "https://example.com/webhooks/odps-created",
  "event_types": ["odps.created"],
  "status": "ACTIVE",
  "max_retries": 5,
  "retry_intervals": [1, 5, 30, 300, 1800],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/v1/webhooks/`

List webhook subscriptions.

**Query Parameters**:
- `status`: Filter by status (ACTIVE, PAUSED, DISABLED)
- `event_type`: Filter by event type

**Response** (200 OK):
```json
{
  "count": 2,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "ODPS Created Webhook",
      "url": "https://example.com/webhooks/odps-created",
      "event_types": ["odps.created"],
      "status": "ACTIVE"
    }
  ]
}
```

#### `GET /api/v1/webhooks/{id}/`

Get webhook subscription.

#### `PATCH /api/v1/webhooks/{id}/`

Update webhook subscription.

#### `DELETE /api/v1/webhooks/{id}/`

Delete webhook subscription.

#### `POST /api/v1/webhooks/{id}/test/`

Test webhook delivery with a test payload.

#### `GET /api/v1/webhooks/{id}/deliveries/`

Get webhook delivery history.

**Response** (200 OK):
```json
{
  "count": 10,
  "results": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "event_type": "odps.created",
      "status": "SUCCESS",
      "attempt_number": 1,
      "http_status_code": 200,
      "delivered_at": "2024-01-15T10:31:00Z",
      "created_at": "2024-01-15T10:30:55Z"
    }
  ]
}
```

#### `GET /api/v1/webhooks/event-types/`

Get available webhook event types.

**Query Parameters**:
- `odps_only`: If `true`, return only ODPS event types

**Response** (200 OK):
```json
{
  "event_types": [
    {
      "value": "odps.created",
      "label": "ODPS Created"
    },
    {
      "value": "odps.updated",
      "label": "ODPS Updated"
    }
  ],
  "odps_event_types": [
    "odps.created",
    "odps.updated",
    "odps.deleted",
    "odps.normalized",
    "odps.linked",
    "odps.unlinked",
    "odps.export.started",
    "odps.export.completed",
    "odps.export.failed"
  ]
}
```

### Webhook Delivery API

#### `GET /api/v1/webhook-deliveries/`

List webhook deliveries (read-only).

#### `GET /api/v1/webhook-deliveries/{id}/`

Get webhook delivery details.

#### `POST /api/v1/webhook-deliveries/{id}/retry/`

Retry a failed webhook delivery.

---

## Payload Examples

### Standard Payload Structure

All webhook payloads follow this structure:

```json
{
  "event_type": "odps.created",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "data": {
    // Event-specific data
  }
}
```

### ODPS Event Payloads

#### `odps.created`

Triggered when an ODPS contract is created.

```json
{
  "event_type": "odps.created",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "asset_id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "DRAFT",
    "odps_version": "4.1",
    "original_format": "JSON",
    "normalization_status": "PENDING"
  }
}
```

#### `odps.updated`

Triggered when an ODPS contract is updated.

```json
{
  "event_type": "odps.updated",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:35:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "changes": {
      "status": {
        "old": "DRAFT",
        "new": "ACTIVE"
      },
      "odps_version": {
        "old": "4.0",
        "new": "4.1"
      }
    },
    "updated_fields": ["status", "odps_version"]
  }
}
```

#### `odps.deleted`

Triggered when an ODPS contract is deleted.

```json
{
  "event_type": "odps.deleted",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:40:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "deleted_at": "2024-01-15T10:40:00.123456Z"
  }
}
```

#### `odps.normalized`

Triggered when an ODPS contract is successfully normalized.

```json
{
  "event_type": "odps.normalized",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:45:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "normalization_status": "NORMALIZED_OK",
    "odps_version": "4.1",
    "validation_status": "VALID",
    "normalized_at": "2024-01-15T10:45:00.123456Z"
  }
}
```

#### `odps.linked`

Triggered when an ODPS contract is linked to another contract.

```json
{
  "event_type": "odps.linked",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:50:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_id": "770e8400-e29b-41d4-a716-446655440002",
    "link_type": "ODPS_TO_ODCS",
    "linked_at": "2024-01-15T10:50:00.123456Z"
  }
}
```

#### `odps.unlinked`

Triggered when a link between ODPS contracts is removed.

```json
{
  "event_type": "odps.unlinked",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:55:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_id": "770e8400-e29b-41d4-a716-446655440002",
    "link_type": "ODPS_TO_ODCS",
    "unlinked_at": "2024-01-15T10:55:00.123456Z"
  }
}
```

#### `odps.export.started`

Triggered when an ODPS export operation begins.

```json
{
  "event_type": "odps.export.started",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T11:00:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_format": "JSON",
    "export_target": "FILE",
    "started_at": "2024-01-15T11:00:00.123456Z"
  }
}
```

#### `odps.export.completed`

Triggered when an ODPS export operation completes successfully.

```json
{
  "event_type": "odps.export.completed",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T11:05:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_format": "JSON",
    "export_target": "FILE",
    "export_url": "https://storage.example.com/exports/odps-550e8400.json",
    "file_size": 12345,
    "started_at": "2024-01-15T11:00:00.123456Z",
    "completed_at": "2024-01-15T11:05:00.123456Z",
    "duration_seconds": 300
  }
}
```

#### `odps.export.failed`

Triggered when an ODPS export operation fails.

```json
{
  "event_type": "odps.export.failed",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T11:10:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_format": "JSON",
    "export_target": "FILE",
    "error": {
      "code": "EXPORT_FAILED",
      "message": "Failed to write export file",
      "details": "Disk quota exceeded"
    },
    "started_at": "2024-01-15T11:00:00.123456Z",
    "failed_at": "2024-01-15T11:10:00.123456Z",
    "duration_seconds": 600
  }
}
```

---

## Configuration Examples

### Python Example

```python
import requests

# Create ODPS webhook
webhook_data = {
    "name": "ODPS Lifecycle Webhook",
    "url": "https://example.com/webhooks/odps",
    "event_types": [
        "odps.created",
        "odps.updated",
        "odps.deleted",
        "odps.normalized"
    ],
    "status": "ACTIVE",
    "max_retries": 5,
    "retry_intervals": [1, 5, 30, 300, 1800]
}

response = requests.post(
    "https://api.example.com/api/v1/webhooks/",
    json=webhook_data,
    headers={
        "Authorization": "Bearer <token>",
        "Content-Type": "application/json"
    }
)

webhook = response.json()
print(f"Created webhook: {webhook['id']}")
```

### cURL Example

```bash
# Create ODPS webhook
curl -X POST https://api.example.com/api/v1/webhooks/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ODPS Export Webhook",
    "url": "https://example.com/webhooks/odps-export",
    "event_types": [
      "odps.export.started",
      "odps.export.completed",
      "odps.export.failed"
    ],
    "status": "ACTIVE"
  }'
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

// Create ODPS webhook
const webhookData = {
  name: 'ODPS Linked Events Webhook',
  url: 'https://example.com/webhooks/odps-links',
  event_types: [
    'odps.linked',
    'odps.unlinked'
  ],
  status: 'ACTIVE',
  max_retries: 5,
  retry_intervals: [1, 5, 30, 300, 1800]
};

axios.post('https://api.example.com/api/v1/webhooks/', webhookData, {
  headers: {
    'Authorization': 'Bearer <token>',
    'Content-Type': 'application/json'
  }
})
.then(response => {
  console.log('Created webhook:', response.data.id);
})
.catch(error => {
  console.error('Error creating webhook:', error);
});
```

### Webhook Receiver Example (Flask)

```python
from flask import Flask, request, jsonify
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = "your-webhook-secret"

@app.route('/webhooks/odps', methods=['POST'])
def handle_odps_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data()

    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return jsonify({"error": "Invalid signature"}), 401

    # Process webhook
    data = request.json
    event_type = data['event_type']

    if event_type == 'odps.created':
        handle_odps_created(data)
    elif event_type == 'odps.updated':
        handle_odps_updated(data)
    # ... handle other event types

    return jsonify({"status": "ok"}), 200

def handle_odps_created(data):
    contract_id = data['data']['contract_id']
    print(f"ODPS contract created: {contract_id}")
    # Process the event...

if __name__ == '__main__':
    app.run(port=5000)
```

---

## Best Practices

### Webhook URL Design

1. **HTTPS Only**: Always use HTTPS for webhook URLs in production
2. **Idempotency**: Design webhook handlers to be idempotent (handle duplicate deliveries)
3. **Quick Response**: Respond quickly (within 5 seconds) to avoid timeouts
4. **Status Codes**: Return 2xx for success, 4xx/5xx for retry
5. **Async Processing**: Process webhooks asynchronously when possible

### Security Best Practices

1. **Secret Rotation**: Rotate webhook secrets periodically
2. **Signature Verification**: Always verify HMAC signature before processing
3. **Rate Limiting**: Implement rate limiting on webhook receivers
4. **IP Whitelisting**: Consider IP whitelisting for additional security
5. **TLS Verification**: Verify TLS certificates when making outbound requests

### Error Handling

1. **Retry Logic**: Use exponential backoff for retries (already handled by the system)
2. **Dead Letter Queue**: Monitor dead letter queue for issues
3. **Alerting**: Set up alerts for high failure rates
4. **Manual Retry**: Support manual retry for failed deliveries via API
5. **Logging**: Log all webhook deliveries for debugging

### ODPS-Specific Best Practices

1. **Event Filtering**: Subscribe only to ODPS events you need
2. **Payload Validation**: Validate ODPS payload structure in your receiver
3. **Contract Lookup**: Use `contract_id` from payload to fetch full contract details if needed
4. **Version Handling**: Check `odps_version` field to handle different ODPS versions
5. **Link Tracking**: Track `odps.linked` and `odps.unlinked` events to maintain relationship graphs

### Performance Considerations

1. **Batch Processing**: Process multiple webhooks in batches when possible
2. **Database Indexing**: Index webhook delivery tables for faster queries
3. **Monitoring**: Monitor webhook delivery latency and success rates
4. **Scaling**: Scale webhook receivers horizontally for high throughput

---

## Related Documentation

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [API Standards](API_STANDARDS.md) - API consistency standards
- [Event Bus](EVENT_BUS.md) - Event-driven communication
- [Event Types Reference](EVENT_TYPES_REFERENCE.md) - Complete event type documentation
- [Services Architecture](SERVICES_ARCHITECTURE.md) - Webhook service architecture

---

## Support

For issues or questions about webhooks:

1. Check delivery history via API: `GET /api/v1/webhooks/{id}/deliveries/`
2. Review error messages in failed deliveries
3. Test webhook configuration: `POST /api/v1/webhooks/{id}/test/`
4. Contact support with webhook ID and delivery ID for troubleshooting

