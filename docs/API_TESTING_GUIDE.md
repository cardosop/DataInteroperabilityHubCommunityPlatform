# API Testing Guide

Comprehensive guide for testing the Data Interoperability Hub API using various tools and methods.

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Authentication](#authentication)
4. [Testing Tools](#testing-tools)
5. [Test Scenarios](#test-scenarios)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

This guide provides comprehensive instructions for testing the Data Interoperability Hub API. The API follows RESTful principles and uses OpenAPI 3.0 specification for documentation.

### API Base URLs

- **Production**: `https://api.datahub.example.com/api/v1`
- **Staging**: `https://staging-api.datahub.example.com/api/v1`
- **Local Development**: `http://localhost:8000/api/v1`

### API Versioning

The API uses URL-based versioning. Current version: **v1**

---

## Getting Started

### Prerequisites

- API access credentials (email/password or API key)
- HTTP client tool (curl, Postman, Insomnia, etc.)
- Understanding of REST API principles
- Basic knowledge of JSON

### Quick Start

1. **Get Authentication Token**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "your-password"}'
   ```

2. **Use Token in Requests**:
   ```bash
   curl -X GET http://localhost:8000/api/v1/contracts/ \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
   ```

---

## Authentication

### JWT Bearer Token Authentication

**Step 1: Login**

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

**Step 2: Use Token**

Include the token in the `Authorization` header for all subsequent requests:

```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Step 3: Refresh Token (when access token expires)**

```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### API Key Authentication

For service-to-service authentication, use API keys:

```bash
Authorization: ApiKey your-api-key-here
```

---

## Testing Tools

### 1. Swagger UI (Interactive Documentation)

**URL**: `http://localhost:8000/api-docs/`

Swagger UI provides an interactive interface to test all API endpoints directly from your browser.

**Features:**
- Try out endpoints with real requests
- See request/response examples
- View schema definitions
- Test authentication

**Usage:**
1. Navigate to `/api-docs/` in your browser
2. Click "Authorize" button to set authentication token
3. Expand any endpoint to see details
4. Click "Try it out" to test the endpoint
5. Fill in parameters and click "Execute"

### 2. Postman

**Import Collection:**

Generate Postman collection from OpenAPI spec:

```bash
# From running API server
python scripts/generate-postman-collection.py \
  --spec-url http://localhost:8000/api-docs/openapi.json \
  --base-url http://localhost:8000 \
  --output postman_collection.json

# From OpenAPI file
python scripts/generate-postman-collection.py \
  --spec-file api/openapi-hub-v1.yaml \
  --base-url http://localhost:8000 \
  --output postman_collection.json
```

**Import into Postman:**
1. Open Postman
2. Click "Import" button
3. Select `postman_collection.json`
4. Collection will be imported with all endpoints organized by tags

**Set Up Environment Variables:**
1. Create new environment in Postman
2. Add variables:
   - `base_url`: `http://localhost:8000`
   - `api_version`: `v1`
   - `access_token`: (will be set automatically after login)
   - `refresh_token`: (will be set automatically after login)

**Use Authentication:**
1. Run "Authentication > Login" request
2. Token will be automatically saved to `access_token` variable
3. All other requests will use this token

### 3. cURL

**Basic cURL Examples:**

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your-password"}'

# Get contracts (with token)
curl -X GET http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Create contract
curl -X POST http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"test-contract\"}",
    "original_format": "JSON"
  }'
```

### 4. Python Requests

**Example Script:**

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Login
response = requests.post(
    f"{BASE_URL}/auth/login/",
    json={"email": "user@example.com", "password": "your-password"}
)
tokens = response.json()
access_token = tokens["access_token"]

# Get contracts
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"{BASE_URL}/contracts/", headers=headers)
contracts = response.json()
print(contracts)
```

### 5. JavaScript/TypeScript (Fetch API)

**Example:**

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';

// Login
const loginResponse = await fetch(`${BASE_URL}/auth/login/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'your-password'
  })
});
const tokens = await loginResponse.json();
const accessToken = tokens.access_token;

// Get contracts
const contractsResponse = await fetch(`${BASE_URL}/contracts/`, {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const contracts = await contractsResponse.json();
console.log(contracts);
```

---

## Test Scenarios

### 1. Authentication Tests

**Test Login:**
- ✅ Valid credentials → 200 OK with tokens
- ✅ Invalid credentials → 401 Unauthorized
- ✅ Missing email → 400 Bad Request
- ✅ Missing password → 400 Bad Request

**Test Token Refresh:**
- ✅ Valid refresh token → 200 OK with new access token
- ✅ Invalid refresh token → 401 Unauthorized
- ✅ Expired refresh token → 401 Unauthorized

**Test Token Usage:**
- ✅ Valid token → Request succeeds
- ✅ Invalid token → 401 Unauthorized
- ✅ Expired token → 401 Unauthorized
- ✅ Missing token → 401 Unauthorized

### 2. Contract Management Tests

**Create Contract:**
```bash
POST /api/v1/contracts/
Authorization: Bearer {token}
Content-Type: application/json

{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"test-contract\",\"name\":\"Test Contract\",\"schema\":{\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}}",
  "original_format": "JSON"
}
```

**Expected Responses:**
- ✅ Valid contract → 201 Created
- ✅ Invalid JSON → 400 Bad Request
- ✅ Missing required fields → 400 Bad Request
- ✅ Duplicate contract ID → 400 Bad Request

**List Contracts:**
```bash
GET /api/v1/contracts/?page=1&page_size=20
Authorization: Bearer {token}
```

**Expected Responses:**
- ✅ Valid request → 200 OK with paginated results
- ✅ Invalid page number → 400 Bad Request
- ✅ Invalid page size → 400 Bad Request

**Get Contract:**
```bash
GET /api/v1/contracts/{contract_id}/
Authorization: Bearer {token}
```

**Expected Responses:**
- ✅ Contract exists → 200 OK
- ✅ Contract not found → 404 Not Found
- ✅ Cross-tenant access → 404 Not Found (tenant isolation)

**Update Contract:**
```bash
PATCH /api/v1/contracts/{contract_id}/
Authorization: Bearer {token}
Content-Type: application/json

{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"test-contract\",\"name\":\"Updated Contract\"}"
}
```

**Expected Responses:**
- ✅ Valid update → 200 OK
- ✅ Invalid data → 400 Bad Request
- ✅ Contract not found → 404 Not Found

### 3. Asset Management Tests

**Create Asset:**
```bash
POST /api/v1/assets/
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Test Asset",
  "description": "Test asset description",
  "asset_type": "DATASET",
  "domain": "analytics"
}
```

**Expected Responses:**
- ✅ Valid asset → 201 Created
- ✅ Missing required fields → 400 Bad Request
- ✅ Invalid asset type → 400 Bad Request

### 4. Error Handling Tests

**Test Error Responses:**

All error responses follow this format:
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
          "code": "ERROR_CODE"
        }
      ]
    }
  }
}
```

**Test Scenarios:**
- ✅ 400 Bad Request - Validation errors
- ✅ 401 Unauthorized - Authentication required
- ✅ 403 Forbidden - Insufficient permissions
- ✅ 404 Not Found - Resource not found
- ✅ 429 Too Many Requests - Rate limit exceeded
- ✅ 500 Internal Server Error - Server error

### 5. Pagination Tests

**Test Pagination:**
```bash
GET /api/v1/contracts/?page=1&page_size=10
GET /api/v1/contracts/?page=2&page_size=10
```

**Expected Response:**
```json
{
  "count": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10,
  "has_next": true,
  "has_previous": false,
  "results": [...]
}
```

**Test Scenarios:**
- ✅ First page → `has_previous: false`
- ✅ Middle page → `has_next: true, has_previous: true`
- ✅ Last page → `has_next: false`
- ✅ Invalid page → 400 Bad Request
- ✅ Page size > max → 400 Bad Request

### 6. Filtering and Sorting Tests

**Test Filtering:**
```bash
GET /api/v1/contracts/?status=ACTIVE&domain=analytics
```

**Test Sorting:**
```bash
GET /api/v1/contracts/?ordering=created_at
GET /api/v1/contracts/?ordering=-created_at
```

**Test Scenarios:**
- ✅ Single filter → Returns filtered results
- ✅ Multiple filters → Returns results matching all filters
- ✅ Invalid filter value → 400 Bad Request
- ✅ Sort ascending → Results sorted ascending
- ✅ Sort descending → Results sorted descending

### 7. Multi-Tenant Isolation Tests

**Test Tenant Isolation:**
1. Create contract as Tenant A
2. Try to access contract as Tenant B
3. Expected: 404 Not Found (tenant isolation enforced)

**Test Scenarios:**
- ✅ Tenant A cannot access Tenant B's resources
- ✅ List operations only return tenant's own resources
- ✅ Cross-tenant access returns 404

---

## Best Practices

### 1. Authentication

- **Always use HTTPS in production** - Never send tokens over unencrypted connections
- **Store tokens securely** - Don't commit tokens to version control
- **Handle token expiration** - Implement automatic token refresh
- **Use environment variables** - Store base URLs and credentials in environment variables

### 2. Error Handling

- **Check response status codes** - Always verify status codes before processing responses
- **Parse error responses** - Use structured error format for user-friendly messages
- **Log request IDs** - Include request IDs in error logs for debugging
- **Implement retry logic** - Retry transient failures (5xx errors) with exponential backoff

### 3. Testing

- **Test happy paths first** - Verify basic functionality before edge cases
- **Test error scenarios** - Verify proper error handling
- **Test edge cases** - Test boundary conditions (empty lists, null values, etc.)
- **Test authentication** - Verify authentication and authorization
- **Test tenant isolation** - Ensure multi-tenant security

### 4. Performance

- **Use pagination** - Always paginate large result sets
- **Limit page size** - Use reasonable page sizes (10-50 items)
- **Cache tokens** - Cache access tokens to reduce authentication requests
- **Batch operations** - Use batch endpoints when available

### 5. Security

- **Never log tokens** - Don't log authentication tokens or sensitive data
- **Validate input** - Always validate input before sending requests
- **Use HTTPS** - Always use HTTPS in production
- **Follow principle of least privilege** - Use tokens with minimum required permissions

---

## Troubleshooting

### Common Issues

**1. 401 Unauthorized**
- **Cause**: Missing or invalid authentication token
- **Solution**: 
  - Verify token is included in `Authorization` header
  - Check token hasn't expired (refresh if needed)
  - Verify token format: `Bearer {token}`

**2. 403 Forbidden**
- **Cause**: Insufficient permissions
- **Solution**: 
  - Verify user has required role/permissions
  - Check if resource belongs to user's tenant

**3. 404 Not Found**
- **Cause**: Resource doesn't exist or belongs to different tenant
- **Solution**: 
  - Verify resource ID is correct
  - Check if resource belongs to your tenant
  - Verify endpoint URL is correct

**4. 400 Bad Request**
- **Cause**: Invalid request data
- **Solution**: 
  - Check request body format (must be valid JSON)
  - Verify required fields are present
  - Check field types match schema
  - Review error response for specific field errors

**5. 429 Too Many Requests**
- **Cause**: Rate limit exceeded
- **Solution**: 
  - Wait for rate limit window to reset
  - Check `Retry-After` header for wait time
  - Implement exponential backoff
  - Reduce request frequency

**6. 500 Internal Server Error**
- **Cause**: Server-side error
- **Solution**: 
  - Check server logs
  - Include request ID in support ticket
  - Retry request (may be transient error)

### Debugging Tips

**1. Enable Verbose Logging:**
```bash
curl -v -X GET http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer {token}"
```

**2. Check Response Headers:**
- `X-Request-ID`: Request identifier for debugging
- `X-RateLimit-Remaining`: Remaining rate limit
- `X-RateLimit-Reset`: Rate limit reset time

**3. Use Swagger UI:**
- Test endpoints interactively
- See request/response examples
- View schema definitions

**4. Review OpenAPI Spec:**
- Check endpoint documentation
- Verify request/response schemas
- Review error response formats

---

## Additional Resources

- **OpenAPI Specification**: `/api-docs/openapi.json`
- **Swagger UI**: `/api-docs/`
- **ReDoc**: `/api-docs/redoc/`
- **API Documentation**: `docs/API_DOCUMENTATION.md`
- **API Standards**: `docs/API_STANDARDS.md`
- **Error Codes**: `docs/API_ERROR_CODES.md`

---

## Support

For API support:
- **Email**: support@datahub.example.com
- **Documentation**: https://docs.datahub.example.com
- **Issue Tracker**: https://github.com/example/datahub/issues

