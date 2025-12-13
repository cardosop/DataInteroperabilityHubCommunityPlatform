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

