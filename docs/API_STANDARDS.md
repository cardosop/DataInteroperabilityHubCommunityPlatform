# API Standards Documentation

Complete documentation of API consistency standards, including response formats, pagination, filtering, sorting, error codes, and validation.

## Table of Contents

1. [Overview](#overview)
2. [Response Formats](#response-formats)
3. [Pagination](#pagination)
4. [Filtering](#filtering)
5. [Sorting](#sorting)
6. [Error Codes](#error-codes)
7. [API Validation](#api-validation)
8. [Usage Examples](#usage-examples)
9. [Best Practices](#best-practices)

---

## Overview

The API Standards module (`hub.apps.api.standards`) provides consistent, standardized components for all API endpoints:

- ✅ **Standardized Response Formats**: Consistent success and error response structures
- ✅ **Cursor-Based Pagination**: High-performance pagination for large datasets
- ✅ **Standardized Filtering**: Consistent query parameter filtering
- ✅ **Standardized Sorting**: Consistent ordering across endpoints
- ✅ **Standardized Error Codes**: Machine-readable error codes
- ✅ **API Validation Middleware**: Request validation for consistency

---

## Response Formats

### Success Responses

All success responses follow a consistent format:

#### Single Resource (200/201)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Resource Name",
  "created_at": "2025-01-15T10:30:00Z"
}
```

Or with message:

```json
{
  "message": "Resource created successfully",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Resource Name"
}
```

#### List Response (200)

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

#### Cursor-Based List Response (200)

```json
{
  "count": 100,
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNVQxMDozMDowMFoifQ==",
  "previous_cursor": null,
  "page_size": 50,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Resource 1"
    }
  ]
}
```

#### No Content (204)

Empty response body for DELETE operations.

### Error Responses

All error responses follow the standard format:

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

### Usage

```python
from hub.apps.api.standards.response_formats import (
    format_success_response,
    format_list_response,
    format_error_response,
)

# Success response
return format_success_response(
    data={'id': '123', 'name': 'Test'},
    message='Resource retrieved successfully',
)

# List response
return format_list_response(
    items=resources,
    count=total_count,
    page=1,
    page_size=50,
)

# Error response
return format_error_response(
    error_code='VALIDATION_ERROR',
    message='Invalid input',
    http_status=400,
    details={'field_errors': [...]},
)
```

---

## Pagination

### Cursor-Based Pagination (Recommended)

Cursor-based pagination is recommended for most endpoints as it provides better performance with large datasets.

#### Request

```
GET /api/v1/resources/?cursor=eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNVQxMDozMDowMFoifQ==&page_size=50
```

#### Response

```json
{
  "count": 1000,
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNlQxMDozMDowMFoifQ==",
  "previous_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNFQxMDozMDowMFoifQ==",
  "page_size": 50,
  "results": [...]
}
```

### Page-Based Pagination

Page-based pagination uses offset-based pagination.

#### Request

```
GET /api/v1/resources/?page=2&page_size=50
```

#### Response

```json
{
  "count": 1000,
  "page": 2,
  "page_size": 50,
  "total_pages": 20,
  "next": "https://api.datahub.example.com/api/v1/resources/?page=3",
  "previous": "https://api.datahub.example.com/api/v1/resources/?page=1",
  "results": [...]
}
```

### Usage

```python
from hub.apps.api.standards.pagination import (
    StandardCursorPagination,
    StandardPageNumberPagination,
)

class ResourceViewSet(viewsets.ModelViewSet):
    # Use cursor-based pagination (recommended)
    pagination_class = StandardCursorPagination
    
    # Or use page-based pagination
    # pagination_class = StandardPageNumberPagination
```

### Parameters

- **page**: Page number (1-indexed, for page-based pagination)
- **page_size**: Items per page (default: 50, max: 100)
- **cursor**: Cursor string (for cursor-based pagination)

---

## Filtering

### Standard Filter Operators

All endpoints support consistent filtering using query parameters:

- **Exact match**: `?field=value`
- **Case-insensitive**: `?field__iexact=value`
- **Contains**: `?field__contains=value`
- **In**: `?field__in=value1,value2`
- **Range**: `?field__gte=value&field__lte=value`
- **Null**: `?field__isnull=true`

### Examples

```
# Exact match
GET /api/v1/resources/?status=active

# Case-insensitive
GET /api/v1/resources/?name__iexact=test

# Contains
GET /api/v1/resources/?description__contains=data

# In (comma-separated)
GET /api/v1/resources/?status__in=active,pending

# Range
GET /api/v1/resources/?created_at__gte=2025-01-01&created_at__lte=2025-01-31

# Null check
GET /api/v1/resources/?deleted_at__isnull=true
```

### Usage

```python
from hub.apps.api.standards.filtering import StandardFilterBackend

class ResourceViewSet(viewsets.ModelViewSet):
    filter_backends = [StandardFilterBackend]
    filter_fields = ['status', 'name', 'created_at']  # Allowed fields
```

---

## Sorting

### Standard Sorting

All endpoints support consistent sorting using the `ordering` parameter:

- **Single field**: `?ordering=field_name`
- **Multiple fields**: `?ordering=field1,field2`
- **Descending**: `?ordering=-field_name`
- **Ascending**: `?ordering=field_name` (default)

### Examples

```
# Single field ascending
GET /api/v1/resources/?ordering=name

# Single field descending
GET /api/v1/resources/?ordering=-created_at

# Multiple fields
GET /api/v1/resources/?ordering=status,-created_at,name
```

### Usage

```python
from hub.apps.api.standards.sorting import StandardOrderingBackend

class ResourceViewSet(viewsets.ModelViewSet):
    filter_backends = [StandardOrderingBackend]
    ordering_fields = ['name', 'created_at', 'status']  # Allowed fields
    ordering = ['-created_at']  # Default ordering
```

---

## Error Codes

### Standard Error Codes

All error codes follow the pattern: `CATEGORY_SPECIFIC_ERROR`

#### Validation Errors (400)

- `VALIDATION_ERROR` - Generic validation error
- `VALIDATION_FAILED` - Validation failed
- `INVALID_INPUT` - Invalid input
- `MISSING_REQUIRED_FIELD` - Missing required field
- `INVALID_FORMAT` - Invalid format

#### Authentication Errors (401)

- `AUTH_UNAUTHORIZED` - Authentication required
- `AUTH_TOKEN_EXPIRED` - Token expired
- `AUTH_TOKEN_INVALID` - Invalid token
- `AUTH_CREDENTIALS_INVALID` - Invalid credentials

#### Authorization Errors (403)

- `AUTH_FORBIDDEN` - Permission denied
- `PERMISSION_DENIED` - Permission denied
- `INSUFFICIENT_PERMISSIONS` - Insufficient permissions
- `TENANT_ACCESS_DENIED` - Tenant access denied

#### Not Found Errors (404)

- `NOT_FOUND` - Resource not found
- `RESOURCE_NOT_FOUND` - Resource not found
- `ENDPOINT_NOT_FOUND` - Endpoint not found

#### Conflict Errors (409)

- `CONFLICT_ERROR` - Resource conflict
- `RESOURCE_CONFLICT` - Resource conflict
- `DUPLICATE_RESOURCE` - Duplicate resource

#### Rate Limiting (429)

- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `TOO_MANY_REQUESTS` - Too many requests

#### Server Errors (500)

- `INTERNAL_ERROR` - Internal server error
- `SERVER_ERROR` - Server error
- `DATABASE_ERROR` - Database error

#### Service Unavailable (502/503)

- `SERVICE_UNAVAILABLE` - Service unavailable
- `BAD_GATEWAY` - Bad gateway
- `SERVICE_TIMEOUT` - Service timeout

### Usage

```python
from hub.apps.api.standards.error_codes import (
    StandardErrorCodes,
    get_error_code,
    get_error_message,
)

# Get error code
error_code = get_error_code(exception, http_status=400)

# Get error message
error_message = get_error_message(exception, http_status=400)
```

---

## API Validation

### Validation Middleware

The API Validation Middleware automatically validates:

- **Content-Type headers**: Must be `application/json` for POST/PUT/PATCH
- **JSON body format**: Valid JSON required
- **Pagination parameters**: Valid page numbers and page sizes
- **Ordering parameters**: Valid field names and operators

### Validation Rules

#### Content-Type

- POST/PUT/PATCH requests must have `Content-Type: application/json`
- Invalid Content-Type returns `400 INVALID_FORMAT`

#### JSON Body

- Request body must be valid JSON
- Invalid JSON returns `400 INVALID_FORMAT`

#### Pagination

- Page number must be >= 1
- Page size must be between 1 and 100
- Cannot use both `page` and `cursor` parameters

#### Ordering

- Ordering field names must contain only alphanumeric characters, `-`, `_`, `,`, `.`
- Invalid characters return `400 VALIDATION_ERROR`

### Usage

The middleware is automatically enabled in `settings.py`:

```python
MIDDLEWARE = [
    ...
    "hub.apps.api.standards.validation_middleware.APIValidationMiddleware",
    ...
]
```

---

## Usage Examples

### Complete ViewSet Example

```python
from rest_framework import viewsets
from hub.apps.api.standards.pagination import StandardCursorPagination
from hub.apps.api.standards.filtering import StandardFilterBackend
from hub.apps.api.standards.sorting import StandardOrderingBackend

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
    
    # Use standardized pagination
    pagination_class = StandardCursorPagination
    
    # Use standardized filtering
    filter_backends = [StandardFilterBackend]
    filter_fields = ['status', 'name', 'created_at']
    
    # Use standardized sorting
    ordering_fields = ['name', 'created_at', 'status']
    ordering = ['-created_at']  # Default ordering
```

### Custom Response Formatting

```python
from hub.apps.api.standards.response_formats import format_success_response

class CustomViewSet(viewsets.ViewSet):
    def list(self, request):
        resources = Resource.objects.all()
        return format_success_response(
            data={'resources': [r.id for r in resources]},
            message='Resources retrieved successfully',
        )
```

---

## Best Practices

### For API Developers

1. **Always use standardized components**: Use `StandardCursorPagination`, `StandardFilterBackend`, etc.
2. **Define allowed fields**: Always specify `filter_fields` and `ordering_fields` in viewsets
3. **Use consistent error codes**: Use `StandardErrorCodes` constants
4. **Format responses consistently**: Use `format_success_response`, `format_list_response`, etc.
5. **Test validation**: Ensure validation middleware catches invalid requests

### For API Consumers

1. **Use cursor-based pagination**: Prefer cursor-based pagination for better performance
2. **Respect page size limits**: Maximum page size is 100
3. **Handle all error codes**: Implement handling for all possible error codes
4. **Validate responses**: Always validate response structure
5. **Use request IDs**: Include `request_id` from error responses when reporting issues

---

## Testing

### Running Tests

```bash
# Run all API standards tests
pytest hub/apps/api/standards/tests/

# Run specific test file
pytest hub/apps/api/standards/tests/test_response_formats.py

# Run with coverage
pytest hub/apps/api/standards/tests/ --cov=hub.apps.api.standards
```

### Test Coverage

All components have comprehensive test coverage targeting 100%:

- ✅ Response formats (100%)
- ✅ Pagination (100%)
- ✅ Filtering (100%)
- ✅ Sorting (100%)
- ✅ Error codes (100%)
- ✅ Validation middleware (100%)

---

**Last Updated**: 2025-12-12  
**Module**: `hub.apps.api.standards`  
**Status**: ✅ Production Ready
