# API Documentation

Complete API documentation for the Interoperable Data Hub REST API v1.

## Table of Contents

1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [API Endpoints](#api-endpoints)
5. [Request/Response Format](#requestresponse-format)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [OpenAPI Schema](#openapi-schema)
9. [Interactive Documentation](#interactive-documentation)

---

## Overview

The Interoperable Data Hub provides a RESTful API (v1) for managing data assets, contracts, datasets, compliance, data quality, and marketplace operations.

**API Version**: v1  
**Content Type**: `application/json`  
**Character Encoding**: UTF-8

---

## Base URL

### Environments

- **Production**: `https://api.hub.example.com/api/v1`
- **Staging**: `https://api-staging.hub.example.com/api/v1`
- **Local Development**: `http://localhost:8000/api/v1`

### Versioning

The API uses URL-based versioning. The current version is `/api/v1`. Future versions will be `/api/v2`, `/api/v3`, etc.

---

## Authentication

The API uses JWT (JSON Web Tokens) for authentication.

### Getting an Access Token

```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Using the Access Token

Include the token in the `Authorization` header:

```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Refreshing the Token

```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### API Keys (Alternative)

For service-to-service authentication, API keys are supported:

```bash
Authorization: ApiKey your-api-key-here
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login/` | User login |
| POST | `/auth/refresh/` | Refresh access token |
| POST | `/auth/logout/` | User logout |
| POST | `/auth/register/` | User registration |

### Tenants

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tenants/` | List tenants |
| POST | `/tenants/` | Create tenant |
| GET | `/tenants/{id}/` | Get tenant details |
| PATCH | `/tenants/{id}/` | Update tenant |
| POST | `/tenants/{id}/suspend/` | Suspend tenant |
| POST | `/tenants/{id}/activate/` | Activate tenant |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/` | List users |
| POST | `/users/` | Create user |
| GET | `/users/{id}/` | Get user details |
| PATCH | `/users/{id}/` | Update user |
| DELETE | `/users/{id}/` | Delete user |
| POST | `/users/invite/` | Invite user |

### Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/files/` | List files |
| POST | `/files/` | Upload file |
| GET | `/files/{id}/` | Get file details |
| DELETE | `/files/{id}/` | Delete file |
| POST | `/files/{id}/download/` | Get download URL |

### Datasets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/datasets/` | List datasets |
| POST | `/datasets/` | Create dataset |
| GET | `/datasets/{id}/` | Get dataset details |
| PATCH | `/datasets/{id}/` | Update dataset |
| DELETE | `/datasets/{id}/` | Delete dataset |

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/assets/` | List assets |
| POST | `/assets/` | Create asset |
| GET | `/assets/{id}/` | Get asset details |
| PATCH | `/assets/{id}/` | Update asset |
| DELETE | `/assets/{id}/` | Delete asset |
| POST | `/assets/{id}/activate/` | Activate asset |
| POST | `/assets/{id}/contracts/` | Attach contract to asset |

### Contracts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contracts/` | List contracts |
| POST | `/contracts/` | Create contract |
| GET | `/contracts/{id}/` | Get contract details |
| PATCH | `/contracts/{id}/` | Update contract |
| DELETE | `/contracts/{id}/` | Delete contract |
| POST | `/contracts/{id}/validate/` | Validate contract |
| POST | `/contracts/{id}/activate/` | Activate contract |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs/` | List jobs |
| GET | `/jobs/{id}/` | Get job details |
| POST | `/jobs/{id}/cancel/` | Cancel job |

### Data Quality

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/dq/runs/` | Create DQ run |
| GET | `/dq/runs/{id}/` | Get DQ run details |
| GET | `/dq/runs/{id}/results/` | Get DQ run results |

### Compliance

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/compliance/scans/` | Create compliance scan |
| GET | `/compliance/scans/{id}/` | Get scan details |
| GET | `/compliance/scans/{id}/results/` | Get scan results |

### Semantic

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/semantic/context/` | Get JSON-LD context |
| GET | `/semantic/ontology/` | Get ontology |
| GET | `/semantic/uri/{resource_type}/{resource_id}/` | Resolve URI to JSON-LD |

### Marketplace

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/marketplace/listings/` | List marketplace listings |
| POST | `/marketplace/listings/` | Create listing |
| GET | `/marketplace/listings/{id}/` | Get listing details |
| POST | `/marketplace/orders/` | Create order |
| GET | `/marketplace/orders/{id}/` | Get order details |
| POST | `/marketplace/orders/{id}/approve/` | Approve order |

### Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/audit/events/` | List audit events |
| GET | `/audit/events/{id}/` | Get audit event details |
| GET | `/audit/events/export/` | Export audit events (CSV) |

---

## Request/Response Format

### Request Headers

All requests should include:

```
Content-Type: application/json
Authorization: Bearer <token>
Accept: application/json
```

### Request Body

Request bodies should be JSON:

```json
{
  "name": "My Asset",
  "description": "Asset description",
  "domain": "marketing"
}
```

### Response Format

Successful responses (2xx):

```json
{
  "id": "uuid",
  "name": "My Asset",
  "status": "ACTIVE",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

List responses include pagination:

```json
{
  "count": 100,
  "next": "https://api.hub.example.com/api/v1/assets/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field_name": ["Error detail for this field"]
    },
    "request_id": "unique-request-id"
  }
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 204 | No Content | Request succeeded, no content |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Common Error Codes

- `VALIDATION_ERROR` - Request validation failed
- `NOT_FOUND` - Resource not found
- `UNAUTHORIZED` - Authentication required
- `FORBIDDEN` - Insufficient permissions
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `INTERNAL_ERROR` - Internal server error

---

## Rate Limiting

The API enforces rate limits to ensure fair usage:

- **Authenticated users**: 1000 requests per hour
- **Unauthenticated users**: 100 requests per hour

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

When rate limit is exceeded, a `429 Too Many Requests` response is returned.

---

## OpenAPI Schema

The complete OpenAPI 3.0 schema is available at:

- **JSON**: `/api-docs/openapi.json`
- **Swagger UI**: `/api-docs/`
- **ReDoc**: `/api-docs/redoc/`

### Download Schema

```bash
curl https://api.hub.example.com/api-docs/openapi.json > openapi.json
```

### Schema Features

- Complete endpoint documentation
- Request/response schemas
- Authentication requirements
- Error responses
- Examples

---

## Interactive Documentation

### Swagger UI

Access interactive API documentation at `/api-docs/`:

- Try out endpoints directly in the browser
- View request/response examples
- Test authentication

### ReDoc

Access alternative documentation at `/api-docs/redoc/`:

- Clean, readable documentation
- Search functionality
- Code examples

---

## SDKs

Official SDKs are available:

- **Python**: `pip install datahub-interoperability`
- **JavaScript/TypeScript**: `npm install @datahub/interoperability-sdk`

See [SDK Documentation](./SDK_DOCUMENTATION.md) for details.

---

## Examples

### Create an Asset

```bash
curl -X POST https://api.hub.example.com/api/v1/assets/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Data",
    "description": "Customer information dataset",
    "domain": "marketing"
  }'
```

### List Assets with Filters

```bash
curl -X GET "https://api.hub.example.com/api/v1/assets/?status=ACTIVE&domain=marketing" \
  -H "Authorization: Bearer <token>"
```

### Upload a File

```bash
# 1. Initialize upload
curl -X POST https://api.hub.example.com/api/v1/files/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "data.csv",
    "size": 1024,
    "content_type": "text/csv"
  }'

# 2. Upload to pre-signed URL
curl -X PUT "<upload_url>" \
  -H "Content-Type: text/csv" \
  --data-binary @data.csv

# 3. Complete upload
curl -X POST "https://api.hub.example.com/api/v1/files/{file_id}/complete/" \
  -H "Authorization: Bearer <token>"
```

---

## Support

For API support:

- **Documentation**: https://docs.hub.example.com
- **Issues**: https://github.com/your-org/datainteroperabilityhub/issues
- **Email**: api-support@hub.example.com

---

## Changelog

### v1.0.0 (2025-01-15)

- Initial API release
- Authentication endpoints
- Tenant, User, File, Dataset, Asset, Contract management
- Marketplace operations
- Semantic layer endpoints
- Audit logging

---

**Last Updated**: 2025-01-15  
**API Version**: v1.0.0

