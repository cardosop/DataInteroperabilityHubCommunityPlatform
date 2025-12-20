# API Error Responses Documentation

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-13  
**Task**: 0.4.3 - Document error responses

---

## Overview

This document provides comprehensive documentation of all API error responses, including error codes, HTTP status codes, error message formats, and handling guidelines.

**Coverage**: All 8 missing API endpoints have complete error response documentation in their OpenAPI 3.0 specifications.

---

## Error Response Format

All API error responses follow a standardized format:

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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Machine-readable error code (e.g., `VALIDATION_ERROR`) |
| `message` | string | Yes | Human-readable error message for display to users |
| `http_status` | integer | Yes | HTTP status code (400, 401, 403, 404, 409, 429, 500, 502, 503, 504) |
| `request_id` | string (UUID) | Yes | Unique request identifier for support and debugging |
| `timestamp` | string (ISO 8601) | Yes | Error timestamp in ISO 8601 format |
| `details` | object | No | Additional error details (field errors, context, etc.) |

---

## HTTP Status Codes

### 400 Bad Request

**Description**: Client error - invalid request format or validation failure.

**Common Causes**:
- Missing required fields
- Invalid field values (format, type, range)
- Malformed JSON
- Invalid query parameters
- Business rule validation failures

**Error Codes**:
- `VALIDATION_ERROR` - Generic validation error
- `VALIDATION_FAILED` - Contract/schema validation failed
- `EMAIL_ALREADY_EXISTS` - Email address already registered (registration endpoint)
- `WEAK_PASSWORD` - Password does not meet strength requirements
- `INVALID_CREDENTIALS` - Invalid credential format (credential endpoints)
- `CONNECTION_FAILED` - Failed to connect with provided credentials
- `INVALID_QUERY` - Invalid natural language query (AI endpoints)
- `QUERY_TOO_COMPLEX` - Query is too complex to process
- `INVALID_SCHEMAS` - Invalid source or target schema (schema matching)
- `SCHEMA_MATCHING_FAILED` - Failed to match schemas
- `INVALID_RATING` - Rating must be between 1 and 5
- `ALREADY_RATED` - User has already rated this asset
- `INVALID_REVIEW` - Review text is required
- `REVIEW_TOO_LONG` - Review exceeds maximum length

