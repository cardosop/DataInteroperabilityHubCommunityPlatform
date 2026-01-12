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

#### Assets
- `GET /api/v1/assets/` - List assets
- `POST /api/v1/assets/` - Create asset
- `GET /api/v1/assets/{id}/` - Get asset
- `PUT /api/v1/assets/{id}/` - Update asset
- `DELETE /api/v1/assets/{id}/` - Delete asset
- `POST /api/v1/assets/{id}/datasets/` - Attach dataset
- `POST /api/v1/assets/{id}/contracts/` - Attach contract
- `POST /api/v1/assets/{id}/activate/` - Activate asset

#### Datasets
- `GET /api/v1/datasets/` - List datasets
- `POST /api/v1/datasets/` - Create dataset
- `GET /api/v1/datasets/{id}/` - Get dataset
- `PUT /api/v1/datasets/{id}/` - Update dataset
- `DELETE /api/v1/datasets/{id}/` - Delete dataset

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
- `GET /api/v1/marketplace/listings/` - List marketplace listings
- `POST /api/v1/marketplace/listings/` - Create listing
- `GET /api/v1/marketplace/listings/{id}/` - Get listing
- `POST /api/v1/marketplace/orders/` - Create order
- `GET /api/v1/marketplace/orders/{id}/` - Get order

#### Governance
- `GET /api/v1/governance/access-requests/` - List access requests
- `POST /api/v1/governance/access-requests/` - Create access request
- `GET /api/v1/governance/access-requests/{id}/` - Get access request
- `POST /api/v1/governance/access-requests/{id}/approve/` - Approve request
- `POST /api/v1/governance/access-requests/{id}/reject/` - Reject request

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
- `POST /api/v1/auth/login/` - Login (get JWT token)
- `POST /api/v1/auth/logout/` - Logout
- `POST /api/v1/auth/refresh/` - Refresh JWT token
- `POST /api/v1/auth/password-reset/` - Request password reset
- `POST /api/v1/auth/password-reset/confirm/` - Confirm password reset

#### Tenants
- `GET /api/v1/tenants/` - List tenants
- `POST /api/v1/tenants/` - Create tenant
- `GET /api/v1/tenants/{id}/` - Get tenant
- `PUT /api/v1/tenants/{id}/` - Update tenant

#### Users
- `GET /api/v1/users/` - List users
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/{id}/` - Get user
- `PUT /api/v1/users/{id}/` - Update user

### Complete Endpoint Reference

For detailed endpoint documentation with request/response examples, see:
- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md) - Complete endpoint documentation

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

