# API Usability Guide

Comprehensive guide for API usability, including discoverability, consistency, error messages, response times, and rate limiting.

## Table of Contents

1. [Overview](#overview)
2. [API Discoverability](#api-discoverability)
3. [API Consistency](#api-consistency)
4. [API Error Messages](#api-error-messages)
5. [API Response Times](#api-response-times)
6. [API Rate Limiting](#api-rate-limiting)
7. [Best Practices](#best-practices)
8. [Testing](#testing)

---

## Overview

API usability ensures that developers can easily discover, understand, and use the API effectively. This guide covers all aspects of API usability in the Data Interoperability Hub.

### Key Principles

1. **Discoverability**: APIs should be easy to find and understand
2. **Consistency**: APIs should follow consistent patterns
3. **Clarity**: Error messages should be clear and helpful
4. **Performance**: APIs should respond within acceptable timeframes
5. **Fair Usage**: Rate limiting prevents abuse while allowing legitimate use

---

## API Discoverability

### API Information Endpoint

The API provides an information endpoint that lists all available endpoints:

```bash
GET /api/v1/
```

**Response:**
```json
{
  "name": "Interoperable Data Hub API",
  "version": "1.0.0",
  "base_url": "/api/v1",
  "documentation": {
    "openapi": "/api-docs/openapi.json",
    "openapi_yaml": "/api/v1/openapi.yaml",
    "swagger": "/api-docs/",
    "redoc": "/api-docs/redoc/"
  },
  "endpoints": {
    "auth": "/api/v1/auth/",
    "assets": "/api/v1/assets/",
    "contracts": "/api/v1/contracts/",
    "datasets": "/api/v1/datasets/",
    "jobs": "/api/v1/jobs/",
    ...
  }
}
```

### OpenAPI Specification

The API provides complete OpenAPI 3.0 specifications:

- **JSON Format**: `/api/v1/openapi.json`
- **YAML Format**: `/api/v1/openapi.yaml`

**Features:**
- Complete endpoint documentation
- Request/response schemas
- Examples for all endpoints
- Error response schemas
- Authentication requirements

### Interactive Documentation

#### Swagger UI

Access Swagger UI at `/api-docs/` for interactive API exploration:

- Try out endpoints directly
- See request/response examples
- Test authentication
- View error responses

#### ReDoc

Access ReDoc at `/api-docs/redoc/` for clean, readable documentation:

- Beautiful documentation layout
- Complete API reference
- Search functionality
- Code examples

### Endpoint Discovery

All endpoints follow consistent URL patterns:

- **Base URL**: `/api/v1/`
- **Resource URLs**: `/api/v1/{resource}/`
- **Resource Detail**: `/api/v1/{resource}/{id}/`
- **Actions**: `/api/v1/{resource}/{id}/{action}/`

---

## API Consistency

### Response Formats

#### Success Responses

**Single Resource (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Resource Name",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**List Response (200 OK):**
```json
{
  "count": 100,
  "page": 1,
  "page_size": 50,
  "total_pages": 2,
  "next": "https://api.datahub.example.com/api/v1/resources/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Resource 1"
    }
  ]
}
```

**Created Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "New Resource",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**No Content (204 No Content):**
Empty response body for DELETE operations.

#### Error Responses

All errors follow a consistent format:

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

### Pagination

All list endpoints support pagination:

**Page-based Pagination:**
```bash
GET /api/v1/assets/?page=1&page_size=50
```

**Cursor-based Pagination:**
```bash
GET /api/v1/assets/?cursor=eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNVQxMDozMDowMFoifQ==&page_size=50
```

**Response:**
```json
{
  "count": 100,
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNVQxMDozMDowMFoifQ==",
  "previous_cursor": null,
  "page_size": 50,
  "results": [...]
}
```

### Filtering

Most list endpoints support filtering:

```bash
GET /api/v1/assets/?status=ACTIVE&domain=finance
```

**Supported Operators:**
- Exact match: `?field=value`
- Contains: `?field__contains=value`
- In: `?field__in=value1,value2`
- Range: `?field__gte=value&field__lte=value`
- Null: `?field__isnull=true`

### Sorting

Most list endpoints support sorting:

```bash
GET /api/v1/assets/?ordering=name,-created_at
```

- Prefix with `-` for descending order
- Multiple fields separated by commas

### Content Types

All API endpoints:
- Accept: `application/json`
- Return: `application/json`
- Use UTF-8 encoding

---

## API Error Messages

### Error Code Format

Error codes are machine-readable and follow these patterns:

- **Format**: UPPERCASE_WITH_UNDERSCORES
- **Examples**: `VALIDATION_ERROR`, `NOT_FOUND`, `RATE_LIMIT_EXCEEDED`

### Error Message Guidelines

Error messages are:
- **Clear**: Explain what went wrong
- **Actionable**: Suggest how to fix the issue
- **Contextual**: Include relevant details
- **User-friendly**: Avoid technical jargon when possible

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Permission denied |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `INTERNAL_SERVER_ERROR` | 500 | Server error |

### Error Response Structure

All errors include:

- **code**: Machine-readable error code
- **message**: Human-readable error message
- **http_status**: HTTP status code
- **request_id**: Unique request identifier for tracking
- **timestamp**: ISO 8601 timestamp
- **details**: Additional error details (field errors, etc.)

### Field-Level Errors

Validation errors include field-level details:

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
          "code": "INVALID_FORMAT"
        },
        {
          "field": "password",
          "message": "Password must be at least 8 characters",
          "code": "TOO_SHORT"
        }
      ]
    }
  }
}
```

### Request ID

Every error response includes a `request_id` for tracking:

```json
{
  "error": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    ...
  }
}
```

Use this ID when reporting issues or contacting support.

---

## API Response Times

### Performance Targets

| Endpoint Type | Target P95 | Target P99 |
|---------------|------------|------------|
| GET (single resource) | ≤ 300ms | ≤ 500ms |
| GET (list) | ≤ 500ms | ≤ 1000ms |
| POST (create) | ≤ 1000ms | ≤ 2000ms |
| PUT/PATCH (update) | ≤ 500ms | ≤ 1000ms |
| DELETE | ≤ 300ms | ≤ 500ms |

### Response Time Headers

Response times are not included in headers by default, but can be monitored via:
- Application logs
- APM tools (if configured)
- Custom monitoring

### Performance Best Practices

1. **Use Pagination**: Request only the data you need
2. **Use Filtering**: Filter results server-side
3. **Use Caching**: Cache responses when appropriate
4. **Batch Operations**: Use batch endpoints when available
5. **Avoid Over-fetching**: Request only required fields

### Monitoring Response Times

Monitor response times using:
- Application performance monitoring (APM) tools
- Custom logging and metrics
- Client-side timing measurements

---

## API Rate Limiting

### Rate Limit Configuration

Rate limits are configured per:
- **User**: Per authenticated user
- **Tenant**: Per tenant organization
- **API Key**: Per API key
- **IP Address**: Per IP (if configured)

### Rate Limit Windows

Multiple time windows are supported:

- **Burst**: Short-term burst protection (e.g., 100 requests/minute)
- **Sustained**: Medium-term sustained usage (e.g., 1000 requests/hour)
- **Daily**: Long-term daily limits (e.g., 10000 requests/day)

### Rate Limit Headers

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1642233600
```

Or:

```
RateLimit-Limit: 1000
RateLimit-Remaining: 950
RateLimit-Reset: 1642233600
```

### Rate Limit Exceeded Response

When rate limit is exceeded:

**Status Code**: `429 Too Many Requests`

**Response:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded for user (sustained)",
    "http_status": 429,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "limit_type": "user",
      "category": "sustained",
      "limit": 1000,
      "remaining": 0,
      "reset_time": 1642233600,
      "retry_after": 3600
    }
  }
}
```

**Headers:**
```
Retry-After: 3600
```

### Rate Limit Best Practices

1. **Respect Retry-After**: Wait for the specified time before retrying
2. **Implement Exponential Backoff**: Gradually increase retry delays
3. **Cache Responses**: Reduce API calls by caching responses
4. **Batch Requests**: Combine multiple operations when possible
5. **Monitor Usage**: Track your API usage to stay within limits

### Rate Limit Categories

Different endpoint categories may have different rate limits:

- **Read Operations**: Higher limits (e.g., 1000/hour)
- **Write Operations**: Lower limits (e.g., 100/hour)
- **Heavy Operations**: Very low limits (e.g., 10/hour)

---

## Best Practices

### For API Consumers

1. **Use OpenAPI Spec**: Always refer to the OpenAPI specification
2. **Handle Errors Gracefully**: Check error codes and messages
3. **Respect Rate Limits**: Implement retry logic with backoff
4. **Use Pagination**: Don't request all data at once
5. **Cache When Appropriate**: Reduce unnecessary API calls
6. **Monitor Response Times**: Track performance in your application
7. **Use Request IDs**: Include request IDs in error reports

### For API Developers

1. **Maintain Consistency**: Follow established patterns
2. **Provide Clear Errors**: Include helpful error messages
3. **Document Thoroughly**: Keep OpenAPI spec up to date
4. **Monitor Performance**: Track response times and optimize
5. **Test Usability**: Regularly test API usability
6. **Gather Feedback**: Collect user feedback on API usability

---

## Testing

### E2E Test Suite

Comprehensive E2E tests verify API usability:

**Test File**: `tests/e2e/test_api_usability_comprehensive.py`

**Test Categories:**
1. **API Discoverability Tests** (10 tests)
   - API info endpoint
   - OpenAPI spec availability
   - Interactive documentation
   - Endpoint discovery

2. **API Consistency Tests** (8 tests)
   - Response format consistency
   - Pagination consistency
   - Filtering consistency
   - Content type consistency

3. **API Error Messages Tests** (9 tests)
   - Error message clarity
   - Error code format
   - Field-level errors
   - Request ID inclusion

4. **API Response Times Tests** (5 tests)
   - GET endpoint performance
   - List endpoint performance
   - POST endpoint performance
   - Concurrent request performance

5. **API Rate Limits Tests** (6 tests)
   - Rate limit headers
   - Rate limit enforcement
   - Error format
   - Per-user isolation

### Running Tests

```bash
# Run all API usability tests
pytest tests/e2e/test_api_usability_comprehensive.py -v

# Run specific test category
pytest tests/e2e/test_api_usability_comprehensive.py::APIDiscoverabilityE2ETest -v

# Run with coverage
pytest tests/e2e/test_api_usability_comprehensive.py --cov=hub.apps.api --cov-report=html
```

### Test Coverage

The test suite provides:
- **100% coverage** of API usability aspects
- **Real service testing** (no mocks/stubs)
- **Comprehensive scenarios** (success, failure, edge cases)
- **Performance validation** (response time targets)

---

## Related Documentation

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [API Standards](API_STANDARDS.md) - API consistency standards
- [API Error Codes](API_ERROR_CODES.md) - Complete error code reference
- [API Testing Guide](API_TESTING_GUIDE.md) - API testing strategies
- [API Best Practices](API_BEST_PRACTICES.md) - API development best practices