**Example**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        },
        {
          "field": "password",
          "message": "Password must be at least 8 characters",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

---

### 401 Unauthorized

**Description**: Authentication required - missing or invalid authentication token.

**Common Causes**:
- Missing `Authorization` header
- Invalid JWT token format
- Expired token
- Invalid token signature
- Token not found in system

**Error Codes**:
- `AUTH_UNAUTHORIZED` - Authentication required
- `INVALID_CREDENTIALS` - Invalid email or password (login endpoint)
- `ACCOUNT_LOCKED` - Account is locked due to too many failed attempts

**Example**:
```json
{
  "error": {
    "code": "AUTH_UNAUTHORIZED",
    "message": "Authentication required",
    "http_status": 401,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Check if token is expired - refresh if possible
2. Prompt user to re-authenticate
3. Clear stored credentials
4. Redirect to login page

---

### 403 Forbidden

**Description**: Permission denied - authenticated but insufficient permissions.

**Common Causes**:
- Insufficient role permissions
- Tenant access restrictions
- Resource ownership restrictions
- Operation not allowed for user role
- Preview not available (marketplace preview endpoint)

**Error Codes**:
- `AUTH_FORBIDDEN` - Permission denied
- `PREVIEW_NOT_ALLOWED` - Preview not available for this listing

**Example**:
```json
{
  "error": {
    "code": "AUTH_FORBIDDEN",
    "message": "Permission denied",
    "http_status": 403,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Display permission denied message
2. Hide or disable action that triggered error
3. Log error for admin review
4. Do not retry (will fail again)

---

### 404 Not Found

**Description**: Resource not found - requested resource doesn't exist.

**Common Causes**:
- Invalid resource ID (UUID format invalid or not found)
- Resource deleted
- Incorrect URL path
- Resource belongs to different tenant (tenant isolation)

**Error Codes**:
- `NOT_FOUND` - Resource not found
- `CREDENTIALS_NOT_FOUND` - Credentials not found for scheduled ingestion
- `LISTING_NOT_FOUND` - Marketplace listing not found

**Example**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "http_status": 404,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Display "not found" message to user
2. Navigate to appropriate page (list view, home)
3. Clear cached resource data
4. Do not retry (resource won't appear)

---

### 409 Conflict

**Description**: Resource conflict - request conflicts with current state.

**Common Causes**:
- Duplicate resource creation (email already exists, etc.)
- Concurrent modification conflict
- State transition conflict (e.g., activating already active asset)
- Version conflict

**Error Codes**:
- `CONFLICT_ERROR` - Resource conflict
- `EMAIL_ALREADY_EXISTS` - Email address already registered

**Example**:
```json
{
  "error": {
    "code": "CONFLICT_ERROR",
    "message": "Resource conflict",
    "http_status": 409,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "conflicting_field": "email",
      "conflicting_value": "user@example.com"
    }
  }
}
```

**Client Handling**:
1. Display conflict message
2. Show conflicting resource if available
3. Allow user to resolve conflict
4. Refresh resource state before retry

---

### 429 Too Many Requests

**Description**: Rate limit exceeded - too many requests in time window.

**Common Causes**:
- Exceeded per-tenant rate limit
- Exceeded per-endpoint rate limit
- Burst request pattern
- Registration/login abuse prevention

**Error Codes**:
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded

**Example**:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after the specified time.",
    "http_status": 429,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "retry_after": 60
    }
  }
}
```

**Response Headers**:
- `Retry-After`: Number of seconds to wait before retrying (integer)
- `X-RateLimit-Limit`: Request limit per time window (integer)
- `X-RateLimit-Remaining`: Remaining requests in current window (integer)
- `X-RateLimit-Reset`: Unix timestamp when rate limit resets (integer)

**Client Handling**:
1. Read `Retry-After` header or `details.retry_after`
2. Display rate limit message with retry time
3. Implement exponential backoff
4. Queue request for retry after delay
5. Monitor rate limit headers to prevent future limits

---

### 500 Internal Server Error

**Description**: Server error - unexpected server-side error.

**Common Causes**:
- Database connection failure
- External service failure
- Unhandled exception
- Configuration error
- Data corruption

**Error Codes**:
- `INTERNAL_ERROR` - Internal server error

**Example**:
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An internal server error occurred",
    "http_status": 500,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Display generic error message (don't expose internal details)
2. Log error with `request_id` for support
3. Retry with exponential backoff (transient error)
4. Report to support if persistent
5. Do not expose stack traces or internal details to users

---

### 502 Bad Gateway

**Description**: Bad Gateway - upstream service error.

**Common Causes**:
- Upstream service unavailable
- Gateway timeout
- Service communication failure

**Error Codes**:
- `SERVICE_UNAVAILABLE` - Service unavailable

**Example**:
```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Service temporarily unavailable",
    "http_status": 502,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Retry with exponential backoff
2. Display "service temporarily unavailable" message
3. Check service status page if available

---

### 503 Service Unavailable

**Description**: Service temporarily unavailable - service is down or overloaded.

**Common Causes**:
- Service maintenance
- High load / overloaded
- Dependency service down
- AI/ML service unavailable (for AI endpoints)

**Error Codes**:
- `SERVICE_UNAVAILABLE` - Service temporarily unavailable
- `LLM_SERVICE_UNAVAILABLE` - AI service is temporarily unavailable (natural language search)
- `AI_SERVICE_UNAVAILABLE` - AI service is temporarily unavailable (schema matching)

**Example**:
```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Service temporarily unavailable. Please try again later.",
    "http_status": 503,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Retry with exponential backoff
2. Display "service temporarily unavailable" message
3. Check service status page
4. Queue request for later retry
5. Implement circuit breaker pattern

---

### 504 Gateway Timeout

**Description**: Gateway Timeout - request timeout.

**Common Causes**:
- Request processing timeout
- Upstream service timeout
- Long-running operation timeout

**Error Codes**:
- `GATEWAY_TIMEOUT` - Request timeout

**Example**:
```json
{
  "error": {
    "code": "GATEWAY_TIMEOUT",
    "message": "Request timeout",
    "http_status": 504,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Client Handling**:
1. Retry request (may have completed on server)
2. Check if operation is idempotent before retry
3. Display timeout message
4. Consider breaking into smaller requests

---

## Error Codes Reference

### Standard Error Codes

| Code | HTTP Status | Description | Retryable |
|------|-------------|-------------|-----------|
| `VALIDATION_ERROR` | 400 | Generic validation error | No |
| `VALIDATION_FAILED` | 400 | Contract/schema validation failed | No |
| `AUTH_UNAUTHORIZED` | 401 | Authentication required | No |
| `AUTH_FORBIDDEN` | 403 | Permission denied | No |
| `NOT_FOUND` | 404 | Resource not found | No |
| `CONFLICT_ERROR` | 409 | Resource conflict | No |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded | Yes (after delay) |
| `INTERNAL_ERROR` | 500 | Internal server error | Yes |
| `SERVICE_UNAVAILABLE` | 502, 503 | Service unavailable | Yes |
| `GATEWAY_TIMEOUT` | 504 | Request timeout | Yes |

### Endpoint-Specific Error Codes

#### Authentication Endpoints

| Code | HTTP Status | Endpoint | Description |
|------|-------------|----------|-------------|
| `EMAIL_ALREADY_EXISTS` | 400 | POST `/api/v1/auth/register/` | Email address already registered |
| `WEAK_PASSWORD` | 400 | POST `/api/v1/auth/register/` | Password does not meet strength requirements |
| `INVALID_CREDENTIALS` | 401 | POST `/api/v1/auth/login/` | Invalid email or password |
| `ACCOUNT_LOCKED` | 401 | POST `/api/v1/auth/login/` | Account locked due to too many failed attempts |

#### Credential Management Endpoints

| Code | HTTP Status | Endpoint | Description |
|------|-------------|----------|-------------|
| `INVALID_CREDENTIALS` | 400 | POST `/api/v1/scheduled-ingestions/{id}/credentials/test/` | Invalid credential format |
| `CONNECTION_FAILED` | 400 | POST `/api/v1/scheduled-ingestions/{id}/credentials/test/` | Failed to connect with provided credentials |
| `CREDENTIALS_NOT_FOUND` | 404 | GET `/api/v1/scheduled-ingestions/{id}/credentials/` | Credentials not found |

#### AI/ML Endpoints

| Code | HTTP Status | Endpoint | Description |
|------|-------------|----------|-------------|
| `INVALID_QUERY` | 400 | POST `/api/v1/ai/natural-language-search/` | Invalid natural language query |
| `QUERY_TOO_COMPLEX` | 400 | POST `/api/v1/ai/natural-language-search/` | Query is too complex to process |
| `INVALID_SCHEMAS` | 400 | POST `/api/v1/ai/schema-matching/` | Invalid source or target schema |
| `SCHEMA_MATCHING_FAILED` | 400 | POST `/api/v1/ai/schema-matching/` | Failed to match schemas |
| `LLM_SERVICE_UNAVAILABLE` | 503 | POST `/api/v1/ai/natural-language-search/` | AI service temporarily unavailable |
| `AI_SERVICE_UNAVAILABLE` | 503 | POST `/api/v1/ai/schema-matching/` | AI service temporarily unavailable |

#### Social Feature Endpoints

| Code | HTTP Status | Endpoint | Description |
|------|-------------|----------|-------------|
| `INVALID_RATING` | 400 | POST `/api/v1/social/ratings/` | Rating must be between 1 and 5 |
| `ALREADY_RATED` | 400 | POST `/api/v1/social/ratings/` | User has already rated this asset |
| `INVALID_REVIEW` | 400 | POST `/api/v1/social/reviews/` | Review text is required |
| `REVIEW_TOO_LONG` | 400 | POST `/api/v1/social/reviews/` | Review exceeds maximum length |

#### Marketplace Endpoints

| Code | HTTP Status | Endpoint | Description |
|------|-------------|----------|-------------|
| `PREVIEW_NOT_ALLOWED` | 403 | GET `/api/v1/marketplace/listings/{id}/preview/` | Preview not available for this listing |
| `LISTING_NOT_FOUND` | 404 | GET `/api/v1/marketplace/listings/{id}/preview/` | Marketplace listing not found |

---

## Field-Level Errors

For validation errors (400), the `details.field_errors` array contains field-specific errors:

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
        },
        {
          "field": "password",
          "message": "Password must be at least 8 characters",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

### Field Error Structure

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | Field name that has the error |
| `message` | string | Field-specific error message |
| `code` | string | Error code (usually `VALIDATION_ERROR`) |

**Client Handling**:
1. Display field errors next to corresponding form fields
2. Highlight fields with errors
3. Scroll to first error field
4. Prevent form submission until errors resolved

---

## Error Handling Best Practices

### Client-Side Error Handling

1. **Always Check Status Codes**: Verify HTTP status code before processing response
2. **Display User-Friendly Messages**: Show `error.message` to users, not technical details
3. **Log Error Details**: Log full error response (including `request_id`) for debugging
4. **Handle Retryable Errors**: Implement retry logic for 5xx errors and 429 with exponential backoff
5. **Preserve Request ID**: Include `request_id` in support requests
6. **Field-Level Error Display**: Map `field_errors` to form fields for validation feedback
7. **Rate Limit Handling**: Respect `Retry-After` header and rate limit headers
8. **Circuit Breaker**: Implement circuit breaker for repeated 5xx errors

### Retry Strategy

| Status Code | Retryable | Strategy |
|-------------|-----------|----------|
| 400, 401, 403, 404, 409 | No | Do not retry |
| 429 | Yes | Retry after `Retry-After` delay |
| 500, 502, 503, 504 | Yes | Exponential backoff (1s, 2s, 4s, 8s, max 30s) |

### Error Logging

Always log:
- `request_id` - For support correlation
- `error.code` - For error categorization
- `error.message` - For debugging
- `http_status` - For monitoring
- `timestamp` - For timeline analysis
- Request details (method, path, headers) - For context

---

## Error Response Examples by Endpoint

### POST `/api/v1/auth/register/`

**400 - Validation Error**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        },
        {
          "field": "password",
          "message": "Password must be at least 8 characters",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

**400 - Email Already Exists**:
```json
{
  "error": {
    "code": "EMAIL_ALREADY_EXISTS",
    "message": "Email address is already registered",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**429 - Rate Limit**:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after the specified time.",
    "http_status": 429,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "retry_after": 60
    }
  }
}
```

### GET `/api/v1/auth/me/`

**401 - Unauthorized**:
```json
{
  "error": {
    "code": "AUTH_UNAUTHORIZED",
    "message": "Authentication required",
    "http_status": 401,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

### POST `/api/v1/scheduled-ingestions/{id}/credentials/test/`

**400 - Connection Failed**:
```json
{
  "error": {
    "code": "CONNECTION_FAILED",
    "message": "Failed to connect with provided credentials",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "connection_error": "Invalid credentials or network error"
    }
  }
}
```

**404 - Credentials Not Found**:
```json
{
  "error": {
    "code": "CREDENTIALS_NOT_FOUND",
    "message": "Credentials not found for this scheduled ingestion",
    "http_status": 404,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

### POST `/api/v1/ai/natural-language-search/`

**400 - Invalid Query**:
```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "Invalid natural language query",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "query": "example invalid query",
      "reason": "Query cannot be empty"
    }
  }
}
```

**503 - LLM Service Unavailable**:
```json
{
  "error": {
    "code": "LLM_SERVICE_UNAVAILABLE",
    "message": "AI service is temporarily unavailable",
    "http_status": 503,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

---

## OpenAPI Specification Integration

All error responses are documented in OpenAPI 3.0 specifications using:

1. **Reusable Schema**: `#/components/schemas/ErrorResponse` - Standard error response schema
2. **Response Definitions**: Each endpoint includes error responses in `responses` section
3. **Examples**: Multiple examples per error code showing different scenarios
4. **Headers**: Rate limiting headers documented for 429 responses

### Schema Reference

All error responses reference the standard schema:

```yaml
responses:
  '400':
    description: Bad Request - Validation error
    content:
      application/json:
        schema:
          $ref: '#/components/schemas/ErrorResponse'
        examples:
          default:
            summary: Validation error example
            value:
              error:
                code: "VALIDATION_ERROR"
                message: "Invalid request data"
                http_status: 400
                request_id: "550e8400-e29b-41d4-a716-446655440000"
                timestamp: "2025-01-15T10:30:00Z"
                details:
                  field_errors: [...]
```

---

## Validation and Testing

### OpenAPI Validation

All OpenAPI specs with error responses are validated against OpenAPI 3.0.3 specification:

```bash
# Validate specs
npx @apidevtools/swagger-cli validate docs/api-contracts/missing/**/*.yaml
```

### Error Response Testing

Error responses should be tested for:
1. **Schema Compliance**: Response matches ErrorResponse schema
2. **Status Code Accuracy**: Correct HTTP status code returned
3. **Error Code Mapping**: Correct error code for error type
4. **Message Quality**: User-friendly, non-technical messages
5. **Request ID Presence**: Unique request ID in all errors
6. **Timestamp Format**: ISO 8601 format
7. **Field Errors**: Proper field error structure for validation errors
8. **Rate Limit Headers**: Correct headers for 429 responses

---

## Summary

- **Total Endpoints Documented**: 8 missing API endpoints
- **Error Responses Per Endpoint**: 4-7 standard error responses
- **Total Error Responses**: 40+ error response definitions
- **Error Codes**: 25+ unique error codes
- **HTTP Status Codes**: 400, 401, 403, 404, 409, 429, 500, 502, 503, 504
- **Documentation Coverage**: 100% of missing endpoints have complete error response documentation

All error responses follow the standardized format and are fully documented in OpenAPI 3.0 specifications with examples, schemas, and comprehensive error codes.

