# API Standards

> Consolidated API standards covering naming, versioning, best practices, and gateway configuration.
>
> **Source**: Merged from 9 API standards docs during Phase 120D documentation consolidation.

---


---

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

**Last Updated**: 2026-03-22  
**Module**: `hub.apps.api.standards`  
**Status**: ✅ Production Ready

---

# API Naming Standards

**Document Version**: 1.0.0
**Last Updated**: 2026-03-22
**Status**: Active
**Applies To**: All REST API endpoints (`/api/v1/*`)

---

## Table of Contents

1. [Overview](#overview)
2. [Core Principles](#core-principles)
3. [No Duplication Rule](#no-duplication-rule)
4. [Plural Resources Rule](#plural-resources-rule)
5. [Consistent Patterns](#consistent-patterns)
6. [Resource Naming Conventions](#resource-naming-conventions)
7. [URL Pattern Validation Rules](#url-pattern-validation-rules)
8. [Examples](#examples)
9. [Migration Guidelines](#migration-guidelines)
10. [Validation Checklist](#validation-checklist)

---

## Overview

This document defines the naming standards for all REST API endpoints in the Data Interoperability Hub. These standards ensure consistency, predictability, and maintainability across the entire API surface.

### Goals

- **Consistency**: All endpoints follow the same patterns
- **Predictability**: Developers can infer endpoint URLs from resource names
- **Clarity**: Endpoints are self-documenting and unambiguous
- **Maintainability**: Standards reduce cognitive load and prevent errors

### Scope

These standards apply to:
- All REST API endpoints under `/api/v1/`
- URL patterns defined in Django `urls.py` files
- ViewSet router registrations
- Custom action endpoints

---

## Core Principles

### 1. RESTful Design
- Use HTTP methods to indicate actions (GET, POST, PUT, PATCH, DELETE)
- Use URLs to identify resources, not actions
- Follow REST conventions for resource manipulation

### 2. Hierarchical Structure
- Organize endpoints hierarchically by resource relationships
- Use nested paths to represent relationships (e.g., `/assets/{id}/datasets/`)

### 3. Explicit Naming
- Use clear, descriptive resource names
- Avoid abbreviations unless universally understood
- Prefer domain terminology over generic terms

### 4. Consistency First
- Apply standards uniformly across all endpoints
- When in doubt, follow existing patterns
- Document exceptions and rationale

---

## No Duplication Rule

### Rule

**Service names or resource names MUST NOT appear multiple times in the URL path.**

### Rationale

Duplication creates confusion, increases URL length unnecessarily, and violates REST principles. The service/resource name should appear exactly once in the path hierarchy.

### Examples

#### ✅ Correct

```
/api/v1/assets/                    # Service name appears once
/api/v1/assets/{id}/               # Service name appears once
/api/v1/contracts/                 # Service name appears once
/api/v1/contracts/{id}/validate/   # Service name appears once
```

#### ❌ Incorrect

```
/api/v1/assets/assets/             # "assets" appears twice
/api/v1/contracts/contracts/       # "contracts" appears twice
/api/v1/dq/dq/runs/                # "dq" appears twice
```

### Common Causes

1. **Router Registration with Duplicate Basename**
   ```python
   # ❌ Incorrect
   router.register(r"assets", AssetViewSet, basename="asset")
   # Results in: /api/v1/assets/assets/

   # ✅ Correct
   router.register(r"", AssetViewSet, basename="asset")
   # Results in: /api/v1/assets/
   ```

2. **Nested Includes with Duplicate Paths**
   ```python
   # ❌ Incorrect
   path('assets/', include('hub.apps.assets.urls')),  # In api/urls.py
   # Then in assets/urls.py:
   router.register(r"assets", AssetViewSet)  # Duplicate!

   # ✅ Correct
   path('assets/', include('hub.apps.assets.urls')),  # In api/urls.py
   # Then in assets/urls.py:
   router.register(r"", AssetViewSet)  # Empty string - no duplication
   ```

### Detection

To detect duplication violations:
1. Extract all URL patterns from `urls.py` files
2. Check for repeated segments in paths
3. Flag patterns where service/resource name appears more than once

---

## Plural Resources Rule

### Rule

**Collection endpoints MUST use plural nouns. Detail endpoints inherit the plural form.**

### Rationale

Plural nouns clearly indicate collections, align with REST conventions, and make endpoints self-documenting. The plural form applies to both list and detail endpoints.

### Examples

#### ✅ Correct

```
GET    /api/v1/assets/              # List all assets (plural)
POST   /api/v1/assets/              # Create asset (plural collection)
GET    /api/v1/assets/{id}/         # Get specific asset (plural form)
PUT    /api/v1/assets/{id}/         # Update asset (plural form)
DELETE /api/v1/assets/{id}/         # Delete asset (plural form)

GET    /api/v1/contracts/           # List all contracts (plural)
POST   /api/v1/contracts/          # Create contract (plural collection)
GET    /api/v1/contracts/{id}/      # Get specific contract (plural form)
```

#### ❌ Incorrect

```
GET    /api/v1/asset/                # Singular - incorrect
GET    /api/v1/contract/             # Singular - incorrect
GET    /api/v1/assets-list/          # Unnecessary "-list" suffix
```

### Special Cases

1. **Uncountable Nouns**: Use plural form even for uncountable nouns
   ```
   ✅ /api/v1/data/                  # Not "datum" (plural)
   ✅ /api/v1/information/           # Plural form
   ```

2. **Mass Nouns**: Treat as plural
   ```
   ✅ /api/v1/equipment/             # Plural form
   ✅ /api/v1/software/              # Plural form
   ```

3. **Irregular Plurals**: Use correct plural form
   ```
   ✅ /api/v1/datasets/              # Not "data"
   ✅ /api/v1/analyses/              # Not "analysis"
   ```

### Implementation

In Django router registration:
```python
# ✅ Correct
router.register(r"assets", AssetViewSet, basename="asset")
# Results in: /api/v1/assets/ (plural)

# ❌ Incorrect
router.register(r"asset", AssetViewSet, basename="asset")
# Results in: /api/v1/asset/ (singular - violates rule)
```

---

## Consistent Patterns

### Pattern Structure

All endpoints follow these consistent patterns:

1. **Collections**: `/api/v1/{resource}/`
2. **Detail**: `/api/v1/{resource}/{id}/`
3. **Actions**: `/api/v1/{resource}/{id}/{action}/`
4. **Sub-resources**: `/api/v1/{resource}/{id}/{sub-resource}/`
5. **Nested Collections**: `/api/v1/{resource}/{id}/{sub-resource}/`

### Pattern Definitions

#### 1. Collections

**Pattern**: `/api/v1/{resource}/`

**Purpose**: List all resources or create a new resource

**HTTP Methods**:
- `GET`: List resources (with pagination, filtering, sorting)
- `POST`: Create new resource

**Examples**:
```
GET  /api/v1/assets/              # List all assets
POST /api/v1/assets/              # Create new asset
GET  /api/v1/contracts/           # List all contracts
POST /api/v1/contracts/           # Create new contract
```

#### 2. Detail

**Pattern**: `/api/v1/{resource}/{id}/`

**Purpose**: Operate on a specific resource

**HTTP Methods**:
- `GET`: Retrieve resource
- `PUT`: Replace resource (full update)
- `PATCH`: Update resource (partial update)
- `DELETE`: Delete resource

**Examples**:
```
GET    /api/v1/assets/{id}/        # Get asset by ID
PUT    /api/v1/assets/{id}/        # Replace asset
PATCH  /api/v1/assets/{id}/        # Update asset partially
DELETE /api/v1/assets/{id}/        # Delete asset
```

#### 3. Actions

**Pattern**: `/api/v1/{resource}/{id}/{action}/`

**Purpose**: Perform a specific action on a resource

**HTTP Methods**:
- `POST`: Most common for actions
- `GET`: For read-only actions
- `PUT`: For state-changing actions

**Naming Convention**: Use kebab-case verbs

**Examples**:
```
POST /api/v1/contracts/{id}/validate/     # Validate contract
POST /api/v1/contracts/{id}/activate/    # Activate contract
POST /api/v1/assets/{id}/activate/        # Activate asset
GET  /api/v1/assets/{id}/dependencies/    # Get dependencies
GET  /api/v1/assets/{id}/health-score/    # Get health score
```

**Action Naming Rules**:
- Use verbs, not nouns
- Use kebab-case
- Be specific and descriptive
- Avoid generic terms like "do", "perform", "execute" unless necessary

#### 4. Sub-resources

**Pattern**: `/api/v1/{resource}/{id}/{sub-resource}/`

**Purpose**: Access related resources

**HTTP Methods**:
- `GET`: List sub-resources
- `POST`: Create sub-resource
- `GET /{sub-id}/`: Get specific sub-resource
- `DELETE /{sub-id}/`: Delete sub-resource

**Examples**:
```
GET    /api/v1/assets/{id}/datasets/           # List datasets for asset
POST   /api/v1/assets/{id}/datasets/          # Attach dataset to asset
GET    /api/v1/assets/{id}/datasets/{sub-id}/ # Get specific dataset
DELETE /api/v1/assets/{id}/datasets/{sub-id}/ # Remove dataset from asset
```

#### 5. Nested Collections

**Pattern**: `/api/v1/{resource}/{id}/{sub-resource}/`

**Purpose**: Access nested collections (same as sub-resources)

**Examples**:
```
GET  /api/v1/contracts/{id}/lineage/          # Get contract lineage
GET  /api/v1/contracts/{id}/versions/         # Get contract versions
POST /api/v1/contracts/{id}/versions/         # Create new version
```

### Pattern Validation

All endpoints MUST match one of these patterns. Custom patterns require explicit documentation and approval.

---

## Resource Naming Conventions

### Kebab-Case Rule

**All resource names MUST use kebab-case (lowercase letters with hyphens).**

### Rationale

- URLs are case-sensitive and lowercase is standard
- Hyphens improve readability over underscores or camelCase
- Consistent with web standards and REST conventions

### Examples

#### ✅ Correct

```
/api/v1/data-contracts/           # kebab-case
/api/v1/data-quality/             # kebab-case
/api/v1/scheduled-ingestions/     # kebab-case
/api/v1/api-analytics/            # kebab-case
```

#### ❌ Incorrect

```
/api/v1/dataContracts/            # camelCase - incorrect
/api/v1/data_contracts/           # snake_case - incorrect
/api/v1/DataContracts/             # PascalCase - incorrect
/api/v1/DATA_CONTRACTS/           # UPPER_SNAKE_CASE - incorrect
```

### Explicit Naming Rule

**Resource names MUST be explicit and descriptive. Avoid abbreviations unless universally understood.**

### Examples

#### ✅ Correct

```
/api/v1/data-contracts/           # Explicit: "data-contracts"
/api/v1/data-quality/              # Explicit: "data-quality"
/api/v1/scheduled-ingestions/      # Explicit: "scheduled-ingestions"
```

#### ❌ Incorrect

```
/api/v1/dc/                       # Abbreviation - unclear
/api/v1/dq/                       # Abbreviation - acceptable if documented
/api/v1/si/                       # Abbreviation - unclear
```

### Acceptable Abbreviations

Some abbreviations are acceptable if:
1. They are universally understood in the domain
2. They are documented in this standard
3. They are consistent across the API

**Currently Acceptable**:
- `dq` for "data-quality" (if consistently used)
- `api` for "application-programming-interface" (standard)

**Not Acceptable**:
- `dc` for "data-contract" (unclear)
- `si` for "scheduled-ingestion" (unclear)

### Resource Name Guidelines

1. **Use Domain Terminology**: Prefer domain-specific terms over generic ones
   ```
   ✅ /api/v1/data-contracts/      # Domain term
   ❌ /api/v1/agreements/          # Generic term (unless domain uses this)
   ```

2. **Be Specific**: Avoid overly generic names
   ```
   ✅ /api/v1/data-contracts/      # Specific
   ❌ /api/v1/items/                # Too generic
   ```

3. **Use Nouns**: Resource names should be nouns, not verbs
   ```
   ✅ /api/v1/contracts/            # Noun
   ❌ /api/v1/create-contract/     # Verb - incorrect
   ```

4. **Avoid Redundancy**: Don't include "api" or "v1" in resource names
   ```
   ✅ /api/v1/contracts/            # Correct
   ❌ /api/v1/api-contracts/        # Redundant "api"
   ❌ /api/v1/v1-contracts/         # Redundant "v1"
   ```

---

## URL Pattern Validation Rules

### Validation Checklist

All URL patterns MUST pass these validation checks:

#### 1. No Duplication Check
- [ ] Service/resource name appears exactly once in path
- [ ] No repeated segments (e.g., `/assets/assets/`)

#### 2. Plural Form Check
- [ ] Collection endpoints use plural nouns
- [ ] Detail endpoints use plural form

#### 3. Kebab-Case Check
- [ ] All resource names use kebab-case
- [ ] No camelCase, snake_case, or PascalCase

#### 4. Pattern Consistency Check
- [ ] Matches one of the defined patterns:
  - Collections: `/api/v1/{resource}/`
  - Detail: `/api/v1/{resource}/{id}/`
  - Actions: `/api/v1/{resource}/{id}/{action}/`
  - Sub-resources: `/api/v1/{resource}/{id}/{sub-resource}/`

#### 5. Explicit Naming Check
- [ ] Resource names are explicit and descriptive
- [ ] Abbreviations are documented if used

#### 6. HTTP Method Check
- [ ] HTTP methods align with REST conventions:
  - `GET`: Read operations (safe, idempotent)
  - `POST`: Create operations or actions
  - `PUT`: Full replacement (idempotent)
  - `PATCH`: Partial update (idempotent)
  - `DELETE`: Delete operations (idempotent)

### Automated Validation

Use the following regex patterns for validation:

```python
# Collection pattern
COLLECTION_PATTERN = r'^/api/v1/[a-z0-9-]+/$'

# Detail pattern
DETAIL_PATTERN = r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/$'

# Action pattern
ACTION_PATTERN = r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$'

# Sub-resource pattern
SUB_RESOURCE_PATTERN = r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$'
```

### Validation Script

A validation script should:
1. Extract all URL patterns from `urls.py` files
2. Check against all validation rules
3. Report violations with specific endpoints and issues
4. Provide suggestions for fixes

---

## Examples

### ✅ Correct Examples

#### Collections
```
GET  /api/v1/assets/                    # List assets
POST /api/v1/assets/                    # Create asset
GET  /api/v1/contracts/                 # List contracts
POST /api/v1/contracts/                 # Create contract
GET  /api/v1/data-contracts/            # List data contracts
GET  /api/v1/scheduled-ingestions/      # List scheduled ingestions
```

#### Detail Endpoints
```
GET    /api/v1/assets/{id}/             # Get asset
PUT    /api/v1/assets/{id}/             # Replace asset
PATCH  /api/v1/assets/{id}/             # Update asset
DELETE /api/v1/assets/{id}/             # Delete asset
```

#### Actions
```
POST /api/v1/contracts/{id}/validate/        # Validate contract
POST /api/v1/contracts/{id}/activate/       # Activate contract
POST /api/v1/assets/{id}/activate/           # Activate asset
GET  /api/v1/assets/{id}/dependencies/       # Get dependencies
GET  /api/v1/assets/{id}/health-score/       # Get health score
POST /api/v1/contracts/{id}/convert/         # Convert contract format
```

#### Sub-resources
```
GET    /api/v1/assets/{id}/datasets/              # List datasets for asset
POST   /api/v1/assets/{id}/datasets/              # Attach dataset
GET    /api/v1/assets/{id}/datasets/{dataset-id}/ # Get specific dataset
DELETE /api/v1/assets/{id}/datasets/{dataset-id}/ # Remove dataset
GET    /api/v1/contracts/{id}/versions/          # List versions
POST   /api/v1/contracts/{id}/versions/          # Create version
```

#### Nested Collections
```
GET  /api/v1/contracts/{id}/lineage/              # Get lineage
GET  /api/v1/contracts/{id}/lineage/visualization/ # Get visualization
```

### ❌ Incorrect Examples

#### Duplication Violations
```
❌ /api/v1/assets/assets/                 # "assets" appears twice
❌ /api/v1/contracts/contracts/           # "contracts" appears twice
❌ /api/v1/dq/dq/runs/                    # "dq" appears twice
```

#### Singular Form Violations
```
❌ /api/v1/asset/                          # Should be "assets"
❌ /api/v1/contract/                      # Should be "contracts"
❌ /api/v1/dataset/                       # Should be "datasets"
```

#### Case Violations
```
❌ /api/v1/dataContracts/                 # Should be "data-contracts"
❌ /api/v1/data_contracts/                # Should be "data-contracts"
❌ /api/v1/DataContracts/                 # Should be "data-contracts"
```

#### Pattern Violations
```
❌ /api/v1/create-asset/                  # Should be POST /api/v1/assets/
❌ /api/v1/assets-list/                   # Should be GET /api/v1/assets/
❌ /api/v1/get-asset/{id}/                 # Should be GET /api/v1/assets/{id}/
```

#### Naming Violations
```
❌ /api/v1/dc/                            # Abbreviation - unclear
❌ /api/v1/si/                            # Abbreviation - unclear
❌ /api/v1/api-contracts/                 # Redundant "api"
```

---

## Migration Guidelines

### Migration Strategy

When migrating existing endpoints to comply with these standards:

1. **Identify Violations**: Use validation script to find all violations
2. **Prioritize**: Focus on high-traffic endpoints first
3. **Plan Deprecation**: Create deprecation timeline for old endpoints
4. **Implement Redirects**: Use HTTP 301/308 redirects for GET requests
5. **Update Documentation**: Update all API documentation
6. **Notify Consumers**: Communicate changes to API consumers
7. **Monitor Usage**: Track usage of old vs new endpoints
8. **Remove Old Endpoints**: After deprecation period, remove old endpoints

### Deprecation Process

#### Step 1: Add New Endpoint
```python
# New compliant endpoint
router.register(r"assets", AssetViewSet, basename="asset")
# Results in: /api/v1/assets/
```

#### Step 2: Keep Old Endpoint with Deprecation Warning
```python
# Old endpoint with deprecation header
@deprecated_api_version
def old_asset_endpoint(request):
    response = new_asset_endpoint(request)
    response['Deprecation'] = 'true'
    response['Sunset'] = '2026-12-31'
    response['Link'] = '</api/v1/assets/>; rel="successor-version"'
    return response
```

#### Step 3: Add Redirect (for GET requests)
```python
# Redirect old endpoint to new endpoint
def redirect_old_asset_endpoint(request):
    return HttpResponsePermanentRedirect('/api/v1/assets/')
```

#### Step 4: Remove Old Endpoint
After deprecation period (typically 6-12 months), remove old endpoint.

### Migration Examples

#### Example 1: Fix Duplication

**Before**:
```python
# In api/urls.py
path('assets/', include('hub.apps.assets.urls')),

# In assets/urls.py
router.register(r"assets", AssetViewSet, basename="asset")
# Results in: /api/v1/assets/assets/
```

**After**:
```python
# In api/urls.py
path('assets/', include('hub.apps.assets.urls')),

# In assets/urls.py
router.register(r"", AssetViewSet, basename="asset")
# Results in: /api/v1/assets/
```

#### Example 2: Fix Singular Form

**Before**:
```python
router.register(r"asset", AssetViewSet, basename="asset")
# Results in: /api/v1/asset/
```

**After**:
```python
router.register(r"assets", AssetViewSet, basename="asset")
# Results in: /api/v1/assets/
```

#### Example 3: Fix Case

**Before**:
```python
router.register(r"dataContracts", DataContractViewSet)
# Results in: /api/v1/dataContracts/
```

**After**:
```python
router.register(r"data-contracts", DataContractViewSet)
# Results in: /api/v1/data-contracts/
```

### Migration Checklist

- [ ] Identify all violations using validation script
- [ ] Create migration plan with timeline
- [ ] Implement new compliant endpoints
- [ ] Add deprecation warnings to old endpoints
- [ ] Add redirects for GET requests (if applicable)
- [ ] Update API documentation
- [ ] Notify API consumers
- [ ] Monitor usage of old vs new endpoints
- [ ] Remove old endpoints after deprecation period

---

## Validation Checklist

### Pre-Implementation Checklist

Before implementing a new endpoint, verify:

- [ ] Resource name uses kebab-case
- [ ] Resource name is plural for collections
- [ ] No duplication of service/resource name in path
- [ ] Endpoint matches one of the defined patterns
- [ ] HTTP methods align with REST conventions
- [ ] Resource name is explicit and descriptive
- [ ] Action names (if any) use kebab-case verbs

### Post-Implementation Checklist

After implementing an endpoint, verify:

- [ ] Endpoint passes all validation rules
- [ ] Endpoint is documented in API reference
- [ ] Endpoint appears in OpenAPI schema
- [ ] Endpoint has appropriate tests
- [ ] Endpoint follows error handling standards
- [ ] Endpoint follows authentication/authorization standards

### Review Checklist

During code review, check:

- [ ] URL pattern follows naming standards
- [ ] No duplication violations
- [ ] Plural form is used correctly
- [ ] Kebab-case is used consistently
- [ ] Pattern matches REST conventions
- [ ] Migration from old endpoint (if applicable) is complete

---

## Appendix

### A. Current Endpoint Inventory

See `docs/api-audit/current-api-inventory.md` for complete list of current endpoints.

### B. Validation Script

See `scripts/validate-api-naming-standards.py` for automated validation.

### C. Related Documents

- [API Standards](API_STANDARDS.md) - Response formats, pagination, filtering
- [API Error Codes](API_ERROR_CODES.md) - Error handling standards
- [API Reference](API_REFERENCE.md) - Complete API reference

### D. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-28 | Initial version |

---

**Document Maintainer**: API Architecture Team
**Review Cycle**: Quarterly
**Next Review**: 2026-03-28


---

# API Naming Validation Rules for CI/CD

**Document Version**: 1.0.0
**Last Updated**: 2026-03-22
**Status**: Active
**Related**: [API Naming Standards](API_NAMING_STANDARDS.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Validation Rule Specifications](#validation-rule-specifications)
3. [Implementation Plan](#implementation-plan)
4. [Error Messages](#error-messages)
5. [CI/CD Integration](#cicd-integration)
6. [Usage](#usage)

---

## Overview

This document defines the validation rules for API naming standards that are enforced in CI/CD pipelines. These rules ensure that all API endpoints comply with the standards defined in `API_NAMING_STANDARDS.md`.

### Purpose

- **Automated Enforcement**: Catch naming violations before code is merged
- **Consistency**: Ensure all developers follow the same standards
- **Early Detection**: Identify issues during development, not in production
- **Documentation**: Provide clear error messages and suggestions

### Scope

These validation rules apply to:
- All REST API endpoints under `/api/v1/`
- URL patterns defined in Django `urls.py` files
- ViewSet router registrations
- Custom action endpoints

---

## Validation Rule Specifications

### Rule 1: No Duplication

**Rule ID**: `no_duplication`

**Description**: Service/resource names MUST NOT appear multiple times in the URL path.

**Validation Logic**:
1. Extract path segments after `/api/v1/`
2. Remove path parameters (e.g., `{id}`)
3. Check for consecutive duplicate segments
4. Flag if any segment appears twice in a row

**Severity**: Error

**Example Violations**:
- `/api/v1/assets/assets/` → Error: "assets" appears twice
- `/api/v1/contracts/contracts/` → Error: "contracts" appears twice
- `/api/v1/dq/dq/runs/` → Error: "dq" appears twice

**Fix**: Remove duplicate segment from router registration or URL pattern.

---

### Rule 2: Plural Resources

**Rule ID**: `plural_resources`

**Description**: Collection endpoints MUST use plural nouns.

**Validation Logic**:
1. Identify collection endpoints (end with `/` and no `{id}` parameter)
2. Extract resource name (first segment after `/api/v1/`)
3. Check against known singular forms
4. Flag if resource name is singular

**Severity**: Error

**Known Singular Forms**:
- `asset` → should be `assets`
- `contract` → should be `contracts`
- `dataset` → should be `datasets`
- `file` → should be `files`
- `job` → should be `jobs`
- `user` → should be `users`
- `tenant` → should be `tenants`
- `role` → should be `roles`
- `webhook` → should be `webhooks`
- `plugin` → should be `plugins`
- `order` → should be `orders`
- `listing` → should be `listings`

**Example Violations**:
- `/api/v1/asset/` → Error: Should be `assets`
- `/api/v1/contract/` → Error: Should be `contracts`

**Fix**: Change router registration to use plural form.

---

### Rule 3: Kebab-Case

**Rule ID**: `kebab_case`

**Description**: All resource names MUST use kebab-case (lowercase letters with hyphens).

**Validation Logic**:
1. Extract all path segments
2. Remove path parameters
3. Check each segment against kebab-case pattern: `^[a-z0-9-]+$`
4. Flag violations (snake_case, camelCase, PascalCase)

**Severity**: Error

**Pattern**: `^[a-z0-9-]+$`

**Example Violations**:
- `/api/v1/dataContracts/` → Error: Uses camelCase
- `/api/v1/data_contracts/` → Error: Uses snake_case
- `/api/v1/DataContracts/` → Error: Uses PascalCase

**Fix**: Convert to kebab-case (e.g., `data-contracts`).

---

### Rule 4: Pattern Consistency

**Rule ID**: `pattern_consistency`

**Description**: Endpoints MUST match one of the defined patterns.

**Validation Logic**:
1. Check against collection pattern: `^/api/v1/[a-z0-9-]+/$`
2. Check against detail pattern: `^/api/v1/[a-z0-9-]+/\{[a-z]+\}/$`
3. Check against action pattern: `^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$`
4. Check against sub-resource pattern: `^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$`
5. Flag if none match

**Severity**: Warning (can be promoted to error with `--strict`)

**Example Violations**:
- `/api/v1/create-asset/` → Warning: Doesn't match any pattern
- `/api/v1/assets-list/` → Warning: Doesn't match any pattern

**Fix**: Refactor to match one of the defined patterns.

---

### Rule 5: Explicit Naming

**Rule ID**: `explicit_naming`

**Description**: Resource names MUST be explicit and descriptive. Avoid unclear abbreviations.

**Validation Logic**:
1. Extract resource names from path segments
2. Check against list of unclear abbreviations
3. Flag if abbreviation is found

**Severity**: Warning

**Unclear Abbreviations**:
- `dc` → should be `data-contracts`
- `si` → should be `scheduled-ingestions`
- `dq` → acceptable if documented, but warn

**Example Violations**:
- `/api/v1/dc/` → Warning: Unclear abbreviation
- `/api/v1/si/` → Warning: Unclear abbreviation

**Fix**: Use explicit name or document abbreviation.

---

## Implementation Plan

### Phase 1: Validation Script (Complete)

**Status**: ✅ Complete

**Deliverables**:
- `scripts/validate_api_naming_standards.py` - Main validation script
- Supports all 5 validation rules
- Generates JSON reports
- Provides clear error messages and suggestions

**Features**:
- Extracts endpoints from Django codebase
- Validates against all rules
- Generates comprehensive reports
- Exit codes for CI/CD integration

### Phase 2: CI/CD Integration

**Status**: In Progress

**Deliverables**:
- GitHub Actions workflow for API naming validation
- Integration with existing CI pipeline
- Automated validation on PR and push

**Integration Points**:
- Run on changes to `hub/apps/**/urls.py`
- Run on changes to `hub/apps/**/views.py`
- Run on changes to API-related files

### Phase 3: Error Reporting

**Status**: In Progress

**Deliverables**:
- Structured error messages
- GitHub Actions annotations
- Artifact uploads for reports

### Phase 4: Documentation

**Status**: In Progress

**Deliverables**:
- This document (validation rules specifications)
- Error message documentation
- Usage examples

---

## Error Messages

### Error Message Format

All error messages follow this structure:

```
[RULE_ID] ENDPOINT_PATH
   Message: Human-readable error message
   Suggestion: How to fix the issue
```

### Error Messages by Rule

#### No Duplication Rule

**Error Message**:
```
[no_duplication] /api/v1/assets/assets/
   Message: Duplicate segment 'assets' appears twice in path
   Suggestion: Remove duplicate segment. Expected: /api/v1/assets/
```

**Context**: Router registration includes duplicate resource name.

**Fix**: Change router registration from `router.register(r"assets", ...)` to `router.register(r"", ...)` when already under `assets/` path.

---

#### Plural Resources Rule

**Error Message**:
```
[plural_resources] /api/v1/asset/
   Message: Resource name 'asset' should be plural
   Suggestion: Use plural form: /api/v1/assets/
```

**Context**: Collection endpoint uses singular form.

**Fix**: Change router registration to use plural: `router.register(r"assets", ...)`.

---

#### Kebab-Case Rule

**Error Message**:
```
[kebab_case] /api/v1/dataContracts/
   Message: Segment 'dataContracts' uses camelCase, should use kebab-case
   Suggestion: Use kebab-case: data-contracts
```

**Context**: Resource name uses camelCase instead of kebab-case.

**Fix**: Change to kebab-case: `router.register(r"data-contracts", ...)`.

---

#### Pattern Consistency Rule

**Error Message**:
```
[pattern_consistency] /api/v1/create-asset/
   Message: Path does not match any defined pattern
   Suggestion: Ensure path matches one of: /api/v1/{resource}/, /api/v1/{resource}/{id}/, /api/v1/{resource}/{id}/{action}/, or /api/v1/{resource}/{id}/{sub-resource}/
```

**Context**: Endpoint doesn't follow REST conventions.

**Fix**: Refactor to use POST `/api/v1/assets/` instead of `/api/v1/create-asset/`.

---

#### Explicit Naming Rule

**Error Message**:
```
[explicit_naming] /api/v1/dc/
   Message: Abbreviation 'dc' is unclear, use explicit name
   Suggestion: Use explicit name: data-contracts
```

**Context**: Resource uses unclear abbreviation.

**Fix**: Use explicit name or document abbreviation in API naming standards.

---

### Error Severity Levels

#### Error (Blocks CI/CD)

- **No Duplication**: Blocks merge
- **Plural Resources**: Blocks merge
- **Kebab-Case**: Blocks merge

#### Warning (Does Not Block)

- **Pattern Consistency**: Warning only (can be promoted with `--strict`)
- **Explicit Naming**: Warning only

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/api-naming-validation.yml`

**Triggers**:
- Push to `main` or `develop` (when API files change)
- Pull requests to `main` or `develop` (when API files change)
- Manual dispatch

**Paths**:
- `hub/apps/**/urls.py`
- `hub/apps/**/views.py`
- `scripts/validate_api_naming_standards.py`

**Steps**:
1. Checkout code
2. Set up Python
3. Install dependencies
4. Run validation script
5. Upload validation report as artifact
6. Fail if errors found

### Integration with Existing Workflows

The validation can be integrated into:
- `ci.yml` - Main CI pipeline
- `openapi-validation.yml` - API validation workflow

### Exit Codes

- `0`: All validations passed
- `1`: Validation errors found (blocks CI/CD)

---

## Usage

### Command Line

```bash
# Basic validation
python scripts/validate_api_naming_standards.py

# Strict mode (treats warnings as errors)
python scripts/validate_api_naming_standards.py --strict

# Custom output file
python scripts/validate_api_naming_standards.py --output validation-report.json
```

### In CI/CD

```yaml
- name: Validate API Naming Standards
  run: |
    python scripts/validate_api_naming_standards.py --strict
```

### Programmatic Usage

```python
from scripts.validate_api_naming_standards import APINamingStandardsValidator

validator = APINamingStandardsValidator()
result = validator.validate_all(strict=True)

if not result.passed:
    for error in result.errors:
        print(f"Error: {error.message}")
```

---

## Validation Checklist

### Pre-Merge Checklist

- [ ] All endpoints pass no duplication rule
- [ ] All collection endpoints use plural nouns
- [ ] All resource names use kebab-case
- [ ] All endpoints match defined patterns (or documented exceptions)
- [ ] No unclear abbreviations (or documented)

### CI/CD Checklist

- [ ] Validation script runs on API file changes
- [ ] Errors block merge
- [ ] Warnings are reported but don't block
- [ ] Validation reports are uploaded as artifacts
- [ ] Error messages are clear and actionable

---

## Related Documents

- [API Naming Standards](API_NAMING_STANDARDS.md) - Complete naming standards
- [API Reference](API_REFERENCE.md) - API documentation
- [CI/CD Summary](.github/workflows/CI_CD_SUMMARY.md) - CI/CD overview

---

**Document Maintainer**: API Architecture Team
**Review Cycle**: Quarterly
**Next Review**: 2026-03-28


---

# API Versioning and Deprecation

**Last Updated**: 2026-03-22

This document describes the API versioning strategy, deprecation policy, and how to use versioned endpoints.

---

## Supported Versions

Currently supported API versions:

- **v1**: Current stable version (default)

All API endpoints are under `/api/v1/` path prefix.

---

## Version Identification

### URL Path

API version is specified in the URL path:

```
GET /api/v1/assets/
POST /api/v1/datasets/
```

### Accept Header (Alternative)

API version can also be specified via Accept header:

```
Accept: application/vnd.idh.v1+json
```

---

## Version Headers

All API responses include version headers:

- **X-API-Version**: Current API version used (e.g., `v1`)
- **X-API-Supported-Versions**: Comma-separated list of supported versions (e.g., `v1`)

**Example Response Headers**:
```
HTTP/1.1 200 OK
X-API-Version: v1
X-API-Supported-Versions: v1
Content-Type: application/json
```

---

## Deprecation Policy

### Deprecation Notice Period

- **Minimum notice**: 6 months before sunset
- **Deprecation announcement**: Via release notes, API documentation, and email to API key holders
- **Sunset date**: Clearly communicated in deprecation notice

### Deprecation Headers

Deprecated endpoints include additional headers:

- **X-API-Deprecated**: Set to `true` for deprecated endpoints
- **Sunset**: RFC 8594 Sunset header with sunset date (e.g., `Sunset: Sat, 31 Dec 2026 23:59:59 GMT`)
- **Link**: Link to replacement endpoint (if available) with `rel="successor-version"`

**Example Deprecated Endpoint Response**:
```
HTTP/1.1 200 OK
X-API-Version: v1
X-API-Supported-Versions: v1
X-API-Deprecated: true
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
Link: <https://api.example.com/api/v2/new-endpoint>; rel="successor-version"
Warning: 299 - "This endpoint is deprecated and will be sunset on Sat, 31 Dec 2026 23:59:59 GMT"
```

### Deprecation Process

1. **Announcement**: Deprecation announced in release notes
2. **Mark as deprecated**: Endpoint marked with deprecation headers
3. **Migration period**: 6+ months for users to migrate
4. **Sunset**: Endpoint removed or returns 410 Gone

---

## Version Introduction

### New Major Versions

When introducing a new major version (e.g., v2):

1. **Parallel support**: Both v1 and v2 supported simultaneously
2. **Migration guide**: Comprehensive migration guide provided
3. **Deprecation notice**: v1 marked as deprecated with sunset date
4. **Sunset period**: v1 sunset after migration period (minimum 6 months)

### Breaking Changes

Breaking changes require a new major version:

- **Removed endpoints**: Endpoint removed or significantly changed
- **Changed request/response formats**: Incompatible schema changes
- **Changed authentication**: Authentication method changes
- **Changed behavior**: Significant behavioral changes

### Non-Breaking Changes

Non-breaking changes can be made within the same major version:

- **New endpoints**: New endpoints added
- **New fields**: New optional fields added to responses
- **New query parameters**: New optional query parameters
- **Bug fixes**: Behavior corrections

---

## Deprecated Endpoints

Currently deprecated endpoints:

*None at this time.*

---

## Migration Guide

### From v1 to v2 (Future)

When v2 is introduced, migration guide will be provided here.

---

## Best Practices

### Version Selection

- **Use latest stable version**: Use the latest stable version for new integrations
- **Specify version explicitly**: Always specify version in URL path or Accept header
- **Monitor deprecation notices**: Subscribe to release notes and API announcements

### Handling Deprecation

- **Monitor Sunset headers**: Check for `Sunset` header in responses
- **Plan migration**: Start migration planning when deprecation is announced
- **Test replacement endpoints**: Test replacement endpoints before sunset
- **Update integrations**: Update integrations before sunset date

### Error Handling

- **Version errors**: Handle `UNSUPPORTED_API_VERSION` errors gracefully
- **Deprecation warnings**: Log deprecation warnings for monitoring
- **Sunset errors**: Handle 410 Gone responses after sunset

---

## Related Documentation

- `docs/API_REFERENCE.md` - Complete API reference
- `docs/DEVELOPMENT_GUIDE.md` - Development guide
- Release notes - Deprecation announcements

---

# API Versioning Policy

Complete policy for API versioning, backward compatibility, and deprecation handling.

## Table of Contents

1. [Overview](#overview)
2. [Versioning Strategy](#versioning-strategy)
3. [Version Negotiation](#version-negotiation)
4. [Backward Compatibility](#backward-compatibility)
5. [Deprecation Policy](#deprecation-policy)
6. [Breaking Changes](#breaking-changes)
7. [Migration Guidelines](#migration-guidelines)

---

## Overview

This document defines the API versioning policy for the Data Interoperability Hub, ensuring stable, predictable API evolution while maintaining backward compatibility.

**Key Principles**:
- **URL-based versioning**: Major versions in URL path (`/api/v1/`, `/api/v2/`)
- **Backward compatibility**: Same major version maintains compatibility
- **Deprecation warnings**: Clear deprecation notices with migration paths
- **Version negotiation**: Automatic version detection and validation

---

## Versioning Strategy

### URL-Based Versioning (Primary)

The API uses URL-based versioning for major versions:

- `/api/v1/...` - API version 1 (current)
- `/api/v2/...` - API version 2 (future)
- `/api/v3/...` - API version 3 (future)

**Benefits**:
- Clear and explicit version in URL
- Easy to understand and use
- Supports multiple versions simultaneously
- No ambiguity about which version is being used

### Semantic Versioning

API versions follow semantic versioning (major.minor.patch):

- **Major version** (v1, v2, v3): Breaking changes require new major version
- **Minor version** (v1.1, v1.2): Additive changes within same major version
- **Patch version** (v1.0.1, v1.0.2): Bug fixes, non-breaking changes

**Note**: Only major versions appear in the URL path. Minor and patch versions are tracked internally.

### Version Format

- **URL Path**: `/api/v1/` (major version only)
- **Internal Tracking**: `v1.0.0` (major.minor.patch)
- **Header Format**: `application/vnd.idh.v1+json` (major version)

---

## Version Negotiation

### Path-Based (Primary Method)

Version is extracted from URL path:

```http
GET /api/v1/assets/
```

The version in the path is the **source of truth**.

### Header-Based (Optional)

Version can be specified in Accept header:

```http
GET /api/v1/assets/
Accept: application/vnd.idh.v1+json
```

**Rules**:
- Header version is optional
- If both path and header versions are provided, they must match
- If they don't match, path version takes precedence (with warning logged)
- Header version alone (without path version) is supported

### Default Version

If no version is specified:
- Defaults to current version (v1)
- No version negotiation required
- Backward compatible behavior

### Version Validation

All API requests are validated:
- Unsupported versions return `400 Bad Request`
- Error response includes supported versions
- Current version is always supported

---

## Backward Compatibility

### Compatibility Guarantees

Within the same major version (e.g., v1.x.x):

#### ✅ Allowed Changes (Backward Compatible)

1. **New Endpoints**: Can be added
   - Example: Adding `/api/v1/new-feature/` endpoint

2. **Optional Request Fields**: Can be added
   - Example: Adding optional `description` field to asset creation

3. **New Response Fields**: Can be added
   - Example: Adding `metadata` field to asset response

4. **New Error Codes**: Can be added (if backward-compatible)
   - Example: Adding new validation error codes

5. **Minor/Patch Updates**: Bug fixes, performance improvements
   - Example: Fixing pagination bug, improving response time

#### ❌ Breaking Changes (Require New Major Version)

1. **Removed Endpoints**: Cannot remove endpoints
   - Must deprecate first, then remove in next major version

2. **Required Fields**: Cannot add required fields
   - Must remain optional or use new major version

3. **Removed Fields**: Cannot remove fields
   - Must deprecate first, then remove in next major version

4. **Type Changes**: Cannot change field types
   - Example: Changing `id` from string to integer

5. **Behavior Changes**: Cannot change endpoint behavior
   - Example: Changing default sorting order

### Compatibility Testing

All changes within same major version must:
- Pass backward compatibility tests
- Not break existing clients
- Maintain API contracts

---

## Deprecation Policy

### Deprecation Timeline

1. **Deprecation Announcement**: Endpoint marked as deprecated
   - Deprecation warning added to responses
   - Documentation updated
   - Migration guide provided

2. **6 Months Notice**: Minimum 6 months before sunset
   - Deprecated endpoints remain functional
   - Warning headers in all responses
   - Migration guide available

3. **Sunset Date**: Endpoint removed after sunset date
   - Endpoint returns `410 Gone` after sunset
   - Migration to new endpoint required

### Deprecation Warnings

Deprecated endpoints include warning headers (RFC 7234):

```
Warning: 299 - "Deprecated API", sunset="2024-07-01T00:00:00Z", link="/api/v2/new-endpoint/"
```

**Warning Header Fields**:
- `299`: Deprecated API status code
- `sunset`: Sunset date (ISO 8601 format)
- `link`: Replacement endpoint URL

### Deprecation in Response Body

For JSON responses, deprecation info is also included in response body:

```json
{
  "data": {...},
  "meta": {
    "deprecated": true,
    "deprecated_since": "2024-01-01",
    "sunset_date": "2024-07-01T00:00:00Z",
    "replacement": "/api/v2/new-endpoint/",
    "migration_guide": "https://docs.example.com/migration"
  }
}
```

### Registering Deprecated Endpoints

```python
from hub.apps.api.versioning import APIVersionManager, DeprecatedEndpoint
from django.utils import timezone
from datetime import timedelta

endpoint = DeprecatedEndpoint(
    path="/api/v1/old-endpoint/",
    method="GET",
    deprecated_since="2024-01-01",
    sunset_date=(timezone.now() + timedelta(days=180)).isoformat(),  # 6 months
    replacement="/api/v2/new-endpoint/",
    migration_guide="https://docs.example.com/migration-guide"
)

APIVersionManager.register_deprecated_endpoint(endpoint)
```

---

## Breaking Changes

### What Constitutes a Breaking Change

A breaking change requires a new major version:

1. **Removed Endpoints**: Endpoint no longer available
2. **Removed Fields**: Field removed from request/response
3. **Required Fields**: Optional field becomes required
4. **Type Changes**: Field type changed (string → integer)
5. **Behavior Changes**: Endpoint behavior changed
6. **Authentication Changes**: Authentication method changed
7. **Error Format Changes**: Error response format changed

### Breaking Change Process

1. **Plan**: Identify breaking change and impact
2. **Document**: Document breaking change and migration path
3. **Deprecate**: Deprecate old endpoint/field in current version
4. **Implement**: Implement new version with breaking change
5. **Migrate**: Provide migration guide and tools
6. **Sunset**: Remove deprecated endpoint after sunset period

---

## Migration Guidelines

### For API Consumers

1. **Monitor Deprecation Warnings**: Check `Warning` header in responses
2. **Plan Migration**: Review migration guide and plan migration
3. **Test New Version**: Test against new version before migration
4. **Migrate Gradually**: Migrate endpoints one at a time
5. **Update Documentation**: Update client code and documentation

### For API Developers

1. **Follow Deprecation Policy**: Always deprecate before removing
2. **Provide Migration Guide**: Clear migration path for consumers
3. **Monitor Usage**: Track usage of deprecated endpoints
4. **Communicate Changes**: Announce deprecations in changelog
5. **Support Both Versions**: Support both old and new during transition

### Migration Checklist

- [ ] Identify endpoints/fields to deprecate
- [ ] Create replacement endpoint/field
- [ ] Register deprecated endpoint
- [ ] Write migration guide
- [ ] Update API documentation
- [ ] Announce deprecation
- [ ] Monitor usage
- [ ] Set sunset date (6+ months)
- [ ] Remove after sunset

---

## Version Support

### Current Version

- **v1.0.0**: Current stable version
- **Status**: Fully supported
- **End of Life**: TBD (will be announced 12 months in advance)

### Supported Versions

- **v1.x.x**: All minor/patch versions within v1
- **Backward Compatible**: Yes
- **Support Period**: Until v2 is released + 12 months

### Unsupported Versions

- **v0.x.x**: Pre-release versions (not supported)
- **v2.x.x**: Future versions (not yet released)

---

## Best Practices

### Version Selection

1. **Use Path-Based**: Primary method for versioning
2. **Header as Fallback**: Use headers for version negotiation if needed
3. **Default to Current**: Default to current version if not specified

### Backward Compatibility

1. **Additive Changes Only**: Only add, never remove in same major version
2. **Optional Fields**: Make new fields optional
3. **Version Documentation**: Document version changes in changelog

### Deprecation

1. **6 Months Notice**: Provide at least 6 months notice
2. **Clear Migration Path**: Provide clear migration guide
3. **Monitor Usage**: Track usage of deprecated endpoints
4. **Gradual Migration**: Support both old and new endpoints during transition

---

## Examples

### Example 1: Adding New Endpoint (v1.1.0)

**Change**: Add new `/api/v1/analytics/` endpoint

**Compatibility**: ✅ Backward compatible (new endpoint)

**Action**: No deprecation needed, just add endpoint

### Example 2: Adding Optional Field (v1.2.0)

**Change**: Add optional `tags` field to asset creation

**Compatibility**: ✅ Backward compatible (optional field)

**Action**: No deprecation needed, field is optional

### Example 3: Deprecating Endpoint (v1.3.0)

**Change**: Deprecate `/api/v1/old-endpoint/` in favor of `/api/v2/new-endpoint/`

**Compatibility**: ✅ Backward compatible (endpoint still works)

**Action**:
1. Register deprecated endpoint
2. Add deprecation warnings
3. Provide migration guide
4. Set sunset date (6+ months)

### Example 4: Breaking Change (v2.0.0)

**Change**: Remove `legacy_field` from response

**Compatibility**: ❌ Breaking change

**Action**:
1. Create v2 with breaking change
2. Deprecate v1 endpoint (if applicable)
3. Provide migration guide
4. Support both v1 and v2 during transition

---

**Last Updated**: 2026-03-22  
**Maintainer**: Engineering Team  
**Status**: ✅ Complete

---

# API Best Practices Guide

This guide provides best practices for using the Data Interoperability Hub API effectively.

## Table of Contents

1. [Authentication](#authentication)
2. [Request Format](#request-format)
3. [Response Handling](#response-handling)
4. [Error Handling](#error-handling)
5. [Pagination](#pagination)
6. [Filtering and Sorting](#filtering-and-sorting)
7. [Rate Limiting](#rate-limiting)
8. [Caching](#caching)
9. [Performance Optimization](#performance-optimization)
10. [Versioning](#versioning)

---

## Authentication

### Bearer Token Authentication

All API requests require authentication using Bearer tokens:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.example.com/api/v1/contracts/
```

### Token Management

- **Token Expiration**: Tokens expire after 24 hours (configurable)
- **Token Refresh**: Use the refresh endpoint to obtain new tokens
- **Token Storage**: Store tokens securely, never commit to version control

### Best Practices

1. **Always use HTTPS**: Never send tokens over unencrypted connections
2. **Rotate tokens regularly**: Generate new tokens periodically
3. **Use token scopes**: Request only necessary permissions
4. **Handle token expiration**: Implement token refresh logic

---

## Request Format

### Content-Type Headers

Always include appropriate Content-Type headers:

```bash
# JSON requests
Content-Type: application/json

# Form data
Content-Type: application/x-www-form-urlencoded

# File uploads
Content-Type: multipart/form-data
```

### Request Body Format

Use JSON for all request bodies:

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### Best Practices

1. **Validate input**: Validate all input data before sending
2. **Use appropriate HTTP methods**: GET for reads, POST for creates, PATCH for updates
3. **Include required fields**: Always include all required fields
4. **Follow naming conventions**: Use snake_case for field names

---

## Response Handling

### Success Responses

Success responses follow standard HTTP status codes:

- `200 OK`: Successful GET, PUT, PATCH requests
- `201 Created`: Successful POST requests
- `204 No Content`: Successful DELETE requests

### Response Format

All responses follow a consistent format:

```json
{
  "id": "uuid",
  "field1": "value1",
  "field2": "value2",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Best Practices

1. **Check status codes**: Always verify HTTP status codes
2. **Handle pagination**: Use pagination for large result sets
3. **Parse timestamps**: Convert ISO 8601 timestamps to local time
4. **Validate response structure**: Verify response structure matches expectations

---

## Error Handling

### Error Response Format

All errors follow a standardized format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "uuid",
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

### Error Codes

Common error codes:

- `VALIDATION_ERROR`: Request validation failed (400)
- `AUTH_UNAUTHORIZED`: Authentication required (401)
- `AUTH_FORBIDDEN`: Permission denied (403)
- `NOT_FOUND`: Resource not found (404)
- `CONFLICT_ERROR`: Resource conflict (409)
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded (429)
- `INTERNAL_ERROR`: Internal server error (500)
- `SERVICE_UNAVAILABLE`: Service unavailable (503)

### Best Practices

1. **Handle all error codes**: Implement handling for all possible error codes
2. **Display user-friendly messages**: Show error.message to users
3. **Log error details**: Log error.details for debugging
4. **Retry on transient errors**: Retry on 5xx errors with exponential backoff
5. **Handle rate limits**: Implement rate limit handling with retry-after

---

## Pagination

### Offset-Based Pagination

Use `page` and `page_size` parameters:

```bash
GET /api/v1/contracts/?page=1&page_size=50
```

### Pagination Response

Paginated responses include metadata:

```json
{
  "count": 1000,
  "page": 1,
  "page_size": 50,
  "total_pages": 20,
  "has_next": true,
  "has_previous": false,
  "next_page": 2,
  "previous_page": null,
  "results": [...]
}
```

### Best Practices

1. **Use appropriate page sizes**: Default to 50, max 100
2. **Handle empty results**: Check for empty results arrays
3. **Respect total_pages**: Don't request pages beyond total_pages
4. **Cache paginated results**: Cache results when appropriate

---

## Filtering and Sorting

### Filtering

Use query parameters for filtering:

```bash
GET /api/v1/contracts/?owner_email=user@example.com&tag=production
```

### Sorting

Use `ordering` parameter for sorting:

```bash
GET /api/v1/contracts/?ordering=-created_at,quality_score
```

### Best Practices

1. **Combine filters**: Use multiple filters for precise results
2. **Use indexes**: Prefer indexed fields for filtering
3. **Limit filter combinations**: Too many filters can slow queries
4. **Cache filtered results**: Cache frequently used filter combinations

---

## Rate Limiting

### Rate Limit Headers

Rate limit information in response headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

### Rate Limit Handling

When rate limited (429), check `Retry-After` header:

```
Retry-After: 60
```

### Best Practices

1. **Monitor rate limits**: Track remaining requests
2. **Implement backoff**: Use exponential backoff on rate limits
3. **Batch requests**: Batch multiple operations when possible
4. **Use webhooks**: Subscribe to webhooks instead of polling

---

## Caching

### Cache Headers

Cache control headers:

```
Cache-Control: public, max-age=300
ETag: "abc123"
Last-Modified: Wed, 15 Jan 2025 10:30:00 GMT
```

### Cache Invalidation

Cache invalidation on updates:

- Contract updates invalidate contract cache
- Lineage updates invalidate lineage cache
- Query result cache invalidated on data changes

### Best Practices

1. **Respect cache headers**: Follow Cache-Control directives
2. **Use ETags**: Implement conditional requests with ETags
3. **Cache at appropriate levels**: Cache at client, proxy, and server levels
4. **Invalidate on updates**: Clear cache when data changes

---

## Performance Optimization

### Query Optimization

Optimize queries for performance:

1. **Use indexes**: Filter on indexed fields
2. **Limit fields**: Use `fields` parameter to limit response fields
3. **Avoid N+1 queries**: Use `select_related` and `prefetch_related`
4. **Batch operations**: Batch multiple operations

### Large JSON Handling

For large contract JSON:

1. **Use compression**: Enable gzip compression
2. **Stream responses**: Stream large responses when possible
3. **Use pagination**: Paginate large result sets
4. **Optimize JSON size**: Keep JSON under 1MB

### Best Practices

1. **Monitor performance**: Track query execution times
2. **Use caching**: Cache frequently accessed data
3. **Optimize payloads**: Minimize request/response payloads
4. **Use async operations**: Use async endpoints for long-running operations

---

## Versioning

### API Versioning

API versioning via URL path:

```
/api/v1/contracts/
/api/v2/contracts/  # Future version
```

### Version Compatibility

- **Backward compatibility**: v1 endpoints remain stable
- **Deprecation warnings**: Deprecated endpoints include warnings
- **Migration guides**: Migration guides for version upgrades

### Best Practices

1. **Pin API version**: Always specify API version in URLs
2. **Monitor deprecations**: Watch for deprecation warnings
3. **Plan migrations**: Plan migrations to new versions
4. **Test version changes**: Test thoroughly before upgrading

---

## Additional Resources

- [API Documentation](./API_DOCUMENTATION.md)
- [Error Code Reference](./API_ERROR_CODES.md)
- [SDK Documentation](./SDK_DOCUMENTATION.md)
- [Webhook API](./WEBHOOK_API.md)


---

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


---

# API Paths: Default vs Optional Traefik Entrypoint

**Last Updated**: 2026-03-22

This document describes how the frontend and API can be reached: the **default path** (direct to api-service) and the **optional path** via Traefik as a single entrypoint.

---

## Overview

| Path | Traffic flow | When to use |
|------|--------------|-------------|
| **Default** | Frontend → api-service directly | Default; no Traefik/API Gateway in path |
| **Optional (via Traefik)** | Browser → Traefik → (Frontend or API Gateway → api-service) | Single entrypoint, TLS, API key at gateway |

---

## 1. Default path (no Traefik)

**Behaviour**: The frontend is built with `VITE_API_BASE_URL` pointing at the api-service (Django). All API and WebSocket traffic goes directly from the browser to api-service; it does **not** go through Traefik or the FastAPI API Gateway.

### Configuration

- **Frontend**: Set `VITE_API_BASE_URL` to the api-service base URL including `/api/v1`.
  - In Docker Compose (default): `VITE_API_BASE_URL=http://api-service:8000/api/v1` (for in-cluster) or for browser e.g. `http://localhost:8000/api/v1`.
  - Do **not** set `VITE_USE_TRAEFIK_ENTRYPOINT` (or set it to `false`).
- **Auth**: Session/cookie and Bearer token auth are handled by Django (api-service). No API key is required at the edge.

### Example (Docker Compose)

```bash
# .env or docker-compose environment
VITE_API_BASE_URL=http://api-service:8000/api/v1
VITE_WS_BASE_URL=ws://api-service:8000
# Leave unset or false for default path
# VITE_USE_TRAEFIK_ENTRYPOINT=false
```

When the app is served from the same host as the user (e.g. frontend at `http://localhost:3000` and API at `http://localhost:8000`), use:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 2. Optional path: via Traefik (single entrypoint)

**Behaviour**: All traffic enters through Traefik. Traefik routes:

- `GET /` (and other non-API paths) → **frontend** service (static/app).
- `GET /api/v1/...` → **API Gateway** (FastAPI) → api-service (Django).

So the browser talks only to one origin (e.g. `https://hub.example.com`); TLS and routing are handled by Traefik.

### Configuration

1. **Traefik**
   Use the dynamic routes in `infrastructure/traefik/dynamic/routes.yml`, which include:
   - A router for `/api/v1` → api-gateway (and optionally host-based API router).
   - A router for `/` (catch-all) → frontend service (when “single entrypoint” is enabled).

2. **Frontend**
   - Set `VITE_USE_TRAEFIK_ENTRYPOINT=true`.
   - Set `VITE_API_BASE_URL` to the **Traefik** API base URL (same origin as the app), e.g. `https://api.hub.local/api/v1` or `https://hub.example.com/api/v1` so that API calls go through Traefik → API Gateway.
   - If you use a dedicated API host (e.g. `api.hub.local`), set `VITE_API_BASE_URL=https://api.hub.local/api/v1` and ensure CORS and cookies are configured for that origin.

3. **Auth**
   - **Via API Gateway (Traefik → api-gateway)**: API key (e.g. `X-API-Key` or `Authorization`) is validated by the FastAPI API Gateway. Session/cookie auth may still be used if the gateway forwards cookies to api-service and the frontend uses the same origin or allowed CORS.
   - **Direct api-service (default path)**: Session/cookie and Bearer token only; no gateway API key.

### Example (Traefik as entrypoint)

```bash
# Frontend build/runtime (same origin for app and API)
VITE_USE_TRAEFIK_ENTRYPOINT=true
VITE_API_BASE_URL=https://hub.example.com/api/v1
VITE_WS_BASE_URL=wss://hub.example.com

# Or API on a separate host
VITE_USE_TRAEFIK_ENTRYPOINT=true
VITE_API_BASE_URL=https://api.hub.local/api/v1
VITE_WS_BASE_URL=wss://api.hub.local
```

---

## 3. Gateway-originated headers

When a request reaches api-service **via the API Gateway** (Traefik → API Gateway → api-service), the gateway sets the following headers on the request to the backend:

| Header | Set by gateway | Description |
|--------|----------------|-------------|
| `X-Gateway-Tenant-ID` | Yes | Tenant ID associated with the validated API key |
| `X-Gateway-User-ID` | Yes (if user-scoped key) | User ID associated with the API key |
| `X-Gateway-Request-ID` | Yes | Request ID for tracing/correlation |

**api-service behavior (ignore, do not trust for auth)**
api-service **ignores** these headers for authentication and authorization. Tenant and user are derived **only** from api-service’s own auth:

- **JWT** (Bearer token): tenant/user from token payload and DB lookup
- **API key** (ApiKey / X-API-Key): tenant/user from API key lookup in the hub DB
- **Session/cookie**: tenant/user from Django session

The gateway sets `X-Gateway-*` for logging and correlation; the backend does **not** use them to set `request.tenant_id`, `request.tenant`, or `request.user`. So:

- **(a) api-service ignores** gateway-originated headers and derives tenant/user from its own auth.
- **(b) Trust is not used** — there is no “trust when request is from gateway” path. If trust were introduced later, it would require verifying that the request actually came from the gateway (e.g. shared secret or network isolation) and must be documented and tested.

**Security (forged headers)**
Because api-service does not read `X-Gateway-Tenant-ID` or `X-Gateway-User-ID` for auth, a direct request to api-service with forged `X-Gateway-Tenant-ID` / `X-Gateway-User-ID` **cannot** override the authenticated tenant or user. Cross-tenant escalation via these headers is not possible. A regression test in `tests/security/test_gateway_headers_forged.py` asserts that forged gateway headers do not change tenant/user context (no mocks).

---

## 4. Auth model per path

| Path | Auth at edge | Notes |
|------|----------------|-------|
| **(1) Frontend → api-service direct** | Session/cookie or JWT (Django) | No API key required. Same as when not using Traefik. |
| **(2) Client → Traefik → API Gateway → api-service** | API key required | Session/cookie is **not** supported on this path; API key (e.g. `X-API-Key` or `Authorization: ApiKey <key>`) is required. Gateway validates the key and forwards the request; api-service validates the key again and derives tenant/user from it. |

When using the gateway path, configure API keys in the hub (tenant/developer) and pass the key in requests as documented in the API Gateway (e.g. `X-API-Key` or `Authorization: ApiKey <key>`).

---

## 5. Rate limiting

Rate limiting depends on the path; limits and response headers may differ.

| Path | Rate limiting | Notes |
|------|----------------|-------|
| **Traefik → API Gateway → api-service** | **API Gateway** (FastAPI, `services/api-gateway/`): tier-based (FREE, PRO, ENTERPRISE), per-tenant and per-API-key when configured. Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After` on 429. |
| **Frontend → api-service direct** | **Django** `hub.apps.rate_limiting.middleware.RateLimitMiddleware`: per-tenant and per-user limits. Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and optionally `X-RateLimit-User-Limit`, `X-RateLimit-User-Remaining`. |

When traffic goes through the API Gateway, rate limiting is applied at the gateway first; api-service may apply its own limits on the forwarded request. When traffic hits api-service directly, only Django rate limiting applies. See `docs/ARCHITECTURE.md` (BaaS / API Gateway) and `hub/apps/rate_limiting/` for implementation details.

---

## 6. Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | Yes (for API calls) | Base URL for the REST API including `/api/v1`. Default path: api-service URL. Traefik path: Traefik entrypoint URL (e.g. `https://api.hub.local/api/v1`). |
| `VITE_USE_TRAEFIK_ENTRYPOINT` | No | Set to `true` when the app is served and the API is reached via Traefik (single entrypoint). When `true`, the frontend uses `VITE_API_BASE_URL` as the Traefik API base. Default: unset/false (direct api-service). |
| `VITE_WS_BASE_URL` | No (optional) | WebSocket base URL (e.g. `ws://api-service:8000` or `wss://api.hub.local`). |

Build-time note: Vite embeds these at build time. Rebuild the frontend after changing `VITE_*` values.

---

## 7. Integration test (no mocks)

When Traefik is used as the single entrypoint, an integration test verifies routing with real services:

- **Location**: `tests/integration/test_traefik_routing.py`
- **Run (recommended)**: `./scripts/run_phase10_traefik_routing_tests.sh` — starts required services and runs tests inside api-service, hitting Traefik at `https://traefik:443`.
- **Run manually**: Start Traefik, frontend, api-gateway, api-service (and dependencies) with Docker Compose, then:
  ```bash
  docker compose exec -e PYTEST_DOCKER_COMPOSE_RUNTIME=1 -e TRAEFIK_BASE_URL=https://traefik:443 api-service \
    python -m pytest tests/integration/test_traefik_routing.py -v -m 'integration and docker_compose_runtime'
  ```
- **Assertions**:
  - `GET /` via Traefik returns 200 and HTML from the frontend.
  - `GET /api/v1/health` via Traefik returns 200 and JSON from the API Gateway (aggregate health with `status` and `backend_services`).

No mocks; real Traefik, frontend, api-gateway, and api-service are used.

---

## 8. URLs and health checks when Traefik is the entrypoint

- **Frontend**: Served at the Traefik host/port and path `/` (e.g. `https://hub.example.com/`). Health: Traefik routes `/` to the frontend service; the frontend container’s own health check remains on the service (e.g. `http://frontend:80/`).
- **API**: `https://<traefik-host>/api/v1/...` or `https://api.hub.local/api/v1/...` (if using the host-based API router). Health: e.g. `GET /api/v1/health` or the gateway’s `/health` behind Traefik; Traefik forwards to the API Gateway, which then talks to backends.
- **Traefik**: Dashboard and internal APIs are configured separately (e.g. `traefik.hub.local`); see `infrastructure/traefik/` and docker-compose.

---

## 9. Summary

- **Default**: Set `VITE_API_BASE_URL` to api-service (e.g. `http://api-service:8000/api/v1`). Do not set `VITE_USE_TRAEFIK_ENTRYPOINT`. Auth is session/Bearer on api-service.
- **Optional (Traefik)**: Set `VITE_USE_TRAEFIK_ENTRYPOINT=true` and `VITE_API_BASE_URL` to the Traefik API base (e.g. `https://api.hub.local/api/v1`). Auth at the edge is API key at the gateway; document session/Bearer if used end-to-end.

---

# Endpoint Pattern Migration Guide

**Date**: 2025-01-15
**Status**: ✅ Complete

## Overview

This guide documents the migration from old endpoint patterns to standardized endpoint patterns for compliance and data quality (DQ) runs.

## What Changed

### Old Patterns (Deprecated)

- Compliance runs: `/api/v1/compliance/compliance-runs/`
- Data quality runs: `/api/v1/dq/dq-runs/`

### New Patterns (Standardized)

- Compliance runs: `/api/v1/compliance/runs/`
- Data quality runs: `/api/v1/dq/runs/`

## Migration Timeline

- **Announcement**: 2025-01-10
- **Migration Start**: 2025-01-15
- **Old Patterns Removed**: 2025-01-15
- **Support Period**: Old patterns no longer supported

## Affected Endpoints

### Compliance Endpoints

| Old Pattern | New Pattern | Method | Description |
|------------|------------|--------|-------------|
| `/api/v1/compliance/compliance-runs/` | `/api/v1/compliance/runs/` | GET, POST | List/create compliance runs |
| `/api/v1/compliance/compliance-runs/{id}/` | `/api/v1/compliance/runs/{id}/` | GET, PUT, PATCH, DELETE | Get/update/delete compliance run |
| `/api/v1/compliance/compliance-runs/{id}/results/` | `/api/v1/compliance/runs/{id}/results/` | GET | Get compliance run results |

### Data Quality Endpoints

| Old Pattern | New Pattern | Method | Description |
|------------|------------|--------|-------------|
| `/api/v1/dq/dq-runs/` | `/api/v1/dq/runs/` | GET, POST | List/create DQ runs |
| `/api/v1/dq/dq-runs/{id}/` | `/api/v1/dq/runs/{id}/` | GET, PUT, PATCH, DELETE | Get/update/delete DQ run |
| `/api/v1/dq/dq-runs/{id}/results/` | `/api/v1/dq/runs/{id}/results/` | GET | Get DQ run results |

## Migration Steps

### 1. Update API Client Code

#### Python SDK

**Before:**
```python
# Old pattern
response = client.get('/api/v1/compliance/compliance-runs/')
```

**After:**
```python
# New pattern
response = client.get('/api/v1/compliance/runs/')
```

#### JavaScript SDK

**Before:**
```javascript
// Old pattern
const response = await fetch('/api/v1/compliance/compliance-runs/');
```

**After:**
```javascript
// New pattern
const response = await fetch('/api/v1/compliance/runs/');
```

#### CLI

**Before:**
```bash
# Old pattern
hub compliance-runs list
```

**After:**
```bash
# New pattern
hub compliance runs list
```

### 2. Update Configuration Files

#### API Gateway Rules

**Before:**
```yaml
routes:
  - path: /api/v1/compliance/compliance-runs/
    service: compliance-service
```

**After:**
```yaml
routes:
  - path: /api/v1/compliance/runs/
    service: compliance-service
```

#### Monitoring Configuration

**Before:**
```yaml
metrics:
  - endpoint: /api/v1/compliance/compliance-runs/
    name: compliance_runs_total
```

**After:**
```yaml
metrics:
  - endpoint: /api/v1/compliance/runs/
    name: compliance_runs_total
```

### 3. Update Documentation

All documentation has been updated to use the new patterns. If you find any references to old patterns, please update them:

- Developer guides
- API reference documentation
- Integration guides
- Code examples

### 4. Update Tests

**Before:**
```python
def test_compliance_runs():
    response = client.get('/api/v1/compliance/compliance-runs/')
    assert response.status_code == 200
```

**After:**
```python
def test_compliance_runs():
    response = client.get('/api/v1/compliance/runs/')
    assert response.status_code == 200
```

## Verification

### Check Your Code

Use the following script to find old patterns in your codebase:

```bash
# Search for old compliance patterns
grep -r "compliance-runs" --include="*.py" --include="*.js" --include="*.ts" .

# Search for old DQ patterns
grep -r "dq-runs" --include="*.py" --include="*.js" --include="*.ts" .
```

### Verify Endpoints Work

Test the new endpoints:

```bash
# Compliance runs
curl -X GET http://localhost:8000/api/v1/compliance/runs/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# DQ runs
curl -X GET http://localhost:8000/api/v1/dq/runs/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Breaking Changes

### Old Endpoints Return 404

Old endpoint patterns (`/compliance-runs/` and `/dq-runs/`) now return `404 Not Found`. Update all references to use the new patterns.

### API Client Updates Required

All API clients (Python SDK, JavaScript SDK, CLI) have been updated. Ensure you're using the latest versions:

- Python SDK: `>=1.0.0`
- JavaScript SDK: `>=1.0.0`
- CLI: `>=1.0.0`

## Benefits of Standardization

1. **Consistency**: All endpoints follow the same pattern (`/runs/` instead of `/compliance-runs/` or `/dq-runs/`)
2. **Simplicity**: Shorter, cleaner URLs
3. **Maintainability**: Easier to understand and maintain
4. **Scalability**: Pattern can be extended to other run types

## Support

If you encounter issues during migration:

1. Check this guide for common migration steps
2. Review the [API Reference](API_REFERENCE.md) for current endpoint documentation
3. Contact the development team for assistance

## Related Documentation

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md) - Detailed endpoint documentation
- [API Standards](API_STANDARDS.md) - API consistency standards
- [Developer Onboarding](DEVELOPER_ONBOARDING.md) - Developer setup guide

---

**Last Updated**: 2026-03-22
**Version**: 1.0.0


---

## Phase 117+ API Scopes (Added)

### API Key Scopes

API keys can be scoped to specific resource types and access levels:

| Scope | Description |
|-------|-------------|
| `assets:read` | Read access to assets |
| `assets:write` | Create/update/delete assets |
| `contracts:read` | Read access to contracts |
| `contracts:write` | Create/update/delete contracts |
| `datasets:read` | Read access to datasets |
| `datasets:write` | Create/update datasets |
| `files:read` | Read/download files |
| `files:write` | Upload/delete files |
| `ml:read` | Read ML models, training jobs, deployments |
| `ml:write` | Deploy/undeploy models, submit training jobs, link datasets |
| `transformation:read` | Read transformation pipelines and runs |
| `transformation:write` | Create/update/delete/run transformation pipelines |
| `marketplace:read` | Read listings, orders, entitlements |
| `marketplace:write` | Create/publish listings, manage orders |
| `governance:read` | Read access requests, retention policies |
| `governance:write` | Create/approve/reject access requests |
| `billing:read` | Read subscriptions, invoices, usage |
| `billing:admin` | Process refunds, manage plans (admin-only) |
| `baas:read` | Read BaaS usage, documentation |
| `baas:write` | Manage API keys |
| `virtualization:read` | Read virtual datasets, query results |
| `virtualization:write` | Create/update virtual datasets, execute queries |

Scopes are enforced at the middleware level. API keys without explicit scopes have full access (legacy behavior).
