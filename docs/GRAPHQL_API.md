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

**Last Updated**: 2025-12-22
**Maintainer**: Engineering Team
**Status**: ✅ Complete (with ODPS support)
