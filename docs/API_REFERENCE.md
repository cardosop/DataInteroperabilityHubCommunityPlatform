# API Reference

> Consolidated API reference covering all endpoints, error codes, and error handling.
>
> **Source**: Merged from 9 API reference docs during Phase 120D documentation consolidation.

---


---

# API Reference

Complete reference for all APIs in the Data Interoperability Hub.

## API Overview

The Data Interoperability Hub provides multiple API interfaces:

- **REST API** (`/api/v1/`) - Primary RESTful API
- **GraphQL API** (`/graphql`) - Flexible GraphQL queries
- **WebSocket API** (`/ws/`) - Real-time updates

## Base URLs

- **Development**: `http://localhost:8000`
- **Staging**: `https://staging-api.datahub.example.com`
- **Production**: `https://api.datahub.example.com`

## Authentication

All APIs require authentication. See [Authentication](#authentication) section below.

### JWT Token Authentication

```bash
# Login to get token
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"password"}'

# Use token in requests
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/contracts/
```

### API Key Authentication

```bash
curl -H "X-API-Key: <api-key>" \
  http://localhost:8000/api/v1/contracts/
```

### ODPS Endpoint Authentication

All ODPS endpoints require authentication:

- **JWT Token**: Required for all ODPS operations
- **API Key**: Supported for programmatic access
- **Tenant Scoping**: All operations are automatically scoped to the authenticated user's tenant
- **Authorization**: Standard user permissions apply (no special roles required for basic operations)

### BaaS Platform Authentication

BaaS Platform endpoints require authentication:

- **JWT Token**: Required for API key management and usage tracking
- **API Key**: Supported for all BaaS endpoints (tier-based access)
- **Tenant Scoping**: All operations are automatically scoped to the authenticated user's tenant
- **Authorization Requirements**:
  - **API Key Management**: `TENANT_ADMIN` or `DEVELOPER` role
  - **Usage Tracking**: `TENANT_ADMIN` or `DEVELOPER` role
  - **Developer Portal**: Public endpoints (no authentication required)

### ODH Integration Authentication

ODH Integration endpoints require authentication and specific authorization:

- **JWT Token**: Required for all ODH operations
- **API Key**: Supported for programmatic access (tier-based rate limiting)
- **Tenant Scoping**: All operations are automatically scoped to the authenticated user's tenant
- **Authorization Requirements**:
  - **Model Registry**: `DATA_ENGINEER`, `DATA_SCIENTIST`, or `TENANT_ADMIN` role
  - **Training Jobs**: `DATA_ENGINEER`, `DATA_SCIENTIST`, or `TENANT_ADMIN` role
  - **Inference Deployments**: `DATA_ENGINEER`, `DATA_SCIENTIST`, `DATA_CONSUMER`, or `TENANT_ADMIN` role

### Marketplace Integration Authentication

Marketplace Integration endpoints require authentication and specific authorization:

- **JWT Token**: Required for all marketplace operations
- **API Key**: Supported for programmatic access
- **Tenant Scoping**: All operations are automatically scoped to the authenticated user's tenant
- **Authorization Requirements**:
  - **Read Operations** (List/Get): Authenticated user (tenant-scoped)
  - **Write Operations** (Create/Update/Delete): `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

## REST API

### API Standards

All REST endpoints follow consistent standards:
- [API Standards Documentation](API_STANDARDS.md) - Response formats, pagination, filtering, sorting
- [API Error Codes](API_ERROR_CODES.md) - Complete error code reference

### Endpoints

#### Contracts
- `GET /api/v1/contracts/` - List contracts
- `POST /api/v1/contracts/` - Create contract
- `GET /api/v1/contracts/{id}/` - Get contract
- `PUT /api/v1/contracts/{id}/` - Update contract
- `DELETE /api/v1/contracts/{id}/` - Delete contract
- `POST /api/v1/contracts/{id}/validate/` - Validate contract
- `POST /api/v1/contracts/{id}/lint/` - Lint contract
- `POST /api/v1/contracts/{id}/convert/` - Convert contract format

#### ODPS (Open Data Product Standard)

**ODPS Product Creation**

- `POST /api/v1/contracts/products/` - Create ODPS product (Product-First flow)
  - **Description**: Create an ODPS product with automatic ODCS extraction from `product.contract.spec`
  - **Request Body**:
    ```json
    {
      "original_raw": "ODPS document (JSON or YAML string)",
      "original_format": "JSON" | "YAML",
      "resolve_external_refs": true,
      "asset_id": "optional-asset-uuid"
    }
    ```
  - **Response**: Returns both ODPS and ODCS contracts with workflow instance ID
  - **See**: [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md#rest-api-ingestion)

**ODPS Export and Download**

- `GET /api/v1/contracts/{id}/export/` - Export contract (ODPS, ODCS, or HubContract format)
  - **Query Parameters**:
    - `format`: `odps`, `odcs`, or `hubcontract` (default: `hubcontract`)
    - `output_format`: `json` or `yaml` (default: `json`)
    - `version`: ODPS version (e.g., `4.1`, optional, defaults to contract version)
  - **Response**: Returns contract in requested format
  - **See**: [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md#export-and-download)

- `GET /api/v1/contracts/{id}/download/` - Download contract as file
  - **Query Parameters**: Same as export endpoint
  - **Response**: Downloads file with appropriate extension (`.odps.json`, `.odps.yaml`, etc.)
  - **Content-Type**: `application/json` or `application/x-yaml`
  - **Content-Disposition**: `attachment; filename="product-{id}.odps.json"`

**ODPS Linking**

- `POST /api/v1/contracts/{odcs_contract_id}/link-odps/` - Link ODPS to ODCS contract
  - **Description**: Link an existing ODCS contract to an ODPS contract (or create new ODPS and link)
  - **Request Body**:
    ```json
    {
      "odps_contract_id": "existing-odps-contract-uuid",
      "odps_raw": "optional-new-odps-document",
      "odps_format": "JSON" | "YAML",
      "resolve_external_refs": true
    }
    ```
  - **Response**: Returns linked ODPS contract
  - **See**: [ODPS Creation Flows](ODPS_CREATION_FLOWS.md#technical-first-flow)

- `POST /api/v1/contracts/{id}/unlink-odps/` - Unlink ODPS from ODCS contract
  - **Description**: Remove bidirectional link between ODPS and ODCS contracts
  - **Response**: Returns unlinked contracts

- `GET /api/v1/contracts/{id}/links/` - List contract links
  - **Description**: Get all linked contracts (ODPS ↔ ODCS)
  - **Response**: Returns list of linked contracts with link metadata

#### Assets
- `GET /api/v1/assets/` - List assets
- `POST /api/v1/assets/` - Create asset
- `POST /api/v1/assets/data-first/` - Create asset, dataset, and contract from uploaded file (data-first flow)
- `GET /api/v1/assets/{id}/` - Get asset
- `PUT /api/v1/assets/{id}/` - Update asset
- `DELETE /api/v1/assets/{id}/` - Delete asset
- `POST /api/v1/assets/{id}/datasets/` - Attach dataset
- `POST /api/v1/assets/{id}/contracts/` - Attach contract
- `POST /api/v1/assets/{id}/activate/` - Activate asset

##### Data-First Asset Creation

**Endpoint**: `POST /api/v1/assets/data-first/`

**Description**: Create asset, dataset, and contract from an uploaded file in one call. Infers schema from file, generates ODCS contract, runs AssetCreationWorkflow.

**Request body**:
```json
{
  "file_id": "uuid",
  "key": "my-asset-key",
  "name": "My Asset Name",
  "description": "Optional",
  "domain": "sales",
  "visibility": "INTERNAL"
}
```

**Required**: `file_id`, `key`, `name`. **Optional**: `description`, `domain`, `visibility`.

**Response (201)**:
```json
{
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "contract_id": "uuid"
}
```

**Errors**: 400 (missing/invalid fields), 401 (unauthenticated), 404 (file not found or cross-tenant).

**Runbook**: [docs/runbooks/DATA_FIRST_ASSET_CREATION.md](runbooks/DATA_FIRST_ASSET_CREATION.md)

#### Datasets
- `GET /api/v1/datasets/` - List datasets
- `POST /api/v1/datasets/` - Create dataset
- `GET /api/v1/datasets/{id}/` - Get dataset
- `PUT /api/v1/datasets/{id}/` - Update dataset (full update)
- `PATCH /api/v1/datasets/{id}/` - Update dataset (partial update; supports `asset` for linking)
- `DELETE /api/v1/datasets/{id}/` - Delete dataset

**Dataset Update (PATCH/PUT) — Asset linking**: To link a dataset to an asset, send `asset` (UUID) in the request body. To unlink, send `asset: null`. Response includes `asset_id` and `asset_name` when linked. Writable fields: `asset`, `format`.

##### Dataset Update — Asset/Asset ID

**Endpoint**: `PATCH /api/v1/datasets/{id}/` or `PUT /api/v1/datasets/{id}/`

**Request body** (partial update via PATCH):
```json
{
  "asset": "uuid-of-asset-to-link",
  "format": "CSV"
}
```

To **unlink** dataset from asset: `{"asset": null}`.

**Response**: Same as GET dataset; includes `asset_id` and `asset_name` when linked.

**Validation**: `asset` must be a valid UUID of an asset in the same tenant, or `null`. 400 if invalid.

#### Data Quality
- `GET /api/v1/dq/runs/` - List DQ runs
- `POST /api/v1/dq/runs/` - Create DQ run
- `GET /api/v1/dq/runs/{id}/` - Get DQ run
- `GET /api/v1/dq/runs/{id}/results/` - Get DQ results

#### Compliance
- `GET /api/v1/compliance/runs/` - List compliance runs
- `POST /api/v1/compliance/runs/` - Create compliance run
- `GET /api/v1/compliance/runs/{id}/` - Get compliance run
- `GET /api/v1/compliance/runs/{id}/results/` - Get compliance run results

#### Marketplace

Internal marketplace (Hub catalog, orders, entitlements): `/api/v1/marketplace/`. External integrations (connections, sync, mappings): `/api/v1/integrations/marketplace/`. See [Internal vs External Marketplace](MARKETPLACE_INTERNAL_VS_EXTERNAL.md) for the full split and URLs.

- `GET /api/v1/marketplace/listings/` - List marketplace listings
- `POST /api/v1/marketplace/listings/` - Create listing
- `GET /api/v1/marketplace/listings/{id}/` - Get listing
- `POST /api/v1/marketplace/orders/` - Create order
- `GET /api/v1/marketplace/orders/{id}/` - Get order

#### Marketplace Integration
- `GET /api/v1/integrations/marketplace/connections/` - List marketplace connections
- `POST /api/v1/integrations/marketplace/connections/` - Create marketplace connection
- `GET /api/v1/integrations/marketplace/connections/{id}/` - Get marketplace connection
- `PATCH /api/v1/integrations/marketplace/connections/{id}/` - Update marketplace connection
- `DELETE /api/v1/integrations/marketplace/connections/{id}/` - Delete marketplace connection
- `POST /api/v1/integrations/marketplace/connections/{id}/test/` - Test marketplace connection
- `GET /api/v1/integrations/marketplace/sync/` - List marketplace sync jobs
- `POST /api/v1/integrations/marketplace/sync/` - Create marketplace sync job
- `GET /api/v1/integrations/marketplace/sync/{id}/` - Get marketplace sync job
- `POST /api/v1/integrations/marketplace/sync/{id}/cancel/` - Cancel marketplace sync job
- `GET /api/v1/integrations/marketplace/mappings/` - List marketplace mappings
- `GET /api/v1/integrations/marketplace/mappings/{id}/` - Get marketplace mapping
- `DELETE /api/v1/integrations/marketplace/mappings/{id}/` - Delete marketplace mapping

#### Governance
- `GET /api/v1/governance/access-requests/` - List access requests
- `POST /api/v1/governance/access-requests/` - Create access request
- `GET /api/v1/governance/access-requests/{id}/` - Get access request
- `POST /api/v1/governance/access-requests/{id}/approve/` - Approve request
- `POST /api/v1/governance/access-requests/{id}/reject/` - Reject request

#### Files
- `GET /api/v1/files/` - List files
- `POST /api/v1/files/init/` - Initiate multipart upload
- `POST /api/v1/files/{id}/complete/` - Complete multipart upload
- `GET /api/v1/files/{id}/download/` - Download file

#### Jobs
- `GET /api/v1/jobs/` - List jobs
- `POST /api/v1/jobs/` - Create job
- `GET /api/v1/jobs/{id}/` - Get job
- `POST /api/v1/jobs/{id}/cancel/` - Cancel job

#### Search
- `GET /api/v1/search/` - Search across resources
- `GET /api/v1/search/contracts/` - Search contracts
- `GET /api/v1/search/assets/` - Search assets

#### Authentication
- `GET /api/v1/auth/me/` - Get current user (id, email, name, tenant_id, roles, permissions, avatar, preferences, feature_tenant_switch_enabled)
- `PATCH /api/v1/auth/me/` - Update profile (display_name, avatar, preferences); see [User Profile](#user-profile)
- `GET /api/v1/auth/me/tenants/` - List tenants the user has membership in (tenant switch); see [Tenant Switch](#tenant-switch)
- `POST /api/v1/auth/switch-tenant/` - Switch active tenant context; see [Tenant Switch](#tenant-switch)
- `POST /api/v1/auth/register/` - Register new user (see [User Registration](#user-registration))
- `POST /api/v1/auth/login/` - Login (get JWT token)
- `POST /api/v1/auth/logout/` - Logout
- `POST /api/v1/auth/refresh/` - Refresh JWT token
- `POST /api/v1/auth/password-reset/` - Request password reset
- `POST /api/v1/auth/password-reset/confirm/` - Confirm password reset

**User Profile** (`GET` / `PATCH /api/v1/auth/me/`)

**GET** returns current user: `id`, `email`, `name`, `tenant_id`, `roles`, `permissions`, `created_at`, `last_login_at`, `avatar`, `preferences`, `feature_tenant_switch_enabled` (boolean; when false, tenant switch UI and X-Tenant-Id are disabled).

**PATCH** (partial update) request body:
```json
{
  "display_name": "Display Name",
  "avatar": "https://example.com/avatar.png",
  "preferences": {"theme": "dark", "language": "en"}
}
```
All fields optional. `preferences` must be a JSON object (max 10KB serialized). Requires authentication.

**User Registration** (`POST /api/v1/auth/register/`)

When `tenant_id` is **omitted**, the system creates a **personal tenant** for the user and assigns `DATA_PROVIDER` and `DATA_CONSUMER` roles. The user can immediately create assets, consume data, and access marketplace listings within their personal tenant.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "name": "Display Name",
  "tenant_id": "optional-tenant-uuid"
}
```

**Response** (201 Created): `id`, `email`, `name`, `tenant_id` (personal tenant UUID when created)

**When `tenant_id` provided**: User is associated with that tenant (unchanged behavior). **When `tenant_id` omitted**: Personal tenant created and returned; user receives `DATA_PROVIDER` and `DATA_CONSUMER` roles. See [ONBOARDING.md](ONBOARDING.md#personal-tenant-self-service-registration) and [Personal tenant creation failures](RUNBOOKS.md#personal-tenant-creation-failures) runbook.

**Tenant Switch** (`GET /api/v1/auth/me/tenants/`, `POST /api/v1/auth/switch-tenant/`)

Users with multiple tenants (e.g. personal + org via invitation) can switch active tenant context without re-login.

- **GET /api/v1/auth/me/tenants/** — Returns list of tenants the user has membership in: `[{ id, name, slug }]`. Requires authentication. Returns 403 when `FEATURE_TENANT_SWITCH_ENABLED` is false.
- **POST /api/v1/auth/switch-tenant/** — Request body: `{ "tenant_id": "uuid" }`. Validates membership; returns 200 with updated me summary (tenant_id overridden). Requires authentication. Returns 403 when feature disabled or user has no membership in target tenant.
- **X-Tenant-Id header** — When feature enabled, clients send `X-Tenant-Id: <uuid>` to scope requests to a switched tenant. Backend validates membership; 403 if invalid or feature disabled.

See [TENANT_SWITCH_PLAN.md](TENANT_SWITCH_PLAN.md) for migration and rollback.

#### Tenants
- `GET /api/v1/tenants/` - List tenants
- `POST /api/v1/tenants/` - Create tenant
- `GET /api/v1/tenants/{id}/` - Get tenant
- `PUT /api/v1/tenants/{id}/` - Update tenant
- `GET /api/v1/tenants/me/usage/` - Get current tenant usage (storage, API calls, limits); TENANT_ADMIN or PLATFORM_ADMIN
- `GET /api/v1/tenants/me/config/` - Get tenant configuration; TENANT_ADMIN or PLATFORM_ADMIN
- `PATCH /api/v1/tenants/me/config/` - Update tenant configuration (trust signals, versioning, workflows, etc.); TENANT_ADMIN or PLATFORM_ADMIN

#### Billing (useronboardfix Phase 9, 17)
- `GET /api/v1/billing/subscription/current/` - Get current subscription (plan, status, limits)
- `POST /api/v1/billing/subscription/current/change-plan/` - Change subscription plan; TENANT_ADMIN or PLATFORM_ADMIN; body: `{"plan_slug": "pro"}`
- `GET /api/v1/billing/plans/` - List available plans for subscription change
- `GET /api/v1/billing/invoices/` - List invoices for tenant
- `GET /api/v1/billing/invoices/{id}/` - Get invoice detail
- `GET /api/v1/billing/invoices/{id}/download/` - Redirect to invoice PDF or hosted URL

See [BILLING.md](BILLING.md) for full billing documentation. Runbook: [Subscription plan change failures](RUNBOOKS.md#subscription-plan-change-failures).

#### Users
- `GET /api/v1/users/` - List users
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/{id}/` - Get user
- `PUT /api/v1/users/{id}/` - Update user (roles, status); TENANT_ADMIN or PLATFORM_ADMIN

### Complete Endpoint Reference

For detailed endpoint documentation with request/response examples, see:
- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md) - Complete endpoint documentation

#### BaaS Platform (Backend as a Service)

**API Key Management**
- `POST /api/v1/baas/api-keys/` - Create API key
- `GET /api/v1/baas/api-keys/` - List API keys
- `GET /api/v1/baas/api-keys/{id}/` - Get API key
- `PATCH /api/v1/baas/api-keys/{id}/` - Update API key
- `DELETE /api/v1/baas/api-keys/{id}/` - Revoke API key

**Usage Tracking**
- `GET /api/v1/baas/usage/stats/` - Get usage statistics
- `GET /api/v1/baas/usage/by-endpoint/` - Get usage by endpoint
- `GET /api/v1/baas/usage/by-tenant/` - Get usage by tenant

**Developer Portal**
- `GET /api/v1/baas/docs/` - Get API documentation
- `GET /api/v1/baas/docs/openapi.json` - Get OpenAPI schema
- `GET /api/v1/baas/docs/sdks/` - Get SDK download links

**Authentication**: JWT token or API key (tier-based rate limiting)

**Rate Limiting**: Tier-based (FREE: 1000/hour, PRO: 10000/hour, ENTERPRISE: unlimited)

**See**: [BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md) and [BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md)

#### ODH Integration (Open Data Hub)

**Model Registry**
- `GET /api/v1/ml/models/` - List ML models
- `POST /api/v1/ml/models/` - Create ML model
- `GET /api/v1/ml/models/{id}/` - Get ML model
- `PATCH /api/v1/ml/models/{id}/` - Update ML model
- `DELETE /api/v1/ml/models/{id}/` - Delete ML model
- `GET /api/v1/ml/models/{id}/versions/` - Get model versions
- `POST /api/v1/ml/models/{id}/link-dataset/` - Link model to dataset

**Training Jobs**
- `POST /api/v1/ml/training/jobs/` - Submit training job
- `GET /api/v1/ml/training/jobs/` - List training jobs
- `GET /api/v1/ml/training/jobs/{id}/` - Get training job
- `POST /api/v1/ml/training/jobs/{id}/cancel/` - Cancel training job
- `GET /api/v1/ml/training/jobs/{id}/logs/` - Get training logs

**Inference Deployments**
- `POST /api/v1/ml/inference/deployments/` - Deploy model for inference
- `POST /api/v1/ml/inference/deployments/predict/` - Run inference prediction
- `GET /api/v1/ml/inference/deployments/` - List inference deployments
- `GET /api/v1/ml/inference/deployments/{id}/` - Get inference deployment
- `DELETE /api/v1/ml/inference/deployments/{id}/` - Undeploy model
- `GET /api/v1/ml/inference/deployments/{id}/metrics/` - Get inference metrics

**Authentication**: JWT token or API key (tier-based rate limiting)

**Authorization**: `DATA_ENGINEER`, `DATA_SCIENTIST`, or `TENANT_ADMIN` role

**Rate Limiting**: Tier-based

**See**: [ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md) and [ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md)

## GraphQL API

The GraphQL API provides flexible querying capabilities.

### Endpoint

- **URL**: `/graphql`
- **Method**: POST
- **Content-Type**: `application/json`

### Example Query

```graphql
query {
  contracts {
    id
    name
    status
    createdAt
  }
}
```

### ODPS Mutations

**Create ODPS Product**

```graphql
mutation {
  createODPS(input: {
    originalRaw: "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{...}}"
    originalFormat: JSON
    extractOdcs: true
    resolveExternalRefs: true
    assetId: "optional-asset-uuid"
  }) {
    odpsContract {
      id
      originalSpecType
      originalSpecVersion
      status
    }
    odcsContract {
      id
      originalSpecType
      originalSpecVersion
      status
    }
    workflowInstanceId
  }
}
```

**Link ODPS to ODCS**

```graphql
mutation {
  linkODPS(input: {
    odcsContractId: "odcs-contract-uuid"
    odpsContractId: "odps-contract-uuid"
  }) {
    odpsContract {
      id
      status
    }
    odcsContract {
      id
      status
    }
  }
}
```

**Export ODPS**

```graphql
mutation {
  exportODPS(input: {
    contractId: "odps-contract-uuid"
    format: ODPS
    outputFormat: JSON
    version: "4.1"
  }) {
    content
    format
    version
  }
}
```

### Interactive Documentation

- **GraphiQL**: Available at `/graphql` (when DEBUG=True)
- **GraphQL Playground**: Available via Strawberry GraphQL

### Documentation

See [GraphQL API Documentation](GRAPHQL_API.md) for complete GraphQL schema and examples.

## WebSocket API

Real-time updates via WebSocket connections.

### Endpoint

- **URL**: `/ws/`
- **Protocol**: WebSocket
- **Authentication**: JWT token in query string or header

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/?token=<jwt-token>');
```

### Events

- `contract.created` - Contract created
- `contract.updated` - Contract updated
- `asset.activated` - Asset activated
- `job.completed` - Job completed
- `dq.run.completed` - DQ run completed

### Documentation

See [WebSocket API Documentation](WEBSOCKET_API.md) for complete WebSocket API reference.

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available:

- **JSON**: `/api/v1/openapi.json`
- **YAML**: `/api/v1/openapi.yaml`

### Interactive Documentation

- **Swagger UI**: `/api-docs/`
- **ReDoc**: `/api-docs/redoc/`

## Rate Limiting

API requests are rate-limited to prevent abuse:

- **Default**: 1000 requests per hour per user
- **Burst**: 100 requests per minute
- **Headers**: Rate limit information in response headers:
  - `X-RateLimit-Limit`: Total requests allowed
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset timestamp

### ODPS Endpoint Rate Limiting

ODPS-specific endpoints have the following rate limits:

- **Create ODPS Product**: 20 requests per hour per user
- **Export/Download**: 100 requests per hour per user
- **Link/Unlink Operations**: 50 requests per hour per user
- **List Links**: 100 requests per hour per user

### Marketplace Integration Rate Limiting

Marketplace Integration endpoints have the following rate limits:

- **Connection Management**:
  - List/Get: 100 requests per hour per user
  - Create/Update/Delete: 10-20 requests per hour per user
  - Test Connection: 20 requests per hour per user
- **Sync Jobs**:
  - List/Get: 100 requests per hour per user
  - Create: 10 requests per hour per user
  - Cancel: 20 requests per hour per user
- **Mappings**:
  - List/Get: 100 requests per hour per user
  - Delete: 20 requests per hour per user

## Versioning

The API uses URL versioning:

- **Current Version**: `v1` (`/api/v1/`)
- **Version Header**: `X-API-Version: v1` (optional)

See [API Versioning Policy](API_VERSIONING_POLICY.md) for versioning strategy.

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "http_status": 400,
    "request_id": "uuid",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {}
  }
}
```

See [API Error Codes](API_ERROR_CODES.md) for complete error code reference.

### ODPS Error Codes

Common ODPS-specific error codes:

- `ODPS_INVALID_FORMAT` (400): Invalid ODPS document format
- `ODPS_VALIDATION_FAILED` (400): ODPS document validation failed
- `ODPS_VERSION_MISMATCH` (400): ODPS version mismatch
- `ODPS_REF_RESOLUTION_FAILED` (400): External $ref resolution failed
- `ODPS_LINKING_FAILED` (400): ODPS/ODCS linking failed
- `ODPS_EXPORT_FAILED` (500): ODPS export operation failed
- `ODPS_NORMALIZATION_FAILED` (500): ODPS normalization failed

### Marketplace Integration Error Codes

Common Marketplace Integration error codes:

- `MARKETPLACE_CONNECTION_INVALID` (400): Invalid marketplace connection configuration
- `MARKETPLACE_CONNECTION_TEST_FAILED` (400): Marketplace connection test failed
- `MARKETPLACE_CONNECTION_NOT_FOUND` (404): Marketplace connection not found
- `MARKETPLACE_SYNC_INVALID_DIRECTION` (400): Invalid sync direction
- `MARKETPLACE_SYNC_JOB_NOT_FOUND` (404): Sync job not found
- `MARKETPLACE_SYNC_JOB_CANNOT_CANCEL` (400): Sync job cannot be cancelled
- `MARKETPLACE_MAPPING_NOT_FOUND` (404): Marketplace mapping not found
- `MARKETPLACE_CONNECTOR_ERROR` (500): Marketplace connector error

### BaaS Platform Error Codes

Common BaaS Platform error codes:

- `BAAS_API_KEY_INVALID` (400): Invalid API key
- `BAAS_API_KEY_REVOKED` (401): API key has been revoked
- `BAAS_API_KEY_EXPIRED` (401): API key has expired
- `BAAS_QUOTA_EXCEEDED` (429): API quota exceeded for tier
- `BAAS_TIER_INVALID` (400): Invalid tier specified
- `BAAS_USAGE_TRACKING_FAILED` (500): Usage tracking operation failed
- `BAAS_DOCUMENTATION_NOT_FOUND` (404): Documentation resource not found

### ODH Integration Error Codes

Common ODH Integration error codes:

- `ODH_MODEL_NOT_FOUND` (404): ML model not found
- `ODH_MODEL_INVALID` (400): Invalid model configuration
- `ODH_TRAINING_JOB_NOT_FOUND` (404): Training job not found
- `ODH_TRAINING_JOB_FAILED` (500): Training job execution failed
- `ODH_INFERENCE_DEPLOYMENT_NOT_FOUND` (404): Inference deployment not found
- `ODH_INFERENCE_VALIDATION_FAILED` (400): Inference input/output validation failed
- `ODH_CLIENT_ERROR` (500): ODH service client error
- `ODH_CONNECTION_FAILED` (503): ODH service connection failed

## Pagination

List endpoints support pagination:

- **Page-based**: `?page=1&page_size=50`
- **Cursor-based**: `?cursor=<base64-encoded-cursor>&page_size=50`

See [API Standards](API_STANDARDS.md#pagination) for details.

## Filtering

Most list endpoints support filtering:

```bash
GET /api/v1/contracts/?owner_email=user@example.com&status=ACTIVE
```

See [API Standards](API_STANDARDS.md#filtering) for filtering syntax.

## List API Query Parameters (Resource Pickers)

List endpoints used by resource pickers (AssetPicker, ContractPicker, DatasetPicker, FilePicker) support the following params. See [RESOURCE_PICKER_LINKING_PLAN.md](../openspec/changes/useronboardfix/RESOURCE_PICKER_LINKING_PLAN.md) for picker integration.

| Endpoint | search | filter | ordering | page_size |
|----------|--------|--------|----------|-----------|
| GET /api/v1/assets/ | name, key, description | domain, status, visibility | name, key, created_at, updated_at | 50 default, max 100 |
| GET /api/v1/contracts/ | info.name, info.title | status, spec_type (ODPS/ODCS), owner_email, tag, etc. | created_at, updated_at, quality_score | 50 default, max 100 |
| GET /api/v1/datasets/ | file name, format | asset_id, dataset_format | created_at, updated_at, format | 50 default, max 100 |
| GET /api/v1/files/ | name | status | name, created_at, updated_at | 50 default, max 100 |

**Examples:**
```bash
GET /api/v1/assets/?search=report&status=ACTIVE
GET /api/v1/datasets/?asset_id=<uuid>&dataset_format=CSV&search=report
GET /api/v1/files/?search=report&status=ACTIVE
GET /api/v1/contracts/?spec_type=ODPS&status=ACTIVE
```

## Sorting

Most list endpoints support sorting:

```bash
GET /api/v1/contracts/?ordering=-created_at,name
```

See [API Standards](API_STANDARDS.md#sorting) for sorting syntax.

## SDKs

Official SDKs are available:

- **Python SDK**: See [Python SDK Documentation](SDK_PYTHON.md)
- **JavaScript SDK**: See [JavaScript SDK Documentation](SDK_JAVASCRIPT.md)
- **CLI Tool**: See [CLI Tool Documentation](CLI_TOOL.md)

## Examples

Example code is available in the `examples/` directory:

- `examples/api/` - API usage examples
- `examples/contracts/` - Contract examples

## Support

For API support:
- Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review [API Error Codes](API_ERROR_CODES.md)
- Consult [API Standards](API_STANDARDS.md)


---

# API Endpoints Reference

Complete reference for all API endpoints in the Data Interoperability Hub API v1.

## Standard Error Response Format

All API endpoints return errors in a consistent format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

**Status Codes:**
- `400 Bad Request`: Validation errors (code: `VALIDATION_ERROR` or `VALIDATION_FAILED`)
- `403 Forbidden`: Permission denied (code: `PERMISSION_DENIED` or `AUTH_FORBIDDEN`)
- `404 Not Found`: Resource not found (code: `NOT_FOUND`)
- `409 Conflict`: Resource conflict (code: `CONFLICT_ERROR` or `CONFLICT`)
- `429 Too Many Requests`: Rate limit exceeded (code: `RATE_LIMIT_EXCEEDED`)
- `500 Internal Server Error`: Server error (code: `INTERNAL_ERROR`)

**Error Response Fields:**
- `error` (string): Human-readable error message
- `code` (string): Machine-readable error code (e.g., `VALIDATION_ERROR`, `NOT_FOUND`)
- `details` (object): Optional dictionary with additional error context (field-level errors, validation details, etc.)

**Example Error Responses:**

```json
{
  "error": "Invalid request data",
  "code": "VALIDATION_ERROR",
  "details": {
    "field_errors": [
      {
        "field": "name",
        "message": "This field is required.",
        "code": "VALIDATION_ERROR"
      }
    ]
  }
}
```

```json
{
  "error": "Resource not found",
  "code": "NOT_FOUND",
  "details": {}
}
```

---

## Table of Contents

1. [Contracts](#contracts)
2. [Lineage](#lineage)
3. [Assets](#assets)
4. [Datasets](#datasets)
5. [Compliance](#compliance)
6. [Search](#search)
7. [Observability](#observability)
8. [Versioning](#versioning)
9. [Workflows](#workflows)
10. [Marketplace (listings and data preview)](#marketplace-listings-and-data-preview)
11. [Authentication](#authentication)
12. [Tenants (useronboardfix)](#tenants-useronboardfix)
13. [Billing (useronboardfix)](#billing-useronboardfix)
14. [Users (useronboardfix)](#users-useronboardfix)
15. [BaaS Platform Endpoints](#baas-platform-endpoints)
16. [ODH Integration Endpoints](#odh-integration-endpoints)
17. [Scheduled Ingestion](#scheduled-ingestion)
18. [Scheduled Ingestion Internal Worker API](#scheduled-ingestion-internal-worker-api)
19. [Scheduled Export](#scheduled-export)
20. [Scheduled Export Internal Worker API](#scheduled-export-internal-worker-api)

---

## Contracts

### List Contracts

**GET** `/api/v1/contracts/`

List all contracts with filtering, sorting, and pagination.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `ordering` (string): Sort fields (comma-separated, prefix with `-` for descending)
- `owner_email` (string): Filter by owner email (case-insensitive)
- `owner_name` (string): Filter by owner name (case-insensitive partial match)
- `tag` (string): Filter by tag (can specify multiple)
- `quality_profile` (string): Filter by quality profile key
- `compliance_regime` (string): Filter by compliance jurisdiction
- `contact_email` (string): Filter by contact email (case-insensitive)
- `contact_name` (string): Filter by contact name (case-insensitive partial match)
- `server_type` (string): Filter by server type
- `server_url` (string): Filter by server URL (case-insensitive partial match)
- `min_availability` (float): Filter by minimum availability SLA
- `max_latency_ms` (float): Filter by maximum latency SLA
- `model_name` (string): Filter by model name

**Response (200 OK):**
```json
{
  "count": 100,
  "page": 1,
  "page_size": 50,
  "total_pages": 2,
  "has_next": true,
  "has_previous": false,
  "next_page": 2,
  "previous_page": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "hub_contract_json": {
        "hub_contract_version": "1.0.0",
        "id": "contract-1",
        "info": {"name": "Contract 1"}
      },
      "status": "ACTIVE",
      "normalization_status": "NORMALIZED_OK",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Get Contract

**GET** `/api/v1/contracts/{id}/`

Retrieve a specific contract by ID.

**Path Parameters:**
- `id` (UUID): Contract UUID

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_contract_json": {
    "hub_contract_version": "1.0.0",
    "id": "contract-1",
    "info": {"name": "Contract 1"},
    "contact": [{"email": "support@example.com"}],
    "servers": [{"type": "s3", "url": "s3://bucket"}],
    "models": [{"name": "model1", "fields": []}]
  },
  "status": "ACTIVE",
  "normalization_status": "NORMALIZED_OK",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Create Contract

**POST** `/api/v1/contracts/`

Create a new contract from ODCS format.

**Request Body:**
```json
{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"contract-1\",\"name\":\"Contract 1\",\"schema\":{\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}}",
  "original_format": "JSON",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_contract_json": {...},
  "status": "ACTIVE",
  "normalization_status": "NORMALIZED_OK"
}
```

### Update Contract

**PATCH** `/api/v1/contracts/{id}/`

Update a contract (partial update supported).

**Request Body:**
```json
{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"contract-1\",\"name\":\"Updated Contract 1\",\"schema\":{\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}}"
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_contract_json": {...},
  "status": "ACTIVE"
}
```

### Delete Contract

**DELETE** `/api/v1/contracts/{id}/`

Delete a contract (soft delete: sets status to RETIRED).

**Response (204 No Content)**

---

## ODPS (Open Data Product Standard) Endpoints

### Create ODPS Product (Product-First Flow)

**POST** `/api/v1/contracts/products/`

Create an ODPS product contract using the Product-First flow. This automatically extracts an ODCS contract from the ODPS product.contract field and creates both contracts with bidirectional linking.

**Request Body:**
```json
{
  "original_raw": "ODPS document content (JSON or YAML string)",
  "original_format": "JSON" | "YAML",
  "resolve_external_refs": true,
  "asset_id": "optional-asset-uuid",
  "odps_version": "4.1"
}
```

**Request Body Fields:**
- `original_raw` (string, required): ODPS document content as JSON or YAML string
- `original_format` (string, required): Format of ODPS document - "JSON" or "YAML"
- `resolve_external_refs` (boolean, optional): Whether to resolve external $ref references (default: true)
- `asset_id` (UUID, optional): Asset ID to attach contracts to
- `odps_version` (string, optional): ODPS version (e.g., "4.1"). Used for validation/documentation. Version in document takes precedence

**Response (201 Created):**
```json
{
  "odps_contract": {
    "id": "odps-contract-uuid",
    "original_spec_type": "ODPS",
    "original_spec_version": "4.1",
    "status": "DRAFT",
    "normalization_status": "NORMALIZED_OK",
    "hub_contract_json": {...},
    "created_at": "2025-01-15T10:30:00Z"
  },
  "odcs_contract": {
    "id": "odcs-contract-uuid",
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2",
    "status": "DRAFT",
    "normalization_status": "NORMALIZED_OK",
    "hub_contract_json": {...},
    "created_at": "2025-01-15T10:30:00Z"
  },
  "workflow_instance_id": "workflow-instance-uuid"
}
```

**Example Request:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"my-product\",\"name\":\"My Data Product\"},\"contract\":{\"spec\":{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"my-contract\"}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Error Responses:**
- `400 Bad Request`: Invalid ODPS document or missing required fields
- `500 Internal Server Error`: Workflow execution failed

**Notes:**
- The Product-First flow automatically extracts the ODCS contract from `product.contract.spec` in the ODPS document
- Both contracts are created with bidirectional linking stored in `hub_contract_json.extensions.x_odps`
- The workflow instance ID can be used to track the creation process

---

## Export Endpoints

### Export Contract

**GET** `/api/v1/contracts/{id}/export/`

Export a contract in various formats (ODPS, ODCS, or HubContract).

**Path Parameters:**
- `id` (UUID): Contract UUID

**Query Parameters:**
- `format` (string, optional): Export format - `odps`, `odcs`, or `hubcontract` (default: `hubcontract`)
- `output_format` (string, optional): Output format - `json` or `yaml` (default: `json`)
- `version` (string, optional): ODPS version (e.g., `4.1`). Only used for ODPS format export (default: `4.1`)

**Response (200 OK):**

The response format depends on the requested format:

**HubContract Format (JSON):**
```json
{
  "hub_contract_version": "1.0.0",
  "id": "contract-1",
  "info": {"name": "Contract 1"},
  "schema": {"fields": [...]},
  ...
}
```

**HubContract Format (YAML):**
Content-Type: `application/x-yaml`
```
hub_contract_version: 1.0.0
id: contract-1
info:
  name: Contract 1
schema:
  fields: []
...
```

**ODPS Format (JSON):**
```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "marketplace": {
      "pricingPlans": [...]
    }
  }
}
```

**ODPS Format (YAML):**
Content-Type: `application/x-yaml`
```
schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      productID: customer-analytics
      name: Customer Analytics Dataset
  marketplace:
    pricingPlans: []
...
```

**ODCS Format (JSON):**
```json
{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "contract-1",
  "name": "Contract 1",
  "schema": {
    "fields": [...]
  }
}
```

**ODCS Format (YAML):**
Content-Type: `application/x-yaml`
```
apiVersion: odcs/v3
kind: DataContract
id: contract-1
name: Contract 1
schema:
  fields: []
...
```

**Example Requests:**
```bash
# Export as ODPS JSON
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export as ODPS YAML
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export as HubContract JSON
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=hubcontract&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `400 Bad Request`: Invalid format parameter or contract cannot be exported in requested format
- `404 Not Found`: Contract not found

**Notes:**
- ODPS export generates ODPS format from HubContract (may embed original ODCS if available)
- ODCS export prefers `original_raw` if available, otherwise attempts to generate from HubContract
- HubContract export returns the normalized `hub_contract_json` directly

### Download Contract

**GET** `/api/v1/contracts/{id}/download/`

Download a contract as a file in various formats. Similar to export but returns a downloadable file with appropriate Content-Disposition header.

**Path Parameters:**
- `id` (UUID): Contract UUID

**Query Parameters:**
- `format` (string, optional): Export format - `odps`, `odcs`, or `hubcontract` (default: `hubcontract`)
- `output_format` (string, optional): Output format - `json` or `yaml` (default: `json`)
- `version` (string, optional): ODPS version (e.g., `4.1`). Only used for ODPS format (default: `4.1`)

**Response (200 OK):**

Returns the contract content as a downloadable file with appropriate Content-Type and Content-Disposition headers.

**Example Request:**
```bash
# Download as ODPS JSON file
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.json

# Download as ODPS YAML file
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.yaml
```

**Error Responses:**
- `400 Bad Request`: Invalid format parameter or contract cannot be exported in requested format
- `404 Not Found`: Contract not found

**Notes:**
- Same format options as export endpoint
- Returns file with appropriate filename in Content-Disposition header
- Useful for downloading contracts for local storage or sharing

---

## Linking Endpoints

### Link ODPS to ODCS Contract

**POST** `/api/v1/contracts/{id}/link-odps/`

Link an ODPS contract to an ODCS contract. The contract specified by `{id}` must be an ODCS contract. You can either link to an existing ODPS contract or create a new one.

**Path Parameters:**
- `id` (UUID): ODCS contract UUID

**Request Body (Link to Existing ODPS):**
```json
{
  "odps_contract_id": "existing-odps-contract-uuid"
}
```

**Request Body (Create New ODPS and Link):**
```json
{
  "original_raw": "ODPS document content (JSON or YAML string)",
  "original_format": "JSON" | "YAML",
  "resolve_external_refs": true,
  "odps_version": "4.1"
}
```

**Request Body Fields:**
- `odps_contract_id` (UUID, optional): Existing ODPS contract ID to link to (mutually exclusive with `original_raw`)
- `original_raw` (string, optional): ODPS document content to create new ODPS contract (mutually exclusive with `odps_contract_id`)
- `original_format` (string, required if `original_raw` provided): Format of ODPS document - "JSON" or "YAML"
- `resolve_external_refs` (boolean, optional): Whether to resolve external $ref references (default: true, only used if `original_raw` provided)
- `odps_version` (string, optional): ODPS version (e.g., "4.1"). Only used if `original_raw` provided

**Response (200 OK):**
```json
{
  "id": "odps-contract-uuid",
  "original_spec_type": "ODPS",
  "original_spec_version": "4.1",
  "status": "DRAFT",
  "normalization_status": "NORMALIZED_OK",
  "hub_contract_json": {
    "extensions": {
      "x_odps": {
        "odcs_link": "odcs-contract-uuid"
      }
    }
  },
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Example Request (Link to Existing):**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-id}/link-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "odps_contract_id": "existing-odps-contract-uuid"
  }'
```

**Example Request (Create New and Link):**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-id}/link-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"linked-product\",\"name\":\"Linked Product\"}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Error Responses:**
- `400 Bad Request`: Contract is not ODCS type, invalid request body, or validation error
- `404 Not Found`: Contract or ODPS contract not found
- `500 Internal Server Error`: Linking operation failed

**Notes:**
- The contract specified by `{id}` must be an ODCS contract
- Bidirectional linking is automatically established in both contracts' `hub_contract_json.extensions.x_odps`
- If creating a new ODPS contract, it will be normalized and linked in a single operation

### Unlink ODPS from ODCS Contract

**POST** `/api/v1/contracts/{id}/unlink-odps/`

Remove the bidirectional link between an ODCS contract and its linked ODPS contract.

**Path Parameters:**
- `id` (UUID): ODCS contract UUID

**Response (200 OK):**
```json
{
  "message": "ODPS contract unlinked successfully"
}
```

**Example Request:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-id}/unlink-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `400 Bad Request`: Contract is not ODCS type or no link exists
- `404 Not Found`: Contract not found
- `500 Internal Server Error`: Unlinking operation failed

**Notes:**
- The contract specified by `{id}` must be an ODCS contract
- Removes the link from both the ODCS and ODPS contracts
- The contracts themselves are not deleted, only the link is removed

### List Contract Links

**GET** `/api/v1/contracts/{id}/links/`

Get all links for a contract (both ODPS and ODCS links).

**Path Parameters:**
- `id` (UUID): Contract UUID (can be ODPS or ODCS)

**Response (200 OK):**
```json
{
  "odps_link": {
    "id": "odps-contract-uuid",
    "original_spec_type": "ODPS",
    "original_spec_version": "4.1",
    "status": "DRAFT",
    "hub_contract_json": {...},
    ...
  },
  "odcs_link": null
}
```

**Response for ODPS Contract:**
```json
{
  "odps_link": null,
  "odcs_link": {
    "id": "odcs-contract-uuid",
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2",
    "status": "DRAFT",
    "hub_contract_json": {...},
    ...
  }
}
```

**Example Request:**
```bash
curl -X GET https://api.example.com/api/v1/contracts/{id}/links/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `404 Not Found`: Contract not found

**Notes:**
- Returns `null` for links that don't exist
- For ODCS contracts, returns the linked ODPS contract (if any)
- For ODPS contracts, returns the linked ODCS contract (if any)
- Both links are stored in `hub_contract_json.extensions.x_odps`

---

## Lineage

### Get Contract-Level Lineage

**GET** `/api/v1/contracts/{id}/lineage/contracts/`

Get contract-level lineage including contract references.

**Response (200 OK):**
```json
{
  "contracts": [
    {
      "namespace": "ns1",
      "name": "source-contract",
      "version": "1.0.0"
    }
  ],
  "entries": [
    {
      "input_fields": [...],
      "transformations": [...]
    }
  ]
}
```

### Get Model-Level Lineage

**GET** `/api/v1/contracts/{id}/models/{model_name}/lineage/`

Get lineage for a specific model.

**Path Parameters:**
- `id` (UUID): Contract UUID
- `model_name` (string): Model name

**Response (200 OK):**
```json
{
  "model_name": "customer",
  "lineage": {
    "models": [...],
    "entries": [...]
  }
}
```

### Get Field-Level Lineage

**GET** `/api/v1/contracts/{id}/fields/{field_name}/lineage/`

Get lineage for a specific field.

**Path Parameters:**
- `id` (UUID): Contract UUID
- `field_name` (string): Field name

**Response (200 OK):**
```json
{
  "field_name": "email",
  "model_name": "customer",
  "lineage": {
    "input_fields": [
      {
        "namespace": "ns1",
        "name": "source-contract",
        "model_name": "source-model",
        "field": "email_address"
      }
    ],
    "transformations": [
      {
        "logic": "LOWER(email_address)"
      }
    ]
  }
}
```

### Get Full Hierarchical Lineage

**GET** `/api/v1/contracts/{id}/lineage/full/`

Get complete hierarchical lineage (contract, model, and field levels).

**Query Parameters:**
- `max_contract_depth` (integer): Maximum contract depth (default: 10)
- `max_model_depth` (integer): Maximum model depth (default: 10)
- `max_field_depth` (integer): Maximum field depth (default: 10)

**Response (200 OK):**
```json
{
  "upstream": {...},
  "downstream": {...}
}
```

### Get Lineage Visualization

**GET** `/api/v1/contracts/{id}/lineage/visualization/`

Get lineage graph in various visualization formats.

**Query Parameters:**
- `format` (string): Visualization format - `json`, `dot`, or `mermaid` (default: `json`)

**Response (200 OK):**
- JSON format: JSON object for D3.js
- DOT format: Text string for Graphviz
- Mermaid format: Text string for Mermaid

---

## Assets

### List Assets

**GET** `/api/v1/assets/`

List all assets with filtering and pagination.

**Query Parameters:**
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `status` (string): Filter by status
- `type` (string): Filter by asset type

**Response (200 OK):**
```json
{
  "count": 50,
  "results": [...]
}
```

### Get Asset

**GET** `/api/v1/assets/{id}/`

Retrieve a specific asset by ID.

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Asset 1",
  "type": "DATASET",
  "status": "ACTIVE"
}
```

---

## Datasets

### List Datasets

**GET** `/api/v1/datasets/`

List all datasets with filtering and pagination.

**Response (200 OK):**
```json
{
  "count": 50,
  "results": [...]
}
```

### Get Dataset

**GET** `/api/v1/datasets/{id}/`

Retrieve a specific dataset by ID.

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Dataset 1",
  "status": "ACTIVE"
}
```

---

## Search

### Search

**GET** `/api/v1/search/`

Full-text search across contracts and assets.

**Query Parameters:**
- `q` (string): Search query string
- `type` (string): Filter by type (contract, asset, dataset)
- `classification` (string): Filter by data classification
- `owner` (string): Filter by owner
- `tags` (string): Filter by tags
- `domain` (string): Filter by domain
- `quality_status` (string): Filter by quality status
- `compliance_status` (string): Filter by compliance status
- `limit` (integer): Maximum results (default: 50)
- `offset` (integer): Result offset (default: 0)
- `sort_by` (string): Sort field (default: relevance)
- `sort_order` (string): Sort order - `asc` or `desc` (default: desc)

**Response (200 OK):**
```json
{
  "count": 10,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "contract",
      "name": "Contract 1",
      "relevance_score": 0.95
    }
  ]
}
```

### Search Suggestions

**GET** `/api/v1/search/suggestions/`

Get search suggestions/autocomplete.

**Query Parameters:**
- `q` (string): Search query string
- `limit` (integer): Maximum suggestions (default: 10)

**Response (200 OK):**
```json
{
  "suggestions": [
    "customer data",
    "customer analytics",
    "customer profile"
  ]
}
```

---

## Compliance

### List Compliance Runs

**GET** `/api/v1/compliance/runs/`

List all compliance runs with filtering, sorting, and pagination.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `ordering` (string): Sort fields (comma-separated, prefix with `-` for descending)
- `asset_id` (UUID): Filter by asset ID
- `dataset_id` (UUID): Filter by dataset ID
- `file_id` (UUID): Filter by file ID
- `status` (string): Filter by status (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`)
- `scan_mode` (string): Filter by scan mode (`internal`, `external`)
- `limit` (integer): Maximum number of results (alternative to pagination)
- `offset` (integer): Number of results to skip (alternative to pagination)

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "http://localhost:8000/api/v1/compliance/runs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "asset_id": "660e8400-e29b-41d4-a716-446655440001",
      "dataset_id": null,
      "file_id": null,
      "status": "SUCCEEDED",
      "scan_mode": "internal",
      "overall_status": "PASS",
      "risk_level": "LOW",
      "allowed_to_store": true,
      "regulations": ["GDPR", "LGPD"],
      "created_at": "2025-01-15T10:30:00Z",
      "started_at": "2025-01-15T10:30:05Z",
      "completed_at": "2025-01-15T10:35:00Z",
      "job": {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "status": "COMPLETED"
      }
    }
  ]
}
```

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/compliance/runs/?asset_id=660e8400-e29b-41d4-a716-446655440001&status=SUCCEEDED" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions

### Create Compliance Run

**POST** `/api/v1/compliance/runs/`

Create a new compliance run for an asset, dataset, or file.

**Request Body:**
```json
{
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": "770e8400-e29b-41d4-a716-446655440003",
  "file_id": "880e8400-e29b-41d4-a716-446655440004",
  "scan_mode": "internal",
  "applicable_regulations": ["GDPR", "HIPAA"]
}
```

**Request Body Parameters:**
- `asset_id` (UUID, optional): Asset ID to scan
- `dataset_id` (UUID, optional): Dataset ID to scan
- `file_id` (UUID, optional): File ID to scan (scan-only mode)
- `scan_mode` (string, required): Scan mode - `internal` (full scan) or `external` (scan-only)
- `applicable_regulations` (array of strings, optional): List of regulations to check (e.g., `["GDPR", "HIPAA", "LGPD", "CCPA", "SOX"]`)

**Note:** At least one of `asset_id`, `dataset_id`, or `file_id` must be provided.

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": null,
  "file_id": null,
  "status": "PENDING",
  "scan_mode": "internal",
  "regulations": ["GDPR", "LGPD"],
  "created_at": "2025-01-15T10:30:00Z",
  "job": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "status": "PENDING"
  }
}
```

**Example Request:**
```bash
curl -X POST "https://api.example.com/api/v1/compliance/runs/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "660e8400-e29b-41d4-a716-446655440001",
    "scan_mode": "internal",
    "applicable_regulations": ["GDPR", "HIPAA"]
  }'
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or missing required fields
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Asset, dataset, or file not found

### Get Compliance Run

**GET** `/api/v1/compliance/runs/{id}/`

Retrieve a specific compliance run by ID.

**Path Parameters:**
- `id` (UUID): Compliance run UUID

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": null,
  "file_id": null,
  "status": "SUCCEEDED",
  "scan_mode": "internal",
  "overall_status": "PASS",
  "risk_level": "LOW",
  "allowed_to_store": true,
  "regulations": ["GDPR", "LGPD"],
  "detected_categories_json": {
    "EMAIL": 10,
    "PHONE": 5,
    "SSN": 2
  },
  "column_findings_json": [
    {
      "column": "email",
      "category": "EMAIL",
      "risk_level": "LOW"
    }
  ],
  "regulation_mapping_json": {
    "GDPR": {
      "status": "COMPLIANT",
      "violations": []
    }
  },
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:05Z",
  "completed_at": "2025-01-15T10:35:00Z",
  "job": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "status": "COMPLETED",
    "started_at": "2025-01-15T10:30:05Z",
    "completed_at": "2025-01-15T10:35:00Z"
  }
}
```

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/compliance/runs/550e8400-e29b-41d4-a716-446655440000/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Compliance run not found

### Get Compliance Run Results

**GET** `/api/v1/compliance/runs/{id}/results/`

Get detailed compliance scan results for a completed compliance run.

**Path Parameters:**
- `id` (UUID): Compliance run UUID

**Response (200 OK):**
```json
{
  "compliance_run_id": "550e8400-e29b-41d4-a716-446655440000",
  "overall_status": "PASS",
  "risk_level": "LOW",
  "allowed_to_store": true,
  "detected_categories": {
    "EMAIL": 10,
    "PHONE": 5,
    "SSN": 2
  },
  "column_findings": [
    {
      "column": "email",
      "category": "EMAIL",
      "risk_level": "LOW",
      "confidence": 0.95
    },
    {
      "column": "phone_number",
      "category": "PHONE",
      "risk_level": "MEDIUM",
      "confidence": 0.87
    }
  ],
  "regulation_mapping": {
    "GDPR": {
      "status": "COMPLIANT",
      "violations": [],
      "requirements_met": 15,
      "requirements_total": 15
    },
    "HIPAA": {
      "status": "COMPLIANT",
      "violations": [],
      "requirements_met": 12,
      "requirements_total": 12
    }
  },
  "metadata": {
    "scan_duration_seconds": 295.5,
    "rows_scanned": 100000,
    "columns_scanned": 25
  }
}
```

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/compliance/runs/550e8400-e29b-41d4-a716-446655440000/results/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `400 Bad Request`: Compliance run not completed yet
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Compliance run not found

**Notes:**
- Results are only available for completed compliance runs (`status` = `SUCCEEDED` or `FAILED`)
- For runs with `status` = `PENDING` or `RUNNING`, this endpoint returns `400 Bad Request`
- Results include detailed PII detection, risk assessment, and regulatory compliance mapping

---

## Observability

### Get Freshness Metrics

**GET** `/api/v1/observability/freshness/`

Get data freshness monitoring metrics.

**Query Parameters:**
- `dataset_id` (UUID): Filter by dataset ID
- `start_date` (datetime): Start date for metrics
- `end_date` (datetime): End date for metrics

**Response (200 OK):**
```json
{
  "metrics": [
    {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "last_update": "2025-01-15T10:30:00Z",
      "freshness_age_hours": 2.5,
      "is_stale": false
    }
  ]
}
```

### Get Volume Metrics

**GET** `/api/v1/observability/volume/`

Get data volume monitoring metrics.

**Response (200 OK):**
```json
{
  "metrics": [
    {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "row_count": 1000000,
      "size_bytes": 1073741824,
      "timestamp": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Get Lineage

**GET** `/api/v1/observability/lineage/`

Get contract-level lineage (delegates to contract lineage service; tenant isolation enforced).

**Query Parameters:**
- `contract_id` (UUID, required): Contract UUID to retrieve lineage for.

**Response (200 OK):**
```json
{
  "contracts": [
    { "namespace": "ns1", "name": "upstream-contract", "id": "up-1" }
  ],
  "entries": [
    { "type": "derived", "source": "up-1", "target": "self" }
  ]
}
```

**Response (400 Bad Request)** — missing `contract_id`, invalid UUID format, or user has no tenant:
```json
{ "error": "contract_id query parameter is required" }
```
or (invalid UUID format for `contract_id`):
```json
{ "error": "Invalid UUID format for contract_id", "code": "INVALID_UUID" }
```
or (user has no tenant):
```json
{ "error": "User must belong to a tenant to view observability data" }
```

**Response (404 Not Found)** — contract not found or not accessible (e.g. different tenant):
```json
{ "error": "Contract not found", "code": "NOT_FOUND" }
```

---

### Get Schema Drift

**GET** `/api/v1/observability/schema-drift/`

Get schema drift detection results.

**Response (200 OK):**
```json
{
  "drifts": [
    {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "detected_at": "2025-01-15T10:30:00Z",
      "changes": [
        {
          "type": "field_added",
          "field": "new_field",
          "field_type": "string"
        }
      ]
    }
  ]
}
```

---

## Versioning

Minimal Versioning API for listing and comparing contract and dataset versions (Phase 2 Gap Remediation). All endpoints require authentication and are tenant-scoped.

### List Versions

**GET** `/api/v1/versioning/versions/`

List versions for a resource (contract or dataset) by asset id.

**Query Parameters:**
- `resource_type` (string, required): `contract` or `dataset`
- `resource_id` (UUID, required): Asset UUID

**Response (200 OK):**
```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "resource_type": "contract",
      "version": 2,
      "semantic_version": "3.0.2",
      "created_at": "2025-01-15T10:00:00Z",
      "is_current": null
    }
  ]
}
```

**Error Responses:**
- `400`: Missing or invalid `resource_type` / `resource_id`; user without tenant
- `401`: Unauthenticated

### Get Version

**GET** `/api/v1/versioning/versions/{id}/`

Retrieve a single version (contract or dataset) by id.

**Response (200 OK):** Object with `id`, `resource_type`, `version`, `semantic_version`, `created_at`, `updated_at`, `is_current`, and optionally `status`, `original_spec_version`.

**Error Responses:**
- `404`: Version not found or not in tenant
- `401`: Unauthenticated

### Compare Versions

**GET** `/api/v1/versioning/compare/`

Compare two versions (same resource type).

**Query Parameters:**
- `resource_type` (string, required): `contract` or `dataset`
- `id_a` (UUID, required): First version id
- `id_b` (UUID, required): Second version id

**Response (200 OK):**
```json
{
  "id_a": "550e8400-e29b-41d4-a716-446655440001",
  "id_b": "550e8400-e29b-41d4-a716-446655440002",
  "resource_type": "contract",
  "version_a": 1,
  "version_b": 2,
  "created_at_a": "2025-01-15T10:00:00Z",
  "created_at_b": "2025-01-16T11:00:00Z"
}
```

**Error Responses:**
- `400`: Missing `id_a` / `id_b` or invalid `resource_type`
- `404`: One or both versions not found or not in tenant
- `401`: Unauthenticated

---

## Workflows

Workflow definitions and trigger (create/start instance). Tenant required; tenant isolation enforced on trigger.

### List Workflows

**GET** `/api/v1/workflows/`

List workflow definitions with optional filters and pagination.

**Query Parameters:**
- `name` (string, optional): Filter by workflow name
- `is_active` (boolean, optional): Filter by active status (`true`/`false`)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Page size (default: 50, max: 100)

**Response (200 OK):**
```json
{
  "count": 11,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "version_creation",
      "version": "1.0.0",
      "description": null,
      "is_active": true,
      "dependencies": [],
      "metadata": {},
      "created_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

**Response (400 Bad Request)** — user has no tenant:
```json
{ "error": "User must belong to a tenant to access the Workflows API" }
```

**Response (401 Unauthorized)** — not authenticated.

---

### Get Workflow

**GET** `/api/v1/workflows/{name}/`

Get a workflow definition by name. Optional query `version` for a specific version.

**Query Parameters:**
- `version` (string, optional): Workflow version (e.g. `1.0.0`). If omitted, returns the active version.

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "version_creation",
  "version": "1.0.0",
  "description": null,
  "dsl_json": { "version": "1.0.0", "steps": [...] },
  "is_active": true,
  "dependencies": [],
  "metadata": {},
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

**Response (404 Not Found)** — workflow not found:
```json
{ "error": "Workflow not found: {name}", "code": "NOT_FOUND" }
```

---

### Trigger Workflow

**POST** `/api/v1/workflows/{name}/trigger/`

Create a new workflow instance (and optionally start it immediately). Instance is created for the authenticated user's tenant.

**Request Body:**
```json
{
  "input_data": {},
  "start_immediately": false
}
```
- `input_data` (object, optional): Workflow input data; must be a JSON object (default: `{}`)
- `start_immediately` (boolean, optional): If `true`, start the instance after creation (default: `false`)

**Response (201 Created):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "DRAFT",
  "workflow_name": "version_creation",
  "workflow_version": "1.0.0",
  "created_at": "2025-01-15T11:00:00Z"
}
```
When `start_immediately` was `true`, the response may include:
- `started` (boolean): `true` if start succeeded, `false` if start failed
- `start_error` (string, optional): Error message if start was requested but failed (instance remains in DRAFT)

**Response (404 Not Found)** — workflow definition not found:
```json
{ "error": "Workflow definition not found: {name}", "code": "WORKFLOW_NOT_FOUND" }
```

**Response (400 Bad Request)** — user has no tenant, invalid body (e.g. `input_data` not a JSON object), or validation errors.

---

## Marketplace (listings and data preview)

Listings and orders are under `/api/v1/marketplace/`. Data preview is available for published listings (Phase 4 Gap Remediation).

### Data preview (listing)

**GET** `/api/v1/marketplace/listings/{id}/preview/`

Preview sample data, schema, and quality metrics for a **published** listing before purchase. Requires authentication.

**Path Parameters:**
- `id` (UUID): Listing ID.

**Response (200 OK):**
```json
{
  "listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "sample_data": {
    "rows": [ { "id": "1", "name": "test1", "value": 100 } ],
    "total_rows": 1000,
    "sample_size": 10
  },
  "quality_metrics": {
    "completeness": 0.95,
    "accuracy": 1.0,
    "freshness": "current",
    "overall_score": 0.95
  },
  "schema": {
    "fields": [
      { "name": "id", "type": "string", "nullable": false },
      { "name": "name", "type": "string", "nullable": false }
    ]
  },
  "trust_signals": { "badges": ["quality_verified"], "quality_sla": "99.5%" },
  "preview_expires_at": "2025-01-15T12:00:00Z"
}
```
- `quality_metrics`: From latest successful DQ run for the asset (null if none).
- `trust_signals`: Optional; from listing `metadata_json.trust_signals` when set.
- `preview_expires_at`: Preview validity (e.g. 1 hour).

**Response (403 Forbidden)** — listing not published:
```json
{ "error": "Preview is only available for published listings" }
```

**Response (400 Bad Request)** — listing has no associated asset (defensive; normal listings always have an asset):
```json
{ "error": "Listing has no associated asset" }
```

**Response (404 Not Found)** — no dataset for the listing's asset:
```json
{ "error": "No dataset found for this asset" }
```

**Response (401 Unauthorized)** — not authenticated.

### Trust signals configuration API

Tenant-scoped CRUD for trust signal definitions (badges, quality SLAs). Supports UC-MKT-ADV-003 (Manage Trust Signals) and UC-MKT-ADV-005 (Configure Data Quality SLAs). Requires authentication; list/retrieve/update/delete are filtered by the request tenant.

**Base path:** `/api/v1/marketplace/config/trust-signals/`

#### List trust signal configs

**GET** `/api/v1/marketplace/config/trust-signals/`

Returns trust signal configs for the current tenant (paginated). Platform admins see all.

**Response (200 OK):** Paginated list of objects: `id`, `tenant_id`, `name`, `kind` (`badge` | `quality_sla`), `config` (JSON), `is_active`, `created_at`, `updated_at`.

#### Create trust signal config

**POST** `/api/v1/marketplace/config/trust-signals/`

**Request Body:**
```json
{
  "name": "quality_verified",
  "kind": "badge",
  "config": { "description": "Quality verified by DQ run" }
}
```
- `name`: string, unique per tenant
- `kind`: `badge` or `quality_sla`
- `config`: JSON object (e.g. `description` for badge; `availability`, `freshness_hours` for quality_sla)
- `is_active`: optional boolean, default true

**Response (201 Created):** Created object with `id`, `tenant_id`, `name`, `kind`, `config`, `is_active`, `created_at`, `updated_at`.

**Response (400 Bad Request):** Validation error (e.g. missing name/kind). Duplicate name per tenant returns `{"error": "A trust signal config with this name already exists for your tenant.", "code": "DUPLICATE_NAME"}`.

#### Retrieve trust signal config

**GET** `/api/v1/marketplace/config/trust-signals/{id}/`

**Response (200 OK):** Single config object. **Response (404 Not Found):** Config not found or belongs to another tenant.

#### Update trust signal config

**PUT** `/api/v1/marketplace/config/trust-signals/{id}/`  
**PATCH** `/api/v1/marketplace/config/trust-signals/{id}/`

**Response (200 OK):** Updated object. **Response (400 Bad Request):** Duplicate name (same as create; `code`: `DUPLICATE_NAME`). **Response (404 Not Found):** Config not found or belongs to another tenant.

#### Delete trust signal config

**DELETE** `/api/v1/marketplace/config/trust-signals/{id}/`

**Response (204 No Content):** Deleted. **Response (404 Not Found):** Config not found or belongs to another tenant.

**Response (401 Unauthorized):** Not authenticated.

See [FEATURES.md – Trust signals](FEATURES.md#trust-signals).

---

## Authentication

### Login

**POST** `/api/v1/auth/login/`

Authenticate user and get access token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Refresh Token

**POST** `/api/v1/auth/refresh/`

Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Get Current User / Update Profile (useronboardfix Phase 7)

**GET** `/api/v1/auth/me/` — Returns current user: `id`, `email`, `name`, `tenant_id`, `roles`, `permissions`, `avatar`, `preferences`, `feature_tenant_switch_enabled`.

**PATCH** `/api/v1/auth/me/` — Partial update. Request body: `{"display_name": "…", "avatar": "…", "preferences": {"theme": "dark"}}`. All fields optional. Requires authentication.

See [API_REFERENCE.md](API_REFERENCE.md#user-profile) for full details.

### List My Tenants (Tenant Switch)

**GET** `/api/v1/auth/me/tenants/`

Returns list of tenants the current user has membership in (from UserTenantMembership). Used for tenant switcher UI.

**Authentication**: Required (JWT token or session)

**Response (200 OK):**
```json
[
  { "id": "uuid", "name": "Tenant A", "slug": "tenant-a" },
  { "id": "uuid", "name": "Tenant B", "slug": "tenant-b" }
]
```

**Response (403 Forbidden):** Feature disabled (`FEATURE_TENANT_SWITCH_ENABLED=false`) or user not authenticated.

### Switch Tenant

**POST** `/api/v1/auth/switch-tenant/`

Switch active tenant context. Validates user has membership in target tenant; returns updated me summary with `tenant_id` overridden.

**Authentication**: Required (JWT token or session)

**Request Body:**
```json
{
  "tenant_id": "uuid-of-target-tenant"
}
```

**Response (200 OK):** Same shape as GET /auth/me/ with `tenant_id` set to the switched tenant.

**Response (400 Bad Request):** Missing or invalid `tenant_id` (not a valid UUID).

**Response (403 Forbidden):** Feature disabled, or user has no membership in target tenant.

**Response (404 Not Found):** Tenant not found.

**Note:** After switching, clients should send `X-Tenant-Id: <tenant_id>` on subsequent requests to scope operations to the switched tenant. See [TENANT_SWITCH_PLAN.md](TENANT_SWITCH_PLAN.md).

---

## Tenants (useronboardfix)

### Get Tenant Usage

**GET** `/api/v1/tenants/me/usage/`

Returns current tenant usage (storage, API calls, limits). Requires TENANT_ADMIN or PLATFORM_ADMIN.

**Response (200 OK):**
```json
{
  "storage_bytes": 1073741824,
  "api_calls_count": 1500,
  "limits": {"storage_bytes": 5368709120, "api_calls_per_month": 10000}
}
```

### Get / Update Tenant Config

**GET** `/api/v1/tenants/me/config/` — Returns tenant configuration (trust signals, versioning, workflows, default_dq_profile, etc.).

**PATCH** `/api/v1/tenants/me/config/` — Update tenant configuration. Request body: partial config object. Requires TENANT_ADMIN or PLATFORM_ADMIN.

---

## Billing (useronboardfix)

### Get Current Subscription

**GET** `/api/v1/billing/subscription/current/` — Returns current subscription (plan, status, limits). See [BILLING.md](BILLING.md).

### Change Subscription Plan

**POST** `/api/v1/billing/subscription/current/change-plan/` — Body: `{"plan_slug": "pro"}`. Requires TENANT_ADMIN or PLATFORM_ADMIN. Runbook: [Subscription plan change failures](RUNBOOKS.md#subscription-plan-change-failures).

### List Plans / Invoices

**GET** `/api/v1/billing/plans/` — List available plans for subscription change.

**GET** `/api/v1/billing/invoices/` — List invoices for tenant.

**GET** `/api/v1/billing/invoices/{id}/` — Get invoice detail.

**GET** `/api/v1/billing/invoices/{id}/download/` — Redirect to invoice PDF or hosted URL.

See [BILLING.md](BILLING.md) for full documentation.

---

## Users (useronboardfix)

### Update User (Admin Edit)

**PUT** `/api/v1/users/{id}/` — Update user (roles, status). Requires TENANT_ADMIN or PLATFORM_ADMIN. Tenant-scoped: tenant admin can only edit users in their tenant.

---

## Marketplace Integration Endpoints

### List Marketplace Connections

**GET** `/api/v1/integrations/marketplace/connections/`

List all marketplace connections for the authenticated user's tenant with filtering, pagination, and search.

**Query Parameters:**
- `marketplace_type` (string, optional): Filter by marketplace type (e.g., `SNOWFLAKE_DATA_MARKETPLACE`, `AWS_DATA_EXCHANGE`)
- `is_active` (boolean, optional): Filter by active status (`true`/`false`)
- `search` (string, optional): Search in connection name
- `ordering` (string, optional): Order by field (e.g., `name`, `-created_at`). Prefix with `-` for descending
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Authentication**: Required (JWT token or API key)

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "count": 10,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "has_next": false,
  "has_previous": false,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Snowflake Production",
      "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
      "is_active": true,
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

**Rate Limiting**: 100 requests per hour per user

### Get Marketplace Connection

**GET** `/api/v1/integrations/marketplace/connections/{id}/`

Get detailed information about a specific marketplace connection.

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Snowflake Production",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Connection not found
- `403 Forbidden`: Insufficient permissions

### Create Marketplace Connection

**POST** `/api/v1/integrations/marketplace/connections/`

Create a new marketplace connection.

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body:**
```json
{
  "name": "Snowflake Production",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "config": {
    "account": "myaccount",
    "username": "user",
    "password": "password",
    "warehouse": "COMPUTE_WH",
    "database": "MARKETPLACE_DB"
  }
}
```

**Request Body Fields:**
- `name` (string, required): Connection name
- `marketplace_type` (string, required): Marketplace type (e.g., `SNOWFLAKE_DATA_MARKETPLACE`, `AWS_DATA_EXCHANGE`)
- `config` (object, required): Marketplace-specific configuration (credentials, endpoints, etc.)

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Snowflake Production",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or validation error
- `403 Forbidden`: Insufficient permissions
- `429 Too Many Requests`: Rate limit exceeded

**Rate Limiting**: 10 requests per hour per user

### Update Marketplace Connection

**PATCH** `/api/v1/integrations/marketplace/connections/{id}/`

Update a marketplace connection (partial update supported).

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body:**
```json
{
  "name": "Snowflake Production Updated",
  "config": {
    "warehouse": "NEW_COMPUTE_WH"
  }
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Snowflake Production Updated",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "is_active": true,
  "updated_at": "2025-01-15T11:00:00Z"
}
```

**Rate Limiting**: 20 requests per hour per user

### Delete Marketplace Connection

**DELETE** `/api/v1/integrations/marketplace/connections/{id}/`

Delete a marketplace connection.

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Response (204 No Content)**

**Rate Limiting**: 10 requests per hour per user

### Test Marketplace Connection

**POST** `/api/v1/integrations/marketplace/connections/{id}/test/`

Test a marketplace connection to verify credentials and connectivity.

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Connection test successful",
  "tested_at": "2025-01-15T10:35:00Z",
  "details": {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "response_time_ms": 245
  }
}
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "message": "Connection test failed: Invalid credentials",
  "tested_at": "2025-01-15T10:35:00Z",
  "error": "Authentication failed"
}
```

**Rate Limiting**: 20 requests per hour per user

---

### List Marketplace Sync Jobs

**GET** `/api/v1/integrations/marketplace/sync/`

List all marketplace sync jobs for the authenticated user's tenant.

**Query Parameters:**
- `connection_id` (UUID, optional): Filter by connection ID
- `direction` (string, optional): Filter by sync direction (`PUSH`, `PULL`, `BIDIRECTIONAL`)
- `status` (string, optional): Filter by status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`, `CANCELLED`)
- `ordering` (string, optional): Order by field (e.g., `-created_at`)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "count": 25,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "connection": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Snowflake Production",
        "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
      },
      "direction": "PULL",
      "status": "COMPLETED",
      "items_synced": 100,
      "items_failed": 0,
      "created_at": "2025-01-15T10:00:00Z",
      "completed_at": "2025-01-15T10:05:00Z"
    }
  ]
}
```

**Rate Limiting**: 100 requests per hour per user

### Get Marketplace Sync Job

**GET** `/api/v1/integrations/marketplace/sync/{id}/`

Get detailed information about a specific marketplace sync job.

**Path Parameters:**
- `id` (UUID): Sync job UUID

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "COMPLETED",
  "items_synced": 100,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "data_strategy": "METADATA_ONLY",
    "filters": {},
    "options": {}
  },
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:05:00Z",
  "completed_at": "2025-01-15T10:05:00Z"
}
```

### Create Marketplace Sync Job

**POST** `/api/v1/integrations/marketplace/sync/`

Create a new marketplace sync job.

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body (PULL sync):**
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "listing_ids": null,
  "filters": {
    "category": "health"
  },
  "options": {
    "dry_run": false,
    "data_strategy": "METADATA_ONLY"
  }
}
```

**Request Body (PUSH sync):**
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "asset_ids": [
    "770e8400-e29b-41d4-a716-446655440000",
    "880e8400-e29b-41d4-a716-446655440000"
  ],
  "options": {
    "dry_run": false
  }
}
```

**Request Body Fields:**
- `connection_id` (UUID, required): Connection UUID
- `direction` (string, required): Sync direction (`PUSH`, `PULL`, or `BIDIRECTIONAL`)
- `asset_ids` (array of UUIDs, optional): Hub asset IDs for PUSH sync
- `listing_ids` (array of strings, optional): External listing IDs for PULL sync
- `filters` (object, optional): Filters for PULL sync
- `options` (object, optional): Sync options (dry_run, data_strategy, etc.)

**Response (201 Created):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "data_strategy": "METADATA_ONLY",
    "filters": {
      "category": "health"
    },
    "options": {
      "dry_run": false
    }
  },
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z",
  "completed_at": null
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or validation error
- `404 Not Found`: Connection not found
- `429 Too Many Requests`: Rate limit exceeded

**Rate Limiting**: 10 requests per hour per user

**Note**: Sync jobs are executed asynchronously. Use the GET endpoint to monitor progress.

### Cancel Marketplace Sync Job

**POST** `/api/v1/integrations/marketplace/sync/{id}/cancel/`

Cancel a running marketplace sync job.

**Path Parameters:**
- `id` (UUID): Sync job UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body:**
```json
{
  "reason": "User requested cancellation"
}
```

**Response (200 OK):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "CANCELLED",
  "metadata": {
    "cancellation_reason": "User requested cancellation"
  },
  "updated_at": "2025-01-15T10:03:00Z",
  "completed_at": "2025-01-15T10:03:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Job cannot be cancelled (already completed/failed/cancelled)
- `404 Not Found`: Sync job not found

**Rate Limiting**: 20 requests per hour per user

---

### List Marketplace Mappings

**GET** `/api/v1/integrations/marketplace/mappings/`

List all marketplace mappings for the authenticated user's tenant.

**Query Parameters:**
- `connection_id` (UUID, optional): Filter by connection ID
- `hub_asset_id` (UUID, optional): Filter by hub asset ID
- `external_listing_id` (string, optional): Filter by external listing ID
- `ordering` (string, optional): Order by field (e.g., `-created_at`)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "count": 50,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "connection": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Snowflake Production",
        "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
      },
      "hub_asset": {
        "id": "880e8400-e29b-41d4-a716-446655440000",
        "name": "Customer Analytics Dataset"
      },
      "external_listing_id": "SNOWFLAKE_LISTING_123",
      "created_at": "2025-01-15T10:00:00Z",
      "last_synced_at": "2025-01-15T10:05:00Z"
    }
  ]
}
```

**Rate Limiting**: 100 requests per hour per user

### Get Marketplace Mapping

**GET** `/api/v1/integrations/marketplace/mappings/{id}/`

Get detailed information about a specific marketplace mapping.

**Path Parameters:**
- `id` (UUID): Mapping UUID

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "hub_asset": {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "name": "Customer Analytics Dataset"
  },
  "external_listing_id": "SNOWFLAKE_LISTING_123",
  "external_resource_ids": ["resource1", "resource2"],
  "sync_metadata": {
    "last_sync_status": "SUCCESS",
    "last_sync_errors": []
  },
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:05:00Z",
  "last_synced_at": "2025-01-15T10:05:00Z"
}
```

### Delete Marketplace Mapping

**DELETE** `/api/v1/integrations/marketplace/mappings/{id}/`

Delete a marketplace mapping.

**Path Parameters:**
- `id` (UUID): Mapping UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Response (204 No Content)**

**Rate Limiting**: 20 requests per hour per user

---

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "field_name",
          "message": "Field-specific error",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

See [API Error Codes](./API_ERROR_CODES.md) for complete error code reference.

---

## Additional Resources

- [API Best Practices](./API_BEST_PRACTICES.md)
- [API Error Codes](./API_ERROR_CODES.md)
- [Marketplace API Reference](./MARKETPLACE_API_REFERENCE.md) - Complete marketplace API documentation
- [Interactive Documentation](../api-docs/)
- [OpenAPI Schema](../api-docs/openapi.json)
- [Scheduled Ingestion API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_INGESTION.md) - Complete scheduled ingestion API documentation (public and internal worker API)
- [Scheduled Export API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_EXPORT.md) - Complete scheduled export API documentation (public and internal worker API)


---

# Scheduled Export API Endpoints Reference

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Overview

The Scheduled Export API provides endpoints for managing scheduled data export workflows. The API includes:

- **Public API**: Endpoints for creating, managing, and monitoring scheduled exports (tenant-scoped)
- **Internal Worker API**: Endpoints used exclusively by Prefect workers for execution (worker-authenticated)

---

## Scheduled Export (Public API)

### List Scheduled Exports

**GET** `/api/v1/scheduled-exports/`

List all scheduled exports for the authenticated tenant.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `status` (string): Filter by status (`ACTIVE`, `PAUSED`, `ERROR`)

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped (users can only access their tenant's exports)

**Rate Limiting**: Per tenant/user limits (see [Rate Limiting](#rate-limiting))

**Response (200 OK):**
```json
{
  "count": 10,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Daily Sales Export",
      "destination_type": "S3",
      "destination_config": {
        "bucket": "export-bucket",
        "prefix": "exports/sales/"
      },
      "schedule_config": {
        "cron": "0 2 * * *"
      },
      "source_scope": {
        "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"]
      },
      "status": "ACTIVE",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### Create Scheduled Export

**POST** `/api/v1/scheduled-exports/`

Create a new scheduled export.

**Request Body:**
```json
{
  "name": "Daily Sales Export",
  "schedule_config": {
    "cron": "0 2 * * *"
  },
  "destination_type": "S3",
  "destination_config": {
    "bucket": "export-bucket",
    "prefix": "exports/sales/",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  },
  "source_scope": {
    "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"],
    "dataset_ids": [],
    "file_ids": [],
    "contract_id": null
  },
  "status": "ACTIVE"
}
```

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Export",
  "destination_type": "S3",
  "status": "ACTIVE",
  "created_at": "2026-01-15T10:00:00Z"
}
```

### Get Scheduled Export

**GET** `/api/v1/scheduled-exports/{id}/`

Get details of a specific scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Export",
  "destination_type": "S3",
  "destination_config": {
    "bucket": "export-bucket",
    "prefix": "exports/sales/"
  },
  "schedule_config": {
    "cron": "0 2 * * *"
  },
  "source_scope": {
    "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"]
  },
  "status": "ACTIVE",
  "next_run_at": "2026-02-04T02:00:00Z",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### Update Scheduled Export

**PUT** `/api/v1/scheduled-exports/{id}/`

Update a scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Request Body:** Same as create, all fields optional

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):** Updated scheduled export object

### Delete Scheduled Export

**DELETE** `/api/v1/scheduled-exports/{id}/`

Delete a scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (204 No Content)**

### Trigger Scheduled Export

**POST** `/api/v1/scheduled-exports/{id}/trigger/`

Manually trigger a scheduled export run.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Request Body (optional):**
```json
{
  "override_config": {
    "destination_config": {
      "bucket": "override-bucket"
    }
  }
}
```

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "status": "RUNNING",
  "triggered_at": "2026-02-03T10:00:00Z"
}
```

### List Export Runs

**GET** `/api/v1/scheduled-exports/{id}/runs/`

List all runs for a scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `status` (string): Filter by status (`RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`)
- `prefect_flow_run_id` (string): Filter by Prefect flow run ID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "count": 25,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "COMPLETED",
      "prefect_flow_run_id": "prefect-flow-run-123",
      "started_at": "2026-02-03T02:00:00Z",
      "completed_at": "2026-02-03T02:15:00Z",
      "items_exported": 150,
      "items_failed": 0,
      "error_message": null
    }
  ]
}
```

### Get Export Run

**GET** `/api/v1/scheduled-exports/runs/{run_id}/`

Get details of a specific export run.

**Path Parameters:**
- `run_id` (UUID): Export run UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z",
  "completed_at": "2026-02-03T02:15:00Z",
  "items_exported": 150,
  "items_failed": 0,
  "error_message": null,
  "metadata": {
    "destination": "s3://export-bucket/exports/sales/2026-02-03/",
    "files_exported": ["dataset_123.parquet", "dataset_456.parquet"]
  }
}
```

---

## Scheduled Export Internal Worker API

**Status**: Internal (Worker-only)

The Internal Worker API endpoints are used exclusively by Prefect workers for scheduled export execution. These endpoints are **not** intended for public use and are tagged as "Internal (Worker)" in OpenAPI.

### Authentication

**Mechanism**: Worker API key authentication

- **Environment-based**: `HUB_WORKER_API_KEY` environment variable
  - Worker sends: `Authorization: ApiKey <HUB_WORKER_API_KEY>`
  - Worker must send: `X-Tenant-ID: <tenant-uuid>` header
- **Database API key**: API key with scope `scheduled_export:internal`
  - Worker sends: `Authorization: ApiKey <api-key>`
  - Tenant is resolved from API key

**Tenant Isolation**: Every request validates tenant; run and scheduled_export must belong to that tenant. Requests with missing/invalid token or wrong tenant are rejected (401/403).

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

### Create Run

**POST** `/api/v1/scheduled-exports/internal/runs/`

Create a new scheduled export run (status RUNNING). Idempotent by `idempotency_key` or `prefect_flow_run_id`.

**Request Body:**
```json
{
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "idempotency_key": "optional-idempotency-key"
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Path Parameters:**
- `scheduled_export_id` (UUID, required): UUID of the scheduled export
- `prefect_flow_run_id` (string, optional): Prefect flow run ID for correlation
- `idempotency_key` (string, optional): If provided and a run already exists with this key, returns 200 with existing run (no duplicate)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (201 Created):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z"
}
```

**Response (200 OK)** - If run already exists (idempotent):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z"
}
```

### Update Run

**PATCH** `/api/v1/scheduled-exports/internal/runs/{run_id}/`

Update a scheduled export run (status, completion, error message, counts).

**Path Parameters:**
- `run_id` (UUID): Export run UUID

**Request Body:**
```json
{
  "status": "COMPLETED",
  "completed_at": "2026-02-03T02:15:00Z",
  "items_exported": 150,
  "items_failed": 0,
  "error_message": null
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z",
  "completed_at": "2026-02-03T02:15:00Z",
  "items_exported": 150,
  "items_failed": 0
}
```

### Process Export

**POST** `/api/v1/scheduled-exports/internal/process-export/`

Process a single export item (dataset or file) for a scheduled export run. Validates run and tenant, applies business rules (scope, access), prepares payload or signed URL.

**Request Body:**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "item_type": "dataset",
  "item_id": "880e8400-e29b-41d4-a716-446655440000"
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "item_id": "880e8400-e29b-41d4-a716-446655440000",
  "item_type": "dataset",
  "status": "ready",
  "upload_method": "direct",
  "upload_url": "s3://export-bucket/exports/sales/2026-02-03/dataset_123.parquet",
  "signed_url": null,
  "payload": null
}
```

**Response (200 OK)** - If signed URL required:
```json
{
  "item_id": "880e8400-e29b-41d4-a716-446655440000",
  "item_type": "dataset",
  "status": "ready",
  "upload_method": "signed_url",
  "upload_url": "s3://export-bucket/exports/sales/2026-02-03/dataset_123.parquet",
  "signed_url": "https://export-bucket.s3.amazonaws.com/exports/sales/2026-02-03/dataset_123.parquet?X-Amz-Algorithm=...",
  "payload": null
}
```

### Get Config

**GET** `/api/v1/scheduled-exports/internal/config/{scheduled_export_id}/`

Get scheduled export configuration for Prefect worker (without raw credentials).

**Path Parameters:**
- `scheduled_export_id` (UUID): Scheduled export UUID

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Export",
  "destination_type": "S3",
  "destination_config": {
    "bucket": "export-bucket",
    "prefix": "exports/sales/",
    "access_key_id": "***masked***",
    "secret_access_key": "***masked***"
  },
  "schedule_config": {
    "cron": "0 2 * * *"
  },
  "source_scope": {
    "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"],
    "dataset_ids": [],
    "file_ids": [],
    "contract_id": null
  },
  "status": "ACTIVE"
}
```

**Security**: Credentials in `destination_config` are **masked** (e.g., `***masked***`) or omitted. Worker must not log full config. See runbooks for credential handling.

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Scheduled export not found

---

## Rate Limiting

### Public API Endpoints

Public scheduled export endpoints are rate-limited per tenant and per user:

- **Tenant-level**: Per tenant, per endpoint category
- **User-level**: Per user, per endpoint category (50% of tenant limit)
- **API Key-level**: Per API key, per endpoint category (same as user limit)

**Endpoint Category**: `GENERAL` (default)

**Default Limits**:
- **BURST** (10 seconds): 100 requests
- **SUSTAINED** (60 seconds): 600 requests
- **DAILY** (24 hours): 100,000 requests

### Internal Worker API Endpoints

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

Internal worker endpoints (`/api/v1/scheduled-exports/internal/*`) are not subject to rate limiting as they are:
- Used exclusively by Prefect workers (controlled infrastructure)
- Authenticated via worker API keys (not user-facing)
- Required for reliable workflow execution

---

## OpenAPI Schema

Internal worker API endpoints are tagged **"Internal (Worker)"** in the OpenAPI schema and can be:
- Excluded from public API documentation
- Documented separately (see this document)

Public API endpoints are tagged **"Scheduled Exports"** in the OpenAPI schema.

---

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-02-03T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "field_name",
          "message": "Field-specific error",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

**Common Error Codes:**
- `VALIDATION_ERROR`: Request validation failed
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Insufficient permissions
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `SERVICE_UNAVAILABLE`: Prefect service unavailable (503)

---

## Related Documentation

- [Scheduled Export Guide](SCHEDULED_EXPORT_GUIDE.md) - User and operator guide
- [Runbooks](../runbooks/RB-SCHEDULED-EXPORT-001.md) - Operational procedures
- [Services Architecture](SERVICES_ARCHITECTURE.md#scheduled-export-execution-model) - Execution model
- [OpenAPI Schema](../api-docs/openapi.json) - Complete API schema

---

# Scheduled Ingestion API Endpoints Reference

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Overview

The Scheduled Ingestion API provides endpoints for managing scheduled data ingestion workflows. The API includes:

- **Public API**: Endpoints for creating, managing, and monitoring scheduled ingestions (tenant-scoped)
- **Internal Worker API**: Endpoints used exclusively by Prefect workers for execution (worker-authenticated)

---

## Scheduled Ingestion (Public API)

### List Scheduled Ingestions

**GET** `/api/v1/scheduled-ingestions/`

List all scheduled ingestions for the authenticated tenant.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `status` (string): Filter by status (`ACTIVE`, `PAUSED`, `ERROR`)
- `source_type` (string): Filter by source type (`S3`, `GCS`, `AZURE_BLOB`, `HTTP`, `FTP`, `SFTP`)

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped (users can only access their tenant's ingestions)

**Rate Limiting**: Per tenant/user limits (see [Rate Limiting](#rate-limiting))

**Response (200 OK):**
```json
{
  "count": 10,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Daily Sales Data",
      "source_type": "S3",
      "source_config": {
        "bucket": "data-bucket",
        "path": "sales/daily/"
      },
      "schedule_type": "DAILY",
      "schedule_config": {
        "time": "02:00"
      },
      "file_pattern": ".*\\.csv",
      "status": "ACTIVE",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### Create Scheduled Ingestion

**POST** `/api/v1/scheduled-ingestions/`

Create a new scheduled ingestion.

**Request Body:**
```json
{
  "name": "Daily Sales Data",
  "source_type": "S3",
  "source_config": {
    "bucket": "data-bucket",
    "path": "sales/daily/",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  },
  "schedule_type": "DAILY",
  "schedule_config": {
    "time": "02:00"
  },
  "file_pattern": ".*\\.csv",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Data",
  "source_type": "S3",
  "status": "ACTIVE",
  "created_at": "2026-01-15T10:00:00Z"
}
```

### Get Scheduled Ingestion

**GET** `/api/v1/scheduled-ingestions/{id}/`

Get details of a specific scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Data",
  "source_type": "S3",
  "source_config": {
    "bucket": "data-bucket",
    "path": "sales/daily/"
  },
  "schedule_type": "DAILY",
  "schedule_config": {
    "time": "02:00"
  },
  "file_pattern": ".*\\.csv",
  "status": "ACTIVE",
  "next_run_at": "2026-02-04T02:00:00Z",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### Update Scheduled Ingestion

**PUT** `/api/v1/scheduled-ingestions/{id}/`

Update a scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Request Body:** Same as create, all fields optional

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):** Updated scheduled ingestion object

### Delete Scheduled Ingestion

**DELETE** `/api/v1/scheduled-ingestions/{id}/`

Delete a scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (204 No Content)**

### Trigger Scheduled Ingestion

**POST** `/api/v1/scheduled-ingestions/{id}/trigger/`

Manually trigger a scheduled ingestion run (creates Prefect flow run).

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (202 Accepted):**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "status": "RUNNING"
}
```

### List Scheduled Ingestion Runs

**GET** `/api/v1/scheduled-ingestions/{id}/runs/`

List runs for a scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Query Parameters:**
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `status` (string): Filter by status (`RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`)

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "count": 50,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "COMPLETED",
      "files_found": 10,
      "files_processed": 10,
      "files_failed": 0,
      "started_at": "2026-02-03T02:00:00Z",
      "completed_at": "2026-02-03T02:15:00Z",
      "prefect_flow_run_id": "prefect-flow-run-123"
    }
  ]
}
```

---

## Scheduled Ingestion Internal Worker API

**Base Path**: `/api/v1/scheduled-ingestions/internal/`

**Status**: Internal (Worker-only)

The Internal Worker API endpoints are used exclusively by Prefect workers for scheduled ingestion execution. These endpoints are **not** intended for public use and are tagged as "Internal (Worker)" in OpenAPI.

### Authentication

**Mechanism**: Worker API key authentication

- **Environment-based**: `HUB_WORKER_API_KEY` environment variable
  - Worker sends: `Authorization: ApiKey <HUB_WORKER_API_KEY>`
  - Worker must send: `X-Tenant-ID: <tenant-uuid>` header
- **Database API key**: API key with scope `scheduled_ingestion:internal`
  - Worker sends: `Authorization: ApiKey <api-key>`
  - Tenant is resolved from API key

**Tenant Isolation**: Every request validates tenant; run and scheduled_ingestion must belong to that tenant. Requests with missing/invalid token or wrong tenant are rejected (401/403).

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

### Create Run

**POST** `/api/v1/scheduled-ingestions/internal/runs/`

Create a new scheduled ingestion run (status RUNNING). Idempotent by `idempotency_key` or `prefect_flow_run_id`.

**Request Body:**
```json
{
  "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "idempotency_key": "optional-idempotency-key"
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Path Parameters:**
- `scheduled_ingestion_id` (UUID, required): UUID of the scheduled ingestion
- `prefect_flow_run_id` (string, optional): Prefect flow run ID for correlation
- `idempotency_key` (string, optional): If provided and a run already exists with this key, returns 200 with existing run (no duplicate)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_ingestion:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (201 Created):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "started_at": "2026-02-03T02:00:00Z",
  "prefect_flow_run_id": "prefect-flow-run-123"
}
```

**Response (200 OK - Idempotent Replay):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "prefect_flow_run_id": "prefect-flow-run-123"
}
```

**Side Effects:**
- Creates `ScheduledIngestionRun` with status RUNNING
- Emits audit event (`SCHEDULED_INGESTION_RUN.CREATED`)
- Publishes domain event (`ingestion.started`)
- Emits Prometheus metrics (`scheduled_ingestion_runs_total`, `scheduled_ingestion_runs_running`)

**Error Responses:**
- `400 Bad Request`: Validation error or tenant required
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Scheduled ingestion not found

### Update Run

**PATCH** `/api/v1/scheduled-ingestions/internal/runs/{run_id}/`

Update a scheduled ingestion run (status, file counts, result_json, completed_at, etc.).

**Path Parameters:**
- `run_id` (UUID): Run UUID

**Request Body (all fields optional):**
```json
{
  "status": "COMPLETED",
  "files_found": 10,
  "files_processed": 10,
  "files_failed": 0,
  "result_json": {
    "summary": "Processing complete"
  },
  "completed_at": "2026-02-03T02:15:00Z",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "error_message": null
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "files_found": 10,
  "files_processed": 10,
  "files_failed": 0,
  "completed_at": "2026-02-03T02:15:00Z"
}
```

**Side Effects (when status changes to COMPLETED or FAILED):**
1. **ScheduledIngestion**: Recalculate and set `next_run_at`; if COMPLETED and ingestion was in ERROR, clear status to ACTIVE and clear `error_message`
2. **If COMPLETED**: Call `CostTrackingManager.calculate_run_costs(run.id)`
3. Call `DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)`
4. Send completion or failure notification if configured (`source_config.send_notifications`, `notification_recipients`)
5. Emit domain events (`ingestion.completed` or `ingestion.failed`) and audit events
6. Emit Prometheus metrics (`scheduled_ingestion_runs_total`, `scheduled_ingestion_duration_seconds`, `scheduled_ingestion_runs_running`)

**Error Responses:**
- `400 Bad Request`: Validation error or tenant required
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Run not found

### Process File

**POST** `/api/v1/scheduled-ingestions/internal/process-file/`

Process a single file for a scheduled ingestion run (validate, DQ, create file/dataset, index, incremental state).

**Request Body (multipart or JSON):**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "file_path": "sales/daily/2026-02-03.csv",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "660e8400-e29b-41d4-a716-446655440001",
  "dq_options": {
    "profile_key": "sales-profile",
    "strict_mode": true,
    "min_quality_score": 0.8
  },
  "file_content": "<base64-encoded-file-content>"
}
```

**Multipart Form Data:**
- `run_id` (UUID, required): Run UUID
- `file_path` (string, required): Logical path/key of the file
- `file` (file, optional): File upload (multipart)
- `file_content` (string, optional): Base64-encoded file content (JSON)
- `asset_id` (UUID, optional): Override asset
- `contract_id` (UUID, optional): Override contract
- `dq_options` (JSON, optional): DQ options

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)
- `Content-Type: multipart/form-data` (for file upload) or `application/json` (for base64 content)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only

**Rate Limiting**: **No rate limit**

**Response (201 Created):**
```json
{
  "file_id": "880e8400-e29b-41d4-a716-446655440000",
  "dataset_id": "990e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSED",
  "dq_result": {
    "quality_score": 0.95,
    "passed": true
  }
}
```

**Processing Order:**
1. Load run and scheduled ingestion (tenant check)
2. Validate file using **ScheduledIngestionBusinessRules** (validation_type="source" for format/size)
3. Optional DQ (existing DQ service)
4. Create File + Dataset (existing Files/Datasets services)
5. Index (Search service)
6. Update incremental state
7. On permanent failure: DLQ, audit, domain events, Prometheus metrics

**Error Responses:**
- `400 Bad Request`: Validation error (run_id and file_path required)
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Run not found
- `422 Unprocessable Entity`: File validation failed or DQ failed
- `500 Internal Server Error`: Processing error (DLQ record created)

### Get Configuration

**GET** `/api/v1/scheduled-ingestions/internal/config/{scheduled_ingestion_id}/`

Get configuration for a scheduled ingestion (source_type, source_config with masked credentials, file_pattern, schedule_config, ingestion_state, etc.).

**Path Parameters:**
- `scheduled_ingestion_id` (UUID): Scheduled ingestion UUID

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "source_type": "S3",
  "source_config": {
    "bucket": "data-bucket",
    "path": "sales/daily/",
    "access_key_id": "***masked***",
    "secret_access_key": "***masked***"
  },
  "file_pattern": ".*\\.csv",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "660e8400-e29b-41d4-a716-446655440001",
  "schedule_config": {
    "time": "02:00"
  },
  "ingestion_state": {
    "processed_files": ["sales/daily/2026-02-02.csv", "sales/daily/2026-02-03.csv"],
    "last_processed_at": "2026-02-03T02:15:00Z"
  },
  "auto_create_asset": true,
  "auto_activate": false
}
```

**Security**: Credentials in `source_config` are **masked** (e.g., `***masked***`) or omitted. Worker must not log full config. See runbooks for credential handling.

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Scheduled ingestion not found

---

## Rate Limiting

### Public API Endpoints

Public scheduled ingestion endpoints are rate-limited per tenant and per user:

- **Tenant-level**: Per tenant, per endpoint category
- **User-level**: Per user, per endpoint category (50% of tenant limit)
- **API Key-level**: Per API key, per endpoint category (same as user limit)

**Endpoint Category**: `GENERAL` (default)

**Default Limits**:
- **BURST** (10 seconds): 100 requests
- **SUSTAINED** (60 seconds): 600 requests
- **DAILY** (24 hours): 100,000 requests

### Internal Worker API Endpoints

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

Internal worker endpoints (`/api/v1/scheduled-ingestions/internal/*`) are not subject to rate limiting as they are:
- Used exclusively by Prefect workers (controlled infrastructure)
- Authenticated via worker API keys (not user-facing)
- Required for reliable workflow execution

---

## OpenAPI Schema

Internal worker API endpoints are tagged **"Internal (Worker)"** in the OpenAPI schema and can be:
- Excluded from public API documentation
- Documented separately (see [SCHEDULED_INGESTION_WORKER_API.md](SCHEDULED_INGESTION_WORKER_API.md))
- Included in internal/developer documentation only

To view the OpenAPI schema:
- **Public API**: `/api/schema/` (excludes internal endpoints)
- **Full Schema**: `/api/schema/?include_internal=true` (includes internal endpoints)

---

## Error Responses

All endpoints return structured error responses:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

**Common Error Codes:**
- `TENANT_REQUIRED`: Tenant ID missing or invalid
- `NOT_FOUND`: Resource not found
- `FORBIDDEN`: Tenant mismatch or insufficient permissions
- `VALIDATION_ERROR`: Request validation failed
- `AUTHENTICATION_REQUIRED`: Authentication required

---

## Related Documentation

- [Scheduled Ingestion Worker API](SCHEDULED_INGESTION_WORKER_API.md) - Detailed internal API documentation
- [Deployment Order](DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md) - Deployment procedures
- [Release Notes](RELEASE_NOTES_SCHEDULED_INGESTION_PREFECT.md) - Release information
- [Runbooks](runbooks/RB-SCHEDULED-INGESTION-001.md) - Operational procedures

---

# Marketplace Integration API Reference

Complete API reference for the **external** marketplace APIs (connections, sync, mappings).

> **Internal vs external:** For a clear split between the Hub’s own marketplace (listings, orders, entitlements, preview under `/api/v1/marketplace/`) and external marketplace integrations (this API, under `/api/v1/integrations/marketplace/`), see [Internal vs External Marketplace](MARKETPLACE_INTERNAL_VS_EXTERNAL.md).

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Base URLs](#base-urls)
4. [Marketplace Connections API](#marketplace-connections-api)
5. [Marketplace Sync Jobs API](#marketplace-sync-jobs-api)
6. [Marketplace Mappings API](#marketplace-mappings-api)
7. [Request/Response Schemas](#requestresponse-schemas)
8. [Error Responses](#error-responses)
9. [Rate Limiting](#rate-limiting)
10. [OpenAPI/Swagger Examples](#openapiswagger-examples)

---

## Overview

The Marketplace Integration API provides endpoints for managing marketplace connections, synchronization jobs, and mappings between Hub assets and external marketplace listings.

### Key Features

- **Connection Management**: Create, update, test, and delete marketplace connections
- **Sync Job Management**: Create, monitor, and cancel synchronization jobs
- **Mapping Management**: View and delete marketplace mappings
- **Multi-Tenant Support**: All operations are tenant-scoped
- **RBAC/ABAC Authorization**: Role-based and attribute-based access control
- **Rate Limiting**: Built-in rate limiting for all endpoints
- **Comprehensive Filtering**: Filter, search, and paginate results

### API Version

All endpoints are under `/api/v1/integrations/marketplace/`.

---

## Authentication

All endpoints require authentication. Two authentication methods are supported:

### JWT Token Authentication

```bash
# Login to get token
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"password"}'

# Use token in requests
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/marketplace/connections/
```

### API Key Authentication

```bash
curl -H "X-API-Key: <api-key>" \
  http://localhost:8000/api/v1/integrations/marketplace/connections/
```

---

## Base URLs

- **Development**: `http://localhost:8000`
- **Staging**: `https://staging-api.datahub.example.com`
- **Production**: `https://api.datahub.example.com`

---

## Marketplace Connections API

### List Marketplace Connections

List all marketplace connections for the authenticated user's tenant.

**Endpoint**: `GET /api/v1/integrations/marketplace/connections/`

**Authentication**: Required

**Authorization**:
- Read: Authenticated user (tenant-scoped)
- Write: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Query Parameters**:
- `marketplace_type` (string, optional): Filter by marketplace type (e.g., `SNOWFLAKE_DATA_MARKETPLACE`, `AWS_DATA_EXCHANGE`)
- `is_active` (boolean, optional): Filter by active status (`true`/`false`)
- `search` (string, optional): Search in connection name
- `ordering` (string, optional): Order by field (e.g., `name`, `-created_at`). Prefix with `-` for descending.
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Response**: `200 OK`

```json
{
  "count": 10,
  "next": "http://localhost:8000/api/v1/integrations/marketplace/connections/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
      "name": "Snowflake Production",
      "is_active": true,
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-10T10:00:00Z"
    }
  ]
}
```

### Get Marketplace Connection

Get detailed information about a specific marketplace connection.

**Endpoint**: `GET /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

**Note**: The `config` field is not returned in responses for security reasons. Use the test endpoint to verify connection configuration.

### Create Marketplace Connection

Create a new marketplace connection.

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "config": {
    "account": "test_account",
    "user": "test_user",
    "token": "test_token",
    "warehouse": "COMPUTE_WH",
    "role": "ACCOUNTADMIN"
  },
  "is_active": true
}
```

**Response**: `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors (invalid marketplace_type, missing required fields, etc.)
- `409 Conflict`: Connection name already exists for tenant
- `429 Too Many Requests`: Rate limit exceeded

### Update Marketplace Connection

Update an existing marketplace connection.

**Endpoint**: `PUT /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "name": "Snowflake Production Updated",
  "config": {
    "account": "test_account",
    "user": "test_user",
    "token": "new_token",
    "warehouse": "COMPUTE_WH",
    "role": "ACCOUNTADMIN"
  },
  "is_active": true
}
```

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production Updated",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:05:00Z"
}
```

### Partially Update Marketplace Connection

Partially update an existing marketplace connection.

**Endpoint**: `PATCH /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "is_active": false
}
```

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "is_active": false,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:05:00Z"
}
```

### Delete Marketplace Connection

Delete a marketplace connection.

**Endpoint**: `DELETE /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Response**: `204 No Content`

**Error Responses**:
- `404 Not Found`: Connection not found
- `409 Conflict`: Connection has active sync jobs or mappings

### Test Marketplace Connection

Test a marketplace connection.

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{id}/test/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**: (optional)

```json
{
  "config": {
    "account": "test_account",
    "user": "test_user",
    "token": "test_token"
  }
}
```

**Response**: `200 OK`

```json
{
  "success": true,
  "message": "Connection test successful",
  "details": {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "tested_at": "2026-01-10T10:00:00Z"
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid configuration
- `401 Unauthorized`: Authentication failed
- `404 Not Found`: Connection not found
- `500 Internal Server Error`: Connection test failed

---

## Marketplace Sync Jobs API

### List Marketplace Sync Jobs

List all marketplace sync jobs for the authenticated user's tenant.

**Endpoint**: `GET /api/v1/integrations/marketplace/sync/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Query Parameters**:
- `connection_id` (UUID, optional): Filter by connection ID
- `direction` (string, optional): Filter by sync direction (`PULL`, `PUSH`, `BIDIRECTIONAL`)
- `status` (string, optional): Filter by status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`)
- `ordering` (string, optional): Order by field (e.g., `created_at`, `-created_at`). Prefix with `-` for descending.
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Response**: `200 OK`

```json
{
  "count": 25,
  "next": "http://localhost:8000/api/v1/integrations/marketplace/sync/?page=2",
  "previous": null,
  "results": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "connection": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Snowflake Production",
        "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
      },
      "direction": "PULL",
      "status": "COMPLETED",
      "items_synced": 100,
      "items_failed": 0,
      "errors": [],
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-10T10:05:00Z",
      "completed_at": "2026-01-10T10:05:00Z"
    }
  ]
}
```

### Get Marketplace Sync Job

Get detailed information about a specific marketplace sync job.

**Endpoint**: `GET /api/v1/integrations/marketplace/sync/{id}/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response**: `200 OK`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "COMPLETED",
  "items_synced": 100,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "data_strategy": "METADATA_ONLY",
    "filters": {},
    "options": {}
  },
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:05:00Z",
  "completed_at": "2026-01-10T10:05:00Z"
}
```

### Create Marketplace Sync Job

Create a new marketplace sync job.

**Endpoint**: `POST /api/v1/integrations/marketplace/sync/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body** (PULL sync):

```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "listing_ids": null,
  "filters": {
    "category": "health"
  },
  "options": {
    "dry_run": false,
    "data_strategy": "METADATA_ONLY"
  }
}
```

**Request Body** (PUSH sync):

```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "asset_ids": [
    "770e8400-e29b-41d4-a716-446655440000",
    "880e8400-e29b-41d4-a716-446655440000"
  ],
  "options": {
    "dry_run": false
  }
}
```

**Response**: `201 Created`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "data_strategy": "METADATA_ONLY",
    "filters": {
      "category": "health"
    },
    "options": {
      "dry_run": false
    }
  },
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z",
  "completed_at": null
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors (invalid connection_id, missing required fields, etc.)
- `404 Not Found`: Connection not found
- `429 Too Many Requests`: Rate limit exceeded

**Note**: Sync jobs are executed asynchronously. Use the GET endpoint to monitor progress.

### Cancel Marketplace Sync Job

Cancel a running marketplace sync job.

**Endpoint**: `POST /api/v1/integrations/marketplace/sync/{id}/cancel/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "reason": "User requested cancellation"
}
```

**Response**: `200 OK`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "CANCELLED",
  "items_synced": 50,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "cancellation_reason": "User requested cancellation"
  },
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:03:00Z",
  "completed_at": "2026-01-10T10:03:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Job cannot be cancelled (already completed/failed/cancelled)
- `404 Not Found`: Sync job not found
- `429 Too Many Requests`: Rate limit exceeded

---

## Marketplace Mappings API

### List Marketplace Mappings

List all marketplace mappings for the authenticated user's tenant.

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Query Parameters**:
- `connection_id` (UUID, optional): Filter by connection ID
- `hub_asset_id` (UUID, optional): Filter by hub asset ID
- `external_listing_id` (string, optional): Filter by external listing ID
- `ordering` (string, optional): Order by field (e.g., `created_at`, `-created_at`). Prefix with `-` for descending.
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Response**: `200 OK`

```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/integrations/marketplace/mappings/?page=2",
  "previous": null,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "connection": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Snowflake Production",
        "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
      },
      "hub_asset": {
        "id": "880e8400-e29b-41d4-a716-446655440000",
        "name": "Sample Dataset",
        "status": "ACTIVE"
      },
      "external_listing_id": "SNOWFLAKE_SAMPLE_DATA",
      "external_resource_ids": ["SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE1"],
      "sync_metadata": {
        "last_sync_status": "SUCCESS",
        "last_sync_errors": []
      },
      "last_synced_at": "2026-01-10T10:00:00Z",
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-10T10:00:00Z"
    }
  ]
}
```

### Get Marketplace Mapping

Get detailed information about a specific marketplace mapping.

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/{id}/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response**: `200 OK`

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "hub_asset": {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "name": "Sample Dataset",
    "status": "ACTIVE"
  },
  "external_listing_id": "SNOWFLAKE_SAMPLE_DATA",
  "external_resource_ids": ["SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE1"],
  "sync_metadata": {
    "last_sync_status": "SUCCESS",
    "last_sync_errors": []
  },
  "last_synced_at": "2026-01-10T10:00:00Z",
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

### Delete Marketplace Mapping

Delete a marketplace mapping.

**Endpoint**: `DELETE /api/v1/integrations/marketplace/mappings/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Response**: `204 No Content`

**Error Responses**:
- `404 Not Found`: Mapping not found
- `429 Too Many Requests`: Rate limit exceeded

**Note**: Mappings are created automatically during sync operations. They cannot be created manually via API.

---

## Request/Response Schemas

### MarketplaceConnection Schema

```json
{
  "id": "UUID",
  "marketplace_type": "string (enum: SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE, ...)",
  "name": "string (max 255 chars, unique per tenant)",
  "is_active": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Note**: The `config` field is encrypted and not returned in API responses.

### MarketplaceSyncJob Schema

```json
{
  "id": "UUID",
  "connection": {
    "id": "UUID",
    "name": "string",
    "marketplace_type": "string"
  },
  "direction": "string (enum: PULL, PUSH, BIDIRECTIONAL)",
  "status": "string (enum: PENDING, RUNNING, COMPLETED, FAILED, PARTIAL, CANCELLED)",
  "items_synced": "integer",
  "items_failed": "integer",
  "errors": ["string"],
  "metadata": {
    "data_strategy": "string (enum: METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL)",
    "filters": {},
    "options": {},
    "cancellation_reason": "string (optional)"
  },
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "completed_at": "ISO 8601 datetime (nullable)"
}
```

### MarketplaceMapping Schema

```json
{
  "id": "UUID",
  "connection": {
    "id": "UUID",
    "name": "string",
    "marketplace_type": "string"
  },
  "hub_asset": {
    "id": "UUID",
    "name": "string",
    "status": "string"
  },
  "external_listing_id": "string",
  "external_resource_ids": ["string"],
  "sync_metadata": {
    "last_sync_status": "string",
    "last_sync_errors": ["string"]
  },
  "last_synced_at": "ISO 8601 datetime (nullable)",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

### Create Connection Request Schema

```json
{
  "marketplace_type": "string (required, enum)",
  "name": "string (required, max 255 chars)",
  "config": {
    "account": "string (Snowflake)",
    "user": "string (Snowflake)",
    "token": "string (Snowflake)",
    "warehouse": "string (Snowflake, optional)",
    "role": "string (Snowflake, optional)",
    "base_url": "string (CKAN)",
    "api_key": "string (CKAN)",
    "aws_access_key_id": "string (AWS)",
    "aws_secret_access_key": "string (AWS)",
    "region_name": "string (AWS, optional)",
    "project_id": "string (GCP)",
    "credentials_json": "string (GCP, optional)",
    "host": "string (Databricks)",
    "token": "string (Databricks)",
    "cluster_id": "string (Databricks, optional)"
  },
  "is_active": "boolean (optional, default: true)"
}
```

### Create Sync Job Request Schema (PULL)

```json
{
  "connection_id": "UUID (required)",
  "direction": "PULL (required)",
  "listing_ids": ["string"] (optional),
  "filters": {
    "category": "string",
    "tags": ["string"],
    "provider": "string"
  } (optional),
  "options": {
    "dry_run": "boolean (optional, default: false)",
    "data_strategy": "string (optional, enum: METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL, default: METADATA_ONLY)",
    "limit": "integer (optional)"
  } (optional)
}
```

### Create Sync Job Request Schema (PUSH)

```json
{
  "connection_id": "UUID (required)",
  "direction": "PUSH (required)",
  "asset_ids": ["UUID"] (required),
  "options": {
    "dry_run": "boolean (optional, default: false)"
  } (optional)
}
```

---

## Error Responses

All error responses follow a consistent format:

```json
{
  "error": "Error message",
  "details": {
    "field_name": ["Error message for field"]
  }
}
```

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `204 No Content`: Resource deleted successfully
- `400 Bad Request`: Validation errors, invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate name, active sync jobs)
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Common Error Responses

#### 400 Bad Request - Validation Error

```json
{
  "error": "Validation failed",
  "details": {
    "marketplace_type": ["Invalid marketplace type"],
    "name": ["This field is required"]
  }
}
```

#### 401 Unauthorized

```json
{
  "error": "Authentication credentials were not provided"
}
```

#### 403 Forbidden

```json
{
  "error": "You do not have permission to perform this action"
}
```

#### 404 Not Found

```json
{
  "error": "Marketplace connection not found"
}
```

#### 409 Conflict

```json
{
  "error": "Connection name already exists for this tenant"
}
```

#### 429 Too Many Requests

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

---

## Rate Limiting

All endpoints are rate-limited to prevent abuse and ensure fair usage.

### Rate Limit Headers

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1641900000
```

### Rate Limit Exceeded

When rate limit is exceeded, the API returns `429 Too Many Requests` with a `retry_after` value indicating when to retry.

---

## OpenAPI/Swagger Examples

### OpenAPI 3.0 Specification

The API follows OpenAPI 3.0 specification. The complete OpenAPI schema is available at:

- **Development**: `http://localhost:8000/api/schema/`
- **Staging**: `https://staging-api.datahub.example.com/api/schema/`
- **Production**: `https://api.datahub.example.com/api/schema/`

### Swagger UI

Interactive API documentation is available via Swagger UI:

- **Development**: `http://localhost:8000/api/docs/`
- **Staging**: `https://staging-api.datahub.example.com/api/docs/`
- **Production**: `https://api.datahub.example.com/api/docs/`

### Example: Create Connection (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/integrations/marketplace/connections/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "name": "Snowflake Production",
    "config": {
      "account": "test_account",
      "user": "test_user",
      "token": "test_token",
      "warehouse": "COMPUTE_WH",
      "role": "ACCOUNTADMIN"
    },
    "is_active": true
  }'
```

### Example: Create Connection (Python)

```python
import requests

url = "http://localhost:8000/api/v1/integrations/marketplace/connections/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "name": "Snowflake Production",
    "config": {
        "account": "test_account",
        "user": "test_user",
        "token": "test_token",
        "warehouse": "COMPUTE_WH",
        "role": "ACCOUNTADMIN"
    },
    "is_active": True
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Example: Create Sync Job (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/integrations/marketplace/sync/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "550e8400-e29b-41d4-a716-446655440000",
    "direction": "PULL",
    "filters": {
      "category": "health"
    },
    "options": {
      "dry_run": false,
      "data_strategy": "METADATA_ONLY"
    }
  }'
```

### Example: Create Sync Job (Python)

```python
import requests

url = "http://localhost:8000/api/v1/integrations/marketplace/sync/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "connection_id": "550e8400-e29b-41d4-a716-446655440000",
    "direction": "PULL",
    "filters": {
        "category": "health"
    },
    "options": {
        "dry_run": False,
        "data_strategy": "METADATA_ONLY"
    }
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Example: List Connections with Filtering (cURL)

```bash
curl -X GET "http://localhost:8000/api/v1/integrations/marketplace/connections/?marketplace_type=SNOWFLAKE_DATA_MARKETPLACE&is_active=true&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Example: List Connections with Filtering (Python)

```python
import requests

url = "http://localhost:8000/api/v1/integrations/marketplace/connections/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN"
}
params = {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "is_active": True,
    "page": 1,
    "page_size": 10
}

response = requests.get(url, headers=headers, params=params)
print(response.json())
```

---

## Additional Resources

- **Framework Architecture**: `docs/MARKETPLACE_INTEGRATION_FRAMEWORK.md` - Complete architecture documentation
- **Connector Development Guide**: `docs/MARKETPLACE_CONNECTOR_DEVELOPMENT_GUIDE.md` - Connector implementation guide
- **API Standards**: `docs/API_STANDARDS.md` - API standards and conventions
- **API Error Codes**: `docs/API_ERROR_CODES.md` - Complete error code reference
- **CLI Usage**: `cli/docs/MARKETPLACE_USAGE.md` - Complete CLI commands for marketplace integration
- **SDK Usage**: `sdk/python/docs/MARKETPLACE_USAGE.md` - Complete SDK APIs for marketplace integration

---

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

# Semantic API Specification

## Base URLs

| Environment | Hub (Django) | Semantic Service (FastAPI) |
|-------------|--------------|---------------------------|
| Development | `http://localhost:8000/semantic/` | `http://localhost:8081/` |
| Staging | `https://staging.meshant.io/semantic/` | Internal: `semantic-service:8081` |
| Production | `https://meshant.io/semantic/` | Internal: `semantic-service:8081` |

## Content Negotiation

The semantic layer serves multiple RDF serializations based on `Accept` header:

| Accept Header | Format | Endpoint Support |
|---|---|---|
| `application/sparql-results+json` | SPARQL JSON Results | `/sparql` (SELECT, ASK) |
| `text/turtle` | Turtle | `/sparql` (CONSTRUCT, DESCRIBE), `/ontology` |
| `application/ld+json` | JSON-LD | `/id/*`, `/context.jsonld` |
| `application/rdf+xml` | RDF/XML | `/sparql` (CONSTRUCT, DESCRIBE) |

If `Accept` is not specified, the default is `application/sparql-results+json` for SELECT/ASK and `text/turtle` for CONSTRUCT/DESCRIBE.

## Endpoints

### POST /semantic/sparql
Execute a SPARQL 1.1 query (SELECT, ASK, CONSTRUCT, DESCRIBE only).

**Allowed**: SELECT, ASK, CONSTRUCT, DESCRIBE
**Blocked**: INSERT, DELETE, DROP, CLEAR, LOAD, CREATE, MOVE, COPY, ADD, SERVICE

```bash
curl -X POST https://meshant.io/semantic/sparql \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10", "format": "json"}'
```

**Error responses**:
- `400 INVALID_SPARQL` — Syntax error or forbidden keyword
- `408 QUERY_TIMEOUT` — Query exceeded `SPARQL_QUERY_TIMEOUT_SECONDS`
- `429 RATE_LIMIT_EXCEEDED` — Per-tenant or global rate limit hit (`Retry-After` header included)

### GET /semantic/id/{type}/{id}
Resolve a resource IRI to its JSON-LD representation.

**HTTP 303 Flow**:
1. Client requests `/semantic/resource/asset/{uuid}`
2. Server returns `303 See Other` with `Location: /semantic/id/asset/{uuid}`
3. Client follows redirect to get JSON-LD

```bash
curl -L https://meshant.io/semantic/id/asset/550e8400-e29b-41d4-a716-446655440000 \
  -H "Accept: application/ld+json"
```

### GET /semantic/ontology
Returns the Hub ontology in Turtle format.

```bash
curl https://meshant.io/semantic/ontology -H "Accept: text/turtle"
```

### GET /semantic/context.jsonld
Returns the JSON-LD context document.

## Named Graph Scoping

All data is isolated by tenant in named graphs:
- System ontology: `<urn:system:ontology>`
- Tenant data: `<urn:tenant:{tenant_id}>`

SPARQL queries are automatically rewritten to scope results to the authenticated tenant's named graph. Direct `GRAPH` clause access is restricted.

## SHACL Validation

Contracts are validated against SHACL shapes before triple insertion. Violations produce a structured error:

```json
{
  "code": "SHACL_VIOLATION",
  "violations": [
    {"severity": "Violation", "path": "hub:name", "message": "Value does not match pattern"}
  ]
}
```

## Rate Limiting

| Window | Default | Platform Max |
|--------|---------|-------------|
| Burst (10s) | 50 | 500 |
| Sustained (60s) | 200 | 2,000 |
| Daily | 50,000 | 500,000 |

Rate limit headers: `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After` (on 429).

## API Version

All responses include `API-Version: 1.0` header.

---

# Scheduled Ingestion Worker API (Internal)

This document describes the **internal** hub API used only by the Prefect worker for scheduled ingestion execution. These endpoints are not intended for public use and are tagged "Internal (Worker)" in OpenAPI.

## URL namespace

- Base path: `/api/v1/scheduled-ingestions/internal/`
- Endpoints are **not** exposed in public API docs except as internal/worker-only.
- All endpoints require worker authentication (see [Authentication](#authentication)).

## Authentication

- **Mechanism:** API key with scope `scheduled_ingestion:internal`, or environment-based worker key.
- **Required env for worker:** `HUB_WORKER_API_KEY` (or equivalent). When set, the worker can authenticate with `Authorization: ApiKey <HUB_WORKER_API_KEY>` and must send `X-Tenant-ID` on every request. Alternatively, use a tenant API key (from the hub) with scope `scheduled_ingestion:internal`.
- **Tenant isolation:** Every request validates tenant; run and scheduled_ingestion must belong to that tenant. Requests with missing/invalid token or wrong tenant are rejected (401/403).

## Rate Limiting

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

Internal worker API endpoints (`/api/v1/scheduled-ingestions/internal/*`) are not subject to rate limiting as they are:
- Used exclusively by Prefect workers (controlled infrastructure)
- Authenticated via worker API keys (not user-facing)
- Required for reliable workflow execution

This ensures that Prefect workers can execute scheduled ingestion workflows without being throttled by rate limits.

## 1. Run lifecycle

### 1.1 Create run — `POST .../internal/runs/`

**Request body:**

```json
{
  "scheduled_ingestion_id": "uuid",
  "prefect_flow_run_id": "optional-string",
  "idempotency_key": "optional-string"
}
```

- `scheduled_ingestion_id` (required): UUID of the scheduled ingestion.
- `prefect_flow_run_id` (optional): Prefect flow run ID for correlation.
- `idempotency_key` (optional): If provided and a run already exists with this key, returns 200 with existing run (no duplicate).

**Response:**

- **201 Created:** `{"id": "run-uuid", "scheduled_ingestion_id": "...", "status": "RUNNING", ...}`
- **200 OK:** When idempotent replay (same idempotency_key or prefect_flow_run_id); body includes existing run id and status.

**Side effects:** Creates `ScheduledIngestionRun` with status RUNNING; emits audit event and domain events (e.g. IngestionEventPublisher); emits Prometheus metrics (run started).

### 1.2 Update run — `PATCH .../internal/runs/{run_id}/`

**Request body (all optional):**

```json
{
  "status": "COMPLETED|FAILED|CANCELLED|RUNNING",
  "files_found": 0,
  "files_processed": 0,
  "files_failed": 0,
  "result_json": {},
  "completed_at": "ISO8601",
  "prefect_flow_run_id": "string",
  "error_message": "string"
}
```

**Response:** 200 OK with updated run representation.

**Side effects when status is COMPLETED or FAILED:**

1. **ScheduledIngestion:** Recalculate and set `next_run_at`; if COMPLETED and ingestion was in ERROR, clear status to ACTIVE and clear `error_message`.
2. **If COMPLETED:** Call `CostTrackingManager.calculate_run_costs(run.id)`.
3. Call `DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)`.
4. Send completion or failure notification if configured (`source_config.send_notifications`, `notification_recipients`).
5. Emit domain events and audit.

**Metrics:** Run completed/failed/cancelled.

## 2. Process file — `POST .../internal/process-file/`

**Request:** Multipart or JSON with file content or upload URL.

- `run_id` (required): UUID of the run.
- `file_path` (required): Logical path/key of the file.
- `file`: File upload (multipart), or provide `file_content` (base64) / `file_url` per implementation.
- `asset_id` (optional): Override asset.
- `contract_id` (optional): Override contract.
- `dq_options` (optional): e.g. `{"profile_key": "...", "strict_mode": true, "min_quality_score": 0.8}`.

**Response:**

- **201 Created:** `{"file_id": "uuid", "dataset_id": "uuid", ...}` — file and dataset created, indexed, incremental state updated.
- **4xx/5xx:** Structured error; on permanent failure a DLQ record is created and audit/domain events emitted.

**Processing order (same as hub ScheduledIngestionWorkflow):**

1. Load run and scheduled ingestion (tenant check).
2. Validate file using **ScheduledIngestionBusinessRules** (validation_type="source" for format/size).
3. Optional DQ (existing DQ service).
4. Create File + Dataset (existing Files/Datasets services).
5. Index (Search).
6. Update incremental state.
7. On permanent failure: DLQ, audit, domain events, Prometheus metrics.

No business logic in the view; all in service method (e.g. `ScheduledIngestionService.process_file_for_run`).

## 3. Config — `GET .../internal/config/{scheduled_ingestion_id}/`

**Response:** JSON with fields needed by the Prefect flow:

- `source_type`, `source_config` (credentials **masked** or omitted), `file_pattern`, `asset_id`, `contract_id`, `schedule_config`, `ingestion_state` (incremental state), DQ-related options, etc.

**Security:** Config response and hub logs MUST NOT contain raw secrets. Credentials in `source_config` are masked or omitted. Worker must not log full config. See runbooks.

## 4. Error responses

Structured body: `{"error": "message", "code": "CODE", "details": {}}`. Same shape as platform error consistency (e.g. ValidationError → 400, NotFoundError → 404).

## 5. OpenAPI

Internal endpoints are tagged **"Internal (Worker)"** and can be excluded from public schema or documented separately per project convention.

## 6. Running Phase 1 tests

Phase 1 tests (run lifecycle, process-file, config, auth) live in `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py`. No mocks; they use real DB and real services.

**Recommended:** Run with api-service and postgres already up so the database is stable during test DB creation and migrations:

```bash
docker compose up -d postgres redis-cache redis-queue redis-events redis-channels minio jaeger mock-server
# Wait for postgres healthy, then:
docker compose up -d api-service
# Then:
docker compose exec api-service bash -c "cd /app && TESTING=1 python -m pytest hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py -v --tb=short --reuse-db"
```

Or use the script (prefers exec when api-service is running):

```bash
./scripts/run_internal_worker_api_tests.sh
```

If postgres is restarting or you see "database system is shutting down", wait for the stack to be healthy and re-run with `--reuse-db`.

## 7. Phase 2 — Prefect full flow and worker credentials

The Prefect worker runs `scheduled_ingestion_full_flow` (HTTP-only; no Django in worker). Config is fetched from the hub (GET config); credentials in `source_config` are **masked** in the response.

**Worker credentials for connectors:** If a connector needs real credentials (e.g. S3 `access_key_id`/`secret_access_key`), use one of:

- **Prefect Blocks (optional):** Store credentials in a Prefect Block keyed by `scheduled_ingestion/{id}/source_config` and merge into the masked config in the flow before discovery/download. See [Real Scheduled Ingestion/Export E2E runbook](runbooks/REAL_SCHEDULED_INGESTION_EXPORT_E2E.md) for Prefect Blocks, env vars, connector support, and env-gated real E2E tests (`real_scheduled_e2e` marker, `REAL_SCHEDULED_E2E=1`).
- **Environment / config from hub:** For public or env-based auth (e.g. IAM role for S3, or HTTP with no auth), the masked config may be sufficient; or pass credentials via environment variables in the worker and merge in the flow.

Discovery and filter logic match current scheduled ingestion semantics (incremental, file pattern); state is read from hub config (`ingestion_state`).

---

# API Error Codes Reference

Complete reference for all API error codes, their meanings, and how to handle them.

## Table of Contents

1. [Error Response Format](#error-response-format)
2. [HTTP Status Codes](#http-status-codes)
3. [Error Codes](#error-codes)
4. [Field-Level Errors](#field-level-errors)
5. [Error Handling Examples](#error-handling-examples)

---

## Error Response Format

All API errors follow a standardized format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "field_name",
          "message": "Field-specific error message",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

### Error Response Fields

- **code**: Machine-readable error code
- **message**: Human-readable error message
- **http_status**: HTTP status code
- **request_id**: Unique request identifier for support
- **timestamp**: ISO 8601 timestamp of error
- **details**: Additional error details (optional)

---

## HTTP Status Codes

### 400 Bad Request

Client error - invalid request format or validation failure.

**Common causes:**
- Missing required fields
- Invalid field values
- Malformed JSON
- Invalid query parameters

**Example:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "http_status": 400,
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

### 401 Unauthorized

Authentication required - missing or invalid authentication token.

**Common causes:**
- Missing Authorization header
- Invalid token
- Expired token

**Example:**
```json
{
  "error": {
    "code": "AUTH_UNAUTHORIZED",
    "message": "Authentication required",
    "http_status": 401
  }
}
```

### 403 Forbidden

Permission denied - authenticated but insufficient permissions.

**Common causes:**
- Insufficient role permissions
- Tenant access restrictions
- Resource ownership restrictions

**Example:**
```json
{
  "error": {
    "code": "AUTH_FORBIDDEN",
    "message": "Permission denied",
    "http_status": 403
  }
}
```

### 404 Not Found

Resource not found - requested resource doesn't exist.

**Common causes:**
- Invalid resource ID
- Resource deleted
- Incorrect URL path

**Example:**
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Contract not found",
    "http_status": 404
  }
}
```

### 409 Conflict

Resource conflict - request conflicts with current state.

**Common causes:**
- Duplicate resource creation
- Concurrent modification conflict
- State transition conflict

**Example:**
```json
{
  "error": {
    "code": "CONFLICT_ERROR",
    "message": "Contract already exists",
    "http_status": 409
  }
}
```

### 429 Too Many Requests

Rate limit exceeded - too many requests in time window.

**Common causes:**
- Exceeded per-tenant rate limit
- Exceeded per-endpoint rate limit
- Burst request pattern

**Example:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "http_status": 429
  }
}
```

**Response headers:**
```
Retry-After: 60
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1642248000
```

### 500 Internal Server Error

Server error - unexpected server-side error.

**Common causes:**
- Database connection failure
- External service failure
- Unhandled exception

**Example:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Internal server error",
    "http_status": 500,
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 502 Bad Gateway / 503 Service Unavailable

Service unavailable - upstream service unavailable.

**Common causes:**
- External service down
- Service maintenance
- Overloaded service

**Example:**
```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Service temporarily unavailable",
    "http_status": 503
  }
}
```

---

## Error Codes

### Validation Errors

#### VALIDATION_ERROR

General validation error.

**HTTP Status:** 400

**Details:**
- `field_errors`: Array of field-specific errors

**Example:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "http_status": 400,
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

### Authentication Errors

#### AUTH_UNAUTHORIZED

Authentication required.

**HTTP Status:** 401

**Resolution:**
- Include Authorization header with valid token
- Refresh expired token

#### AUTH_FORBIDDEN

Permission denied.

**HTTP Status:** 403

**Resolution:**
- Check user role permissions
- Verify tenant access
- Contact administrator for access

### Resource Errors

#### NOT_FOUND

Resource not found.

**HTTP Status:** 404

**Resolution:**
- Verify resource ID
- Check resource exists
- Verify URL path

#### CONFLICT_ERROR

Resource conflict.

**HTTP Status:** 409

**Common scenarios:**
- Duplicate resource creation
- Concurrent modification
- State transition conflict

**Resolution:**
- Check resource state
- Retry with updated data
- Use conditional requests (ETag)

### Rate Limiting

#### RATE_LIMIT_EXCEEDED

Rate limit exceeded.

**HTTP Status:** 429

**Resolution:**
- Wait for rate limit reset
- Check `Retry-After` header
- Implement exponential backoff
- Reduce request frequency

### Server Errors

#### INTERNAL_ERROR

Internal server error.

**HTTP Status:** 500

**Resolution:**
- Retry request with exponential backoff
- Check service status
- Contact support with request_id

#### SERVICE_UNAVAILABLE

Service unavailable.

**HTTP Status:** 502, 503

**Resolution:**
- Retry request with exponential backoff
- Check service status page
- Wait for service recovery

---

## Field-Level Errors

Field-level errors provide detailed validation information:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "http_status": 400,
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        },
        {
          "field": "age",
          "message": "Must be a positive integer",
          "code": "VALIDATION_ERROR"
        }
      ],
      "non_field_errors": [
        "Email and username cannot be the same"
      ]
    }
  }
}
```

### Field Error Codes

- `VALIDATION_ERROR`: General validation error
- `REQUIRED`: Required field missing
- `INVALID_FORMAT`: Invalid field format
- `INVALID_VALUE`: Invalid field value
- `TOO_LONG`: Field value too long
- `TOO_SHORT`: Field value too short
- `UNIQUE_CONSTRAINT`: Duplicate value

---

## Error Handling Examples

### Python Example

```python
import requests
from requests.exceptions import RequestException

def handle_api_error(response):
    """Handle API error responses."""
    if response.status_code >= 400:
        error_data = response.json()
        error = error_data.get('error', {})
        
        error_code = error.get('code')
        error_message = error.get('message')
        request_id = error.get('request_id')
        
        # Log error for debugging
        print(f"Error {error_code}: {error_message}")
        print(f"Request ID: {request_id}")
        
        # Handle specific error codes
        if error_code == 'RATE_LIMIT_EXCEEDED':
            retry_after = response.headers.get('Retry-After', 60)
            print(f"Rate limited. Retry after {retry_after} seconds")
            return None
        
        # Handle field errors
        if 'details' in error and 'field_errors' in error['details']:
            for field_error in error['details']['field_errors']:
                print(f"Field {field_error['field']}: {field_error['message']}")
        
        return None
    
    return response.json()

# Usage
try:
    response = requests.get('https://api.example.com/api/v1/contracts/')
    result = handle_api_error(response)
except RequestException as e:
    print(f"Request failed: {e}")
```

### JavaScript Example

```javascript
async function handleApiError(response) {
    if (!response.ok) {
        const errorData = await response.json();
        const error = errorData.error;
        
        console.error(`Error ${error.code}: ${error.message}`);
        console.error(`Request ID: ${error.request_id}`);
        
        // Handle specific error codes
        if (error.code === 'RATE_LIMIT_EXCEEDED') {
            const retryAfter = response.headers.get('Retry-After') || 60;
            console.log(`Rate limited. Retry after ${retryAfter} seconds`);
            return null;
        }
        
        // Handle field errors
        if (error.details && error.details.field_errors) {
            error.details.field_errors.forEach(fieldError => {
                console.error(`Field ${fieldError.field}: ${fieldError.message}`);
            });
        }
        
        return null;
    }
    
    return await response.json();
}

// Usage
try {
    const response = await fetch('https://api.example.com/api/v1/contracts/');
    const result = await handleApiError(response);
} catch (error) {
    console.error(`Request failed: ${error}`);
}
```

### Retry Logic Example

```python
import time
import requests

def retry_with_backoff(func, max_retries=3, backoff_factor=2):
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = func()
            if response.status_code < 500:
                return response
            
            # Only retry on server errors
            if response.status_code >= 500:
                wait_time = backoff_factor ** attempt
                time.sleep(wait_time)
                continue
            
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff_factor ** attempt
            time.sleep(wait_time)
    
    return None
```

---

## Best Practices

1. **Always check status codes**: Verify HTTP status before processing response
2. **Log request IDs**: Include request_id in error logs for support
3. **Handle field errors**: Display field-specific errors to users
4. **Implement retry logic**: Retry on transient errors (5xx) with backoff
5. **Respect rate limits**: Implement rate limit handling with Retry-After
6. **User-friendly messages**: Display error.message to users
7. **Debug details**: Log error.details for debugging

---

## Support

For additional support:
- Check [API Documentation](./API_DOCUMENTATION.md)
- Review [API Best Practices](./API_BEST_PRACTICES.md)
- Contact support with request_id from error response


---

# Error Handling Guide

Comprehensive guide for error handling including standardized error responses, enhanced error logging, Sentry integration, and error recovery mechanisms.

## Table of Contents

1. [Overview](#overview)
2. [Standardized Error Responses](#standardized-error-responses)
3. [Error Logging](#error-logging)
4. [Error Tracking (Sentry)](#error-tracking-sentry)
5. [Error Recovery](#error-recovery)
6. [Integration Examples](#integration-examples)
7. [Best Practices](#best-practices)

---

## Overview

The error handling module provides comprehensive tools for handling errors:

- **Standardized Error Responses**: Consistent error response format across all endpoints
- **Enhanced Error Logging**: Structured logging with full context
- **Error Tracking (Sentry)**: Automatic error tracking and monitoring
- **Error Recovery**: Retry logic and circuit breakers

### Module Location

All error handling functionality is in `hub.apps.core.error_handling`:

- `error_responses.py`: Standardized error response formatting
- `error_logging.py`: Enhanced error logging
- `error_tracking.py`: Sentry integration
- `error_recovery.py`: Retry logic and circuit breakers
- `middleware.py`: Error handling middleware

---

## Standardized Error Responses

### Overview

All error responses follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

### Usage

**ErrorResponse Class:**

```python
from hub.apps.core.error_handling.error_responses import ErrorResponse

error = ErrorResponse(
    code="VALIDATION_ERROR",
    message="Invalid input",
    http_status=400,
    details={"field": "email", "message": "Invalid email format"}
)

response = error.to_response()
return response
```

**ErrorResponseBuilder (Fluent Interface):**

```python
from hub.apps.core.error_handling.error_responses import ErrorResponseBuilder

error = (
    ErrorResponseBuilder()
    .code("VALIDATION_ERROR")
    .message("Validation failed")
    .http_status(400)
    .field_error("email", "Invalid email format")
    .field_error("password", "Password too short", "PASSWORD_TOO_SHORT")
    .request_id(request_id)
    .build()
)

return error.to_response()
```

**format_error_response Function:**

```python
from hub.apps.core.error_handling.error_responses import format_error_response

try:
    # Operation that might fail
    result = process_data(data)
except ValueError as e:
    return format_error_response(
        exception=e,
        code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
    )
```

**In DRF Views:**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from hub.apps.core.error_handling.error_responses import format_error_response

class ContractViewSet(APIView):
    def create(self, request):
        try:
            contract = ContractService.create_contract(
                tenant_id=request.user.tenant_id,
                data=request.data
            )
            return Response({"id": str(contract.id)}, status=201)
        except ValidationError as e:
            return format_error_response(
                exception=e,
                code="VALIDATION_ERROR",
                http_status=400,
                request_id=request.id,
            )
```

### Error Codes

Standard error codes are defined in `hub.apps.api.standards.error_codes.StandardErrorCodes`:

- **Validation errors (400)**: `VALIDATION_ERROR`, `VALIDATION_FAILED`, `INVALID_INPUT`
- **Authentication errors (401)**: `AUTH_UNAUTHORIZED`, `AUTH_TOKEN_EXPIRED`
- **Authorization errors (403)**: `AUTH_FORBIDDEN`, `PERMISSION_DENIED`
- **Not found errors (404)**: `NOT_FOUND`, `RESOURCE_NOT_FOUND`
- **Conflict errors (409)**: `CONFLICT_ERROR`, `RESOURCE_CONFLICT`
- **Rate limiting (429)**: `RATE_LIMIT_EXCEEDED`
- **Server errors (500)**: `INTERNAL_ERROR`, `SERVER_ERROR`

---

## Error Logging

### Overview

Enhanced error logging provides structured logging with full context for debugging and monitoring.

### Usage

**ErrorLogger Class:**

```python
from hub.apps.core.error_handling.error_logging import ErrorLogger

logger = ErrorLogger()

try:
    # Operation that might fail
    result = process_data(data)
except ValueError as e:
    logger.log_error(
        error=e,
        error_code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
        tenant_id=str(request.user.tenant_id),
        user_id=str(request.user.id),
        additional_context={
            "operation": "create_contract",
            "data_size": len(data),
        },
        level="error",
    )
```

**Convenience Functions:**

```python
from hub.apps.core.error_handling.error_logging import log_error, log_exception

try:
    result = process_data(data)
except ValueError as e:
    log_error(
        error=e,
        error_code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
    )
```

**Specialized Logging Methods:**

```python
logger = ErrorLogger()

# Log validation error
logger.log_validation_error(
    field="email",
    message="Invalid email format",
    value="invalid-email",
    request_id=request.id,
    tenant_id=str(request.user.tenant_id),
)

# Log permission error
logger.log_permission_error(
    resource="asset",
    action="delete",
    user_id=str(request.user.id),
    tenant_id=str(request.user.tenant_id),
    request_id=request.id,
)

# Log not found error
logger.log_not_found_error(
    resource_type="asset",
    resource_id="asset-id",
    request_id=request.id,
    tenant_id=str(request.user.tenant_id),
)
```

### Log Context

All error logs include:
- **Error type**: Exception class name
- **Error code**: Machine-readable error code
- **Error message**: Human-readable message
- **Request ID**: Unique request identifier
- **Tenant ID**: Tenant identifier (if available)
- **User ID**: User identifier (if available)
- **Traceback**: Full stack trace (for errors)
- **Additional context**: Custom context fields

---

## Error Tracking (Sentry)

### Overview

Sentry integration provides automatic error tracking and monitoring with:
- Automatic exception capture
- User and tenant context
- PII redaction
- Performance monitoring
- Release tracking

### Setup

**1. Install Sentry SDK:**

```bash
pip install sentry-sdk
```

**2. Configure Environment Variables:**

```bash
export SENTRY_DSN="https://your-sentry-dsn@sentry.io/project-id"
export ENVIRONMENT="production"  # or "development", "staging"
export RELEASE_VERSION="1.0.0"  # Optional: release version
export SENTRY_TRACES_SAMPLE_RATE="0.1"  # Optional: trace sampling rate (0.0-1.0)
```

**3. Sentry is automatically initialized** when `ErrorTracker` is first used.

### Usage

**Automatic Tracking:**

Errors are automatically tracked in Sentry through:
- Exception handler integration (already configured)
- Error handling middleware (optional)

**Manual Tracking:**

```python
from hub.apps.core.error_handling.error_tracking import track_error, track_exception

try:
    result = process_data(data)
except ValueError as e:
    track_error(
        error=e,
        error_code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
        tenant_id=str(request.user.tenant_id),
        user_id=str(request.user.id),
        context={
            "operation": "create_contract",
            "data_size": len(data),
        },
    )
```

**Set User Context:**

```python
from hub.apps.core.error_handling.error_tracking import get_error_tracker

tracker = get_error_tracker()
tracker.set_user(user_id=str(request.user.id))
tracker.set_tenant(tenant_id=str(request.user.tenant_id))
```

**Track Messages:**

```python
from hub.apps.core.error_handling.error_tracking import get_error_tracker

tracker = get_error_tracker()
tracker.track_message(
    "Important event occurred",
    level="warning",
    context={"event_type": "data_quality_check"},
)
```

### PII Protection

Sentry automatically redacts PII:
- Email addresses
- Usernames
- Passwords
- Tokens
- API keys
- Other sensitive fields

### Configuration

Sentry is configured with:
- **Django Integration**: Automatic Django exception capture
- **Logging Integration**: Structured log capture
- **Redis Integration**: Redis error tracking
- **Trace Sampling**: Configurable performance monitoring
- **PII Redaction**: Automatic sensitive data removal

---

## Error Recovery

### Overview

Error recovery mechanisms provide resilience patterns:
- **Retry Logic**: Automatic retry with backoff strategies
- **Circuit Breakers**: Prevent cascading failures
- **Error Classification**: Determine if errors are retryable

### Retry Logic

**@with_retry Decorator:**

```python
from hub.apps.core.error_handling.error_recovery import (
    with_retry,
    RetryStrategy,
)

@with_retry(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=1.0,
    max_delay=60.0,
)
def fetch_external_data(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

**Retry Strategies:**

- **EXPONENTIAL_BACKOFF**: Delay = base_delay * (2 ^ attempt)
- **LINEAR_BACKOFF**: Delay = base_delay * (attempt + 1)
- **FIXED_DELAY**: Delay = base_delay (constant)
- **NO_RETRY**: No retry

**Custom Retryable Exceptions:**

```python
@with_retry(
    max_attempts=3,
    retryable_exceptions=[ConnectionError, TimeoutError],
    non_retryable_exceptions=[ValueError, TypeError],
)
def unreliable_operation():
    # Only retries on ConnectionError or TimeoutError
    pass
```

**Retry Callback:**

```python
def on_retry(exc, attempt):
    logger.warning(f"Retry attempt {attempt} after {exc}")

@with_retry(max_attempts=3, on_retry=on_retry)
def flaky_operation():
    pass
```

### Circuit Breakers

**@with_circuit_breaker Decorator:**

```python
from hub.apps.core.error_handling.error_recovery import with_circuit_breaker

@with_circuit_breaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
)
def call_external_service():
    # Automatically protected by circuit breaker
    response = requests.get("https://external-api.com/data")
    response.raise_for_status()
    return response.json()
```

**Circuit Breaker States:**

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures, requests rejected immediately
- **HALF_OPEN**: Testing if service recovered, allows limited requests

**Manual Circuit Breaker:**

```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker

cb = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="external_api",
)

def call_external_service():
    return cb.call(lambda: requests.get("https://external-api.com/data"))
```

**Circuit Breaker Behavior:**

1. **CLOSED**: Requests pass through, failures counted
2. **After threshold failures**: Transitions to OPEN
3. **OPEN**: Requests rejected with `CircuitBreakerOpenError`
4. **After timeout**: Transitions to HALF_OPEN
5. **HALF_OPEN**: Allows requests, counts successes/failures
6. **After success threshold**: Transitions to CLOSED
7. **On failure in HALF_OPEN**: Transitions back to OPEN

### Error Classification

**Determine if Error is Retryable:**

```python
from hub.apps.core.error_handling.error_recovery import ErrorRecovery

try:
    result = unreliable_operation()
except Exception as e:
    if ErrorRecovery.should_retry(e):
        # Retry logic
        pass
    else:
        # Don't retry
        raise
```

**Default Retryable Exceptions:**
- `ConnectionError`
- `TimeoutError`
- `OSError` (network errors)

**Default Non-Retryable Exceptions:**
- `ValueError`
- `TypeError`
- `AttributeError`

---

## Integration Examples

### Complete Example: API View with Error Handling

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from hub.apps.core.error_handling.error_responses import format_error_response
from hub.apps.core.error_handling.error_logging import log_error
from hub.apps.core.error_handling.error_tracking import track_error
from hub.apps.core.error_handling.error_recovery import with_retry, RetryStrategy

class ContractViewSet(APIView):
    @with_retry(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
    def create(self, request):
        try:
            # Validate input
            validated_data = validate_contract_data(request.data)
            
            # Create contract
            contract = ContractService.create_contract(
                tenant_id=request.user.tenant_id,
                data=validated_data
            )
            
            return Response({"id": str(contract.id)}, status=201)
            
        except ValidationError as e:
            # Log and track error
            log_error(
                error=e,
                error_code="VALIDATION_ERROR",
                message="Contract validation failed",
                http_status=400,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
            )
            
            track_error(
                error=e,
                error_code="VALIDATION_ERROR",
                message="Contract validation failed",
                http_status=400,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
            )
            
            # Return standardized error response
            return format_error_response(
                exception=e,
                code="VALIDATION_ERROR",
                message="Contract validation failed",
                http_status=400,
                request_id=request.id,
            )
            
        except Exception as e:
            # Log and track unexpected errors
            log_error(
                error=e,
                error_code="INTERNAL_ERROR",
                message="Internal server error",
                http_status=500,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
                level="critical",
            )
            
            track_error(
                error=e,
                error_code="INTERNAL_ERROR",
                message="Internal server error",
                http_status=500,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
                level="critical",
            )
            
            # Return generic error (don't expose internal details)
            return format_error_response(
                code="INTERNAL_ERROR",
                message="Internal server error",
                http_status=500,
                request_id=request.id,
            )
```

### Example: Service with Circuit Breaker

```python
from hub.apps.core.error_handling.error_recovery import with_circuit_breaker
from hub.apps.core.error_handling.error_logging import log_error

class ExternalAPIService:
    @with_circuit_breaker(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
        name="external_api",
    )
    def fetch_data(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log_error(
                error=e,
                error_code="EXTERNAL_API_ERROR",
                message="External API request failed",
                context={"url": url},
            )
            raise
```

### Example: Background Job with Retry

```python
from hub.apps.core.error_handling.error_recovery import with_retry, RetryStrategy

@with_retry(
    max_attempts=5,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=2.0,
    max_delay=300.0,  # 5 minutes max
)
def process_background_job(job_id):
    job = Job.objects.get(id=job_id)
    
    try:
        # Process job
        result = process_job(job)
        job.status = JobStatus.SUCCEEDED
        job.save()
        return result
    except TransientError as e:
        # Transient errors are retryable
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save()
        raise
    except PermanentError as e:
        # Permanent errors are not retryable
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save()
        raise
```

---

## Best Practices

### 1. Error Response Standardization

- **Always use standardized format**: Use `ErrorResponse` or `format_error_response`
- **Include request_id**: Always include request ID for correlation
- **Provide clear messages**: Use user-friendly error messages
- **Include details**: Add field-level errors and context when helpful
- **Don't expose internals**: Never expose stack traces or internal details

### 2. Error Logging

- **Log all errors**: Log every error with full context
- **Use appropriate levels**: Use `error` for errors, `warning` for recoverable issues, `critical` for system failures
- **Include context**: Always include request_id, tenant_id, user_id when available
- **Don't log PII**: PII is automatically redacted, but avoid logging sensitive data
- **Structured logging**: Use structured logging with consistent fields

### 3. Error Tracking (Sentry)

- **Set SENTRY_DSN**: Configure Sentry DSN in environment
- **Set user context**: Always set user and tenant context
- **Monitor error rates**: Set up alerts for high error rates
- **Review errors regularly**: Review Sentry dashboard for patterns
- **Use releases**: Tag errors with release versions

### 4. Error Recovery

- **Use retry for transient errors**: Retry network errors, timeouts, temporary failures
- **Don't retry permanent errors**: Don't retry validation errors, permission errors
- **Use circuit breakers for external services**: Protect against cascading failures
- **Set appropriate thresholds**: Configure failure thresholds based on service reliability
- **Monitor circuit breaker state**: Log circuit breaker state changes

### 5. Error Handling Patterns

- **Try-except blocks**: Use try-except for error handling
- **Specific exceptions**: Catch specific exceptions, not generic Exception
- **Log before raising**: Log errors before re-raising
- **Track in Sentry**: Track errors in Sentry for monitoring
- **Return standardized responses**: Always return standardized error responses

### 6. Performance Considerations

- **Async error handling**: Use async error handling for async operations
- **Non-blocking logging**: Error logging should not block request processing
- **Efficient retry logic**: Use appropriate backoff strategies to avoid overwhelming services
- **Circuit breaker timeouts**: Set appropriate timeouts for circuit breakers

---

## Ruff E722 (Bare Except)

Bare `except:` clauses are forbidden in production code. They catch `BaseException` (including `KeyboardInterrupt` and `SystemExit`), making programs hard to interrupt and hiding bugs.

- **Ruff rule:** E722 (bare except). Enabled in `pyproject.toml` under `[tool.ruff.lint]` select.
- **CI:** `ruff check .` runs in CI; any use of bare `except:` will fail the build.
- **Fix:** Use `except Exception as e:` and log with context, or catch specific exception types. See [EXCEPTION_HANDLING_AUDIT_PLAN.md](./EXCEPTION_HANDLING_AUDIT_PLAN.md) for patterns.

---

## Summary

Error handling ensures:

1. ✅ **Standardized Responses**: Consistent error format across all endpoints
2. ✅ **Comprehensive Logging**: Full context for debugging and monitoring
3. ✅ **Error Tracking**: Automatic error tracking with Sentry
4. ✅ **Error Recovery**: Retry logic and circuit breakers for resilience

By following these patterns, we ensure:
- **Consistency**: All errors follow the same format
- **Observability**: All errors are logged and tracked
- **Resilience**: Automatic recovery from transient failures
- **Debugging**: Full context for troubleshooting


---

## Phase 117+ API Endpoints (Added)

### ML Model Management

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/ml/models/{id}/deploy/` | Deploy trained model (TRAINED→DEPLOYED) | JWT/API Key |
| `POST` | `/api/v1/ml/models/{id}/undeploy/` | Undeploy model (DEPLOYED→TRAINED) | JWT/API Key |
| `POST` | `/api/v1/ml/models/{id}/deploy-version/` | Atomic version switch (undeploy current + deploy target) | JWT/API Key |
| `POST` | `/api/v1/ml/models/{id}/rollback/` | Rollback to previous version | JWT/API Key |
| `POST` | `/api/v1/ml/models/{id}/publish/` | Publish model to marketplace as listing | JWT/API Key |
| `GET` | `/api/v1/ml/models/{id}/lineage/` | Get model lineage edges (dataset→model→asset) | JWT/API Key |
| `POST` | `/api/v1/ml/models/{id}/link-dataset/` | Link model to training/validation/test dataset | JWT/API Key |

### ML Inference

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/ml/inference/predict/` | Run inference on deployed model | JWT/API Key |
| `GET` | `/api/v1/ml/inference/deployments/` | List deployed models | JWT/API Key |
| `GET` | `/api/v1/ml/inference/deployments/{id}/` | Get deployment details | JWT/API Key |
| `GET` | `/api/v1/ml/inference/metrics/{id}/` | Get inference metrics | JWT/API Key |

### Transformation Pipeline

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/transformation/pipelines/` | List transformation pipelines | JWT/API Key |
| `POST` | `/api/v1/transformation/pipelines/` | Create pipeline | JWT/API Key |
| `GET` | `/api/v1/transformation/pipelines/{id}/` | Get pipeline details | JWT/API Key |
| `PATCH` | `/api/v1/transformation/pipelines/{id}/` | Update pipeline | JWT/API Key |
| `DELETE` | `/api/v1/transformation/pipelines/{id}/` | Delete pipeline | JWT/API Key |
| `POST` | `/api/v1/transformation/pipelines/{id}/validate/` | Validate pipeline DAG | JWT/API Key |
| `POST` | `/api/v1/transformation/pipelines/{id}/runs/` | Submit pipeline run | JWT/API Key |
| `GET` | `/api/v1/transformation/pipelines/{id}/runs/` | List pipeline runs | JWT/API Key |
| `GET` | `/api/v1/transformation/pipelines/{id}/runs/{run_id}/` | Get run details | JWT/API Key |
| `POST` | `/api/v1/transformation/pipelines/{id}/runs/{run_id}/cancel/` | Cancel running pipeline | JWT/API Key |

### Billing & Administration

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/billing/refunds/` | Process refund (admin-only) (B3) | Admin JWT |
| `GET` | `/api/v1/billing/subscription/current/` | Get current subscription | JWT/API Key |
| `GET` | `/api/v1/billing/invoices/` | List invoices | JWT/API Key |
| `GET` | `/api/v1/billing/plans/` | List available plans | JWT/API Key |
| `POST` | `/api/v1/billing/subscription/current/change-plan/` | Change subscription plan | JWT/API Key |

### BaaS Platform

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/baas/dashboard/` | Developer portal dashboard (P5) | API Key |
| `GET` | `/api/v1/baas/api-keys/` | List API keys | JWT/API Key |
| `POST` | `/api/v1/baas/api-keys/` | Create API key | JWT/API Key |
| `GET` | `/api/v1/baas/usage/` | Get usage statistics | API Key |
| `GET` | `/api/v1/baas/docs/` | Developer documentation | API Key |
| `GET` | `/api/v1/baas/openapi-schema/` | OpenAPI schema | API Key |

### Virtualization

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/virtualization/virtual-datasets/{id}/query/` | Execute virtual dataset query | JWT/API Key |
| `GET` | `/api/v1/virtualization/virtual-datasets/{id}/query/{exec_id}/` | Get query execution results | JWT/API Key |
| `GET` | `/api/v1/virtualization/virtual-datasets/{id}/query/{exec_id}/results/` | Get paginated query results | JWT/API Key |

### Internal Worker APIs

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/contracts/{id}/generate-odps/` | Generate ODPS from hub-contract | Internal |
| `POST` | `/api/v1/contracts/products/` | Create ODPS product (async workflow) | JWT/API Key |
| `GET` | `/api/v1/contracts/products/workflows/{id}/status/` | Get product workflow status | JWT/API Key |
| `POST` | `/api/v1/compliance/runs/` | Trigger compliance scan | JWT/API Key |
| `POST` | `/api/v1/dq/runs/` | Trigger data quality run | JWT/API Key |

### Marketplace Integration

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/integrations/marketplace/connections/{id}/sync/` | Trigger marketplace sync | JWT/API Key |
| `GET` | `/api/v1/integrations/marketplace/connections/{id}/mappings/` | List field mappings | JWT/API Key |
| `POST` | `/api/v1/marketplace/listings/` | Create marketplace listing (Integration-2) | JWT/API Key |
| `POST` | `/api/v1/marketplace/listings/{id}/publish/` | Publish listing | JWT/API Key |
