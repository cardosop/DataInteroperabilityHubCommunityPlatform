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

