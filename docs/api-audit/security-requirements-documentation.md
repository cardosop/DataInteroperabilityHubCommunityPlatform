# API Security Requirements Documentation

**Task**: 0.4.5 - Document security requirements  
**Status**: ✅ Complete  
**Date**: 2025-12-13

---

## Overview

This document provides comprehensive security requirements for all missing APIs in the Data Interoperability Hub. It covers authentication methods, authorization rules, rate limiting requirements, and input validation requirements.

---

## Table of Contents

1. [Authentication Methods](#authentication-methods)
2. [Authorization Rules](#authorization-rules)
3. [Rate Limiting Requirements](#rate-limiting-requirements)
4. [Input Validation Requirements](#input-validation-requirements)
5. [Security Best Practices](#security-best-practices)
6. [API-Specific Security Requirements](#api-specific-security-requirements)

---

## Authentication Methods

### JWT Bearer Token Authentication

**Method**: HTTP Bearer Token  
**Header**: `Authorization: Bearer <token>`

#### Token Format

- **Type**: JWT (JSON Web Token)
- **Algorithm**: HS256 (HMAC SHA-256)
- **Structure**: `{header}.{payload}.{signature}`
- **Expiration**: Access tokens expire after 1 hour (3600 seconds)
- **Refresh**: Refresh tokens available for token renewal

#### Token Claims

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
  "email": "user@example.com",
  "roles": ["DATA_PROVIDER"],
  "scopes": ["assets:read", "assets:write"],
  "exp": 1736868000,
  "iat": 1736864400,
  "token_type": "access"
}
```

#### Usage

```bash
# Example request with JWT token
curl -X GET https://api.datahub.example.com/api/v1/auth/me/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Error Responses

- **401 Unauthorized**: Invalid, expired, or missing token
- **403 Forbidden**: Token valid but insufficient permissions

---

### API Key Authentication

**Method**: API Key  
**Headers**: 
- `Authorization: ApiKey <key>` (preferred)
- `X-API-Key: <key>` (alternative)

#### API Key Format

- **Type**: UUID v4
- **Length**: 36 characters (with hyphens)
- **Example**: `550e8400-e29b-41d4-a716-446655440000`
- **Storage**: Hashed in database (SHA-256)
- **Expiration**: Configurable per key (optional)

#### API Key Scopes

API keys can have scopes that limit their access:

- `assets:read` - Read assets
- `assets:write` - Create/update assets
- `assets:delete` - Delete assets
- `contracts:read` - Read contracts
- `contracts:write` - Create/update contracts
- `contracts:validate` - Validate contracts
- `datasets:read` - Read datasets
- `datasets:write` - Create/update datasets
- `marketplace:read` - Browse marketplace
- `marketplace:purchase` - Purchase assets
- `compliance:read` - Read compliance reports
- `compliance:run` - Run compliance scans
- `dq:read` - Read data quality results
- `dq:run` - Run data quality checks
- `admin:*` - All admin operations (tenant-scoped)

#### Usage

```bash
# Example request with API key (preferred method)
curl -X GET https://api.datahub.example.com/api/v1/assets/ \
  -H "Authorization: ApiKey 550e8400-e29b-41d4-a716-446655440000"

# Alternative method
curl -X GET https://api.datahub.example.com/api/v1/assets/ \
  -H "X-API-Key: 550e8400-e29b-41d4-a716-446655440000"
```

#### Error Responses

- **401 Unauthorized**: Invalid, expired, or missing API key
- **403 Forbidden**: API key valid but insufficient scopes

---

### Authentication Requirements by Endpoint

| Endpoint | Authentication Required | Methods Supported |
|----------|------------------------|-------------------|
| `POST /auth/register/` | ❌ No (public) | None |
| `GET /auth/me/` | ✅ Yes | JWT, API Key |
| `GET /scheduled-ingestions/{id}/credentials/` | ✅ Yes | JWT, API Key |
| `POST /scheduled-ingestions/{id}/credentials/test/` | ✅ Yes | JWT, API Key |
| `POST /ai/natural-language-search/` | ✅ Yes | JWT, API Key |
| `POST /ai/schema-matching/` | ✅ Yes | JWT, API Key |
| `POST /social/ratings/` | ✅ Yes | JWT, API Key |
| `POST /social/reviews/` | ✅ Yes | JWT, API Key |
| `POST /social/comments/` | ✅ Yes | JWT, API Key |
| `POST /social/communities/` | ✅ Yes | JWT, API Key |
| `GET /marketplace/listings/{id}/preview/` | ✅ Yes | JWT, API Key |
| `GET /developer/plugins/` | ⚠️ Optional | JWT, API Key (optional) |
| `GET /developer/sdk/` | ⚠️ Optional | JWT, API Key (optional) |

---

## Authorization Rules

### Role-Based Access Control (RBAC)

The system uses role-based access control with the following roles:

#### Platform-Level Roles

- **PLATFORM_ADMIN**: Full platform-wide access (all tenants, all operations)

#### Tenant-Level Roles

- **TENANT_ADMIN**: Full access within tenant (user management, configuration, all operations)
- **DATA_PROVIDER**: Create and manage assets, contracts, datasets (write operations)
- **DATA_CONSUMER**: Browse catalog, marketplace, request access, purchase assets (read + limited write)
- **AUDITOR**: Read-only access to audit logs, compliance reports (read-only)

### Scope-Based Access Control

API keys and some operations use scope-based access control:

#### Scope Format

`<resource>:<action>`

Examples:
- `assets:read` - Read assets
- `assets:write` - Create/update assets
- `assets:delete` - Delete assets
- `contracts:validate` - Validate contracts
- `compliance:run` - Run compliance scans

#### Scope Hierarchy

- `*:read` - Read access to all resources
- `*:write` - Write access to all resources
- `admin:*` - All admin operations

### Authorization Requirements by Endpoint

| Endpoint | Required Role | Required Scope | Notes |
|----------|---------------|----------------|-------|
| `POST /auth/register/` | None | None | Public endpoint |
| `GET /auth/me/` | Any authenticated | None | Returns user's own info |
| `GET /scheduled-ingestions/{id}/credentials/` | DATA_PROVIDER, TENANT_ADMIN | `scheduled_ingestion:read` | Must own or have access to scheduled ingestion |
| `POST /scheduled-ingestions/{id}/credentials/test/` | DATA_PROVIDER, TENANT_ADMIN | `scheduled_ingestion:write` | Must own or have access to scheduled ingestion |
| `POST /ai/natural-language-search/` | Any authenticated | `search:execute` | All authenticated users |
| `POST /ai/schema-matching/` | DATA_PROVIDER, TENANT_ADMIN | `ai:schema_matching` | Requires provider role |
| `POST /social/ratings/` | Any authenticated | `social:rate` | All authenticated users |
| `POST /social/reviews/` | Any authenticated | `social:review` | All authenticated users |
| `POST /social/comments/` | Any authenticated | `social:comment` | All authenticated users |
| `POST /social/communities/` | Any authenticated | `social:community` | All authenticated users |
| `GET /marketplace/listings/{id}/preview/` | Any authenticated | `marketplace:preview` | May require entitlement |
| `GET /developer/plugins/` | None | None | Public endpoint (optional auth for personalization) |
| `GET /developer/sdk/` | None | None | Public endpoint (optional auth for personalization) |

### Permission Checks

#### Role Checks

```python
# Example: Check if user has DATA_PROVIDER role
permission_classes = [IsAuthenticated, HasRole('DATA_PROVIDER')]

# Example: Check if user has any of multiple roles
permission_classes = [IsAuthenticated, HasAnyRole(['DATA_PROVIDER', 'TENANT_ADMIN'])]
```

#### Scope Checks

```python
# Example: Check if user/API key has assets:write scope
permission_classes = [IsAuthenticated, HasScope('assets:write')]

# Example: Check if user/API key has any of multiple scopes
permission_classes = [IsAuthenticated, HasAnyScope(['assets:read', 'assets:write'])]
```

#### Resource Ownership Checks

Some endpoints require resource ownership or explicit access:

- **Scheduled Ingestion Credentials**: User must own the scheduled ingestion or have TENANT_ADMIN role
- **Asset Operations**: User must own the asset or have TENANT_ADMIN role (for write operations)
- **Contract Operations**: User must own the contract or have TENANT_ADMIN role (for write operations)

---

## Rate Limiting Requirements

### Rate Limiting Architecture

The system uses a **sliding window algorithm** with Redis for accurate rate limiting. Rate limits are enforced at multiple levels:

1. **Tenant-level**: Per tenant, per endpoint category
2. **User-level**: Per user, per endpoint category (50% of tenant limit)
3. **API Key-level**: Per API key, per endpoint category (same as user limit)

### Time Windows

Rate limits are enforced across multiple time windows:

- **BURST**: 10 seconds (short-term burst protection)
- **SUSTAINED**: 60 seconds (1 minute, sustained usage)
- **DAILY**: 86400 seconds (24 hours, daily quota)

### Endpoint Categories

Endpoints are categorized for rate limiting:

- **DQ_RUN**: Data quality run endpoints
- **COMPLIANCE_RUN**: Compliance scan endpoints
- **FILE_UPLOAD**: File upload endpoints
- **FILE_DOWNLOAD**: File download endpoints
- **CONTRACT_VALIDATION**: Contract validation endpoints
- **CATALOG_READ**: Catalog browsing endpoints
- **SPARQL_QUERY**: SPARQL query endpoints
- **GENERAL**: General API endpoints
- **AI_ML**: AI/ML endpoints (natural language search, schema matching)
- **SOCIAL**: Social feature endpoints (ratings, reviews, comments)
- **MARKETPLACE**: Marketplace endpoints

### Platform Default Rate Limits

| Category | BURST (10s) | SUSTAINED (60s) | DAILY (24h) |
|----------|-------------|-----------------|-------------|
| DQ_RUN | 20 | 60 | 10,000 |
| COMPLIANCE_RUN | 20 | 60 | 10,000 |
| FILE_UPLOAD | 10 | 30 | 5,000 |
| FILE_DOWNLOAD | 50 | 300 | 50,000 |
| CONTRACT_VALIDATION | 30 | 100 | 20,000 |
| CATALOG_READ | 100 | 600 | 100,000 |
| SPARQL_QUERY | 50 | 200 | 50,000 |
| GENERAL | 100 | 600 | 100,000 |
| AI_ML | 10 | 20 | 5,000 |
| SOCIAL | 20 | 100 | 10,000 |
| MARKETPLACE | 50 | 200 | 20,000 |

### Rate Limiting by Endpoint

| Endpoint | Category | BURST | SUSTAINED | DAILY | Notes |
|----------|----------|-------|-----------|-------|-------|
| `POST /auth/register/` | GENERAL | 10 | 10 | 100 | Per IP address |
| `GET /auth/me/` | GENERAL | 100 | 600 | 100,000 | Per user |
| `GET /scheduled-ingestions/{id}/credentials/` | GENERAL | 100 | 600 | 100,000 | Per user |
| `POST /scheduled-ingestions/{id}/credentials/test/` | GENERAL | 10 | 30 | 1,000 | Per user (expensive operation) |
| `POST /ai/natural-language-search/` | AI_ML | 10 | 20 | 5,000 | Per user (expensive operation) |
| `POST /ai/schema-matching/` | AI_ML | 5 | 10 | 2,000 | Per user (very expensive operation) |
| `POST /social/ratings/` | SOCIAL | 10 | 10 | 1,000 | Per user per asset (10/hour) |
| `POST /social/reviews/` | SOCIAL | 5 | 20 | 100 | Per user per asset |
| `POST /social/comments/` | SOCIAL | 20 | 100 | 5,000 | Per user |
| `POST /social/communities/` | SOCIAL | 5 | 10 | 100 | Per user |
| `GET /marketplace/listings/{id}/preview/` | MARKETPLACE | 20 | 50 | 2,000 | Per user |
| `GET /developer/plugins/` | CATALOG_READ | 100 | 600 | 100,000 | Per IP (public endpoint) |
| `GET /developer/sdk/` | CATALOG_READ | 100 | 600 | 100,000 | Per IP (public endpoint) |

### Rate Limit Headers

All API responses include rate limit headers:

#### Standard Headers

- **X-RateLimit-Limit**: Maximum number of requests allowed in the current window
- **X-RateLimit-Remaining**: Number of requests remaining in the current window
- **X-RateLimit-Reset**: Unix timestamp when the rate limit resets

#### User-Level Headers (if authenticated)

- **X-RateLimit-User-Limit**: User-level rate limit
- **X-RateLimit-User-Remaining**: User-level remaining requests
- **X-RateLimit-User-Reset**: User-level reset timestamp

#### Example Response Headers

```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1736868000
X-RateLimit-User-Limit: 10
X-RateLimit-User-Remaining: 7
X-RateLimit-User-Reset: 1736868000
```

### Rate Limit Exceeded Response

When rate limit is exceeded, the API returns:

**Status Code**: `429 Too Many Requests`

**Response Body**:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Maximum 20 requests per minute.",
    "http_status": 429,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "retry_after": 30,
      "limit": 20,
      "window": 60,
      "category": "AI_ML"
    }
  }
}
```

**Response Headers**:
```
Retry-After: 30
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1736868030
```

### Rate Limiting Best Practices

1. **Monitor Rate Limit Headers**: Always check `X-RateLimit-Remaining` to avoid hitting limits
2. **Implement Exponential Backoff**: When receiving 429, wait for `Retry-After` seconds before retrying
3. **Cache Responses**: Use caching to reduce API calls
4. **Batch Operations**: Use batch endpoints when available to reduce request count
5. **Use Appropriate Endpoints**: Use read endpoints for browsing, write endpoints only when needed

---

## Input Validation Requirements

### Validation Rules

All API endpoints enforce comprehensive input validation:

#### String Validation

- **Email**: Format validation with regex `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`, max 255 chars
- **Password**: Pattern validation `^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$`, min 8 chars, max 128 chars
- **UUID**: Format validation (36 characters with hyphens)
- **Name/Title**: Min 1 char, max 255 chars, pattern `^[a-zA-Z0-9\s\-_\.]+$`
- **Description**: Max 1000-5000 chars (depending on field)
- **Query**: Min 3 chars, max 500 chars (for search queries)

#### Integer Validation

- **Rating**: 1-5 range (for star ratings)
- **Pagination**: Page (1+), page_size (1-100, default 10), offset (0+, default 0)
- **Counts**: Minimum 0 for all count fields
- **Version Numbers**: Minimum 1 for version fields

#### Number Validation

- **Confidence Scores**: 0-1 range (for AI confidence scores)
- **Quality Scores**: 0-1 range (for quality metrics)

#### Array Validation

- **Min/Max Items**: 0-1000 items for arrays
- **Item Validation**: Type and format validation for array items

#### Enum Validation

- **Source Types**: S3, GCS, AZURE_BLOB, HTTP, FTP, SFTP, DATABASE
- **Result Types**: assets, contracts, datasets, marketplace
- **Status Values**: pending, approved, rejected, success, failure, not_tested
- **Plugin Categories**: connector, transformation, quality_check
- **Matching Algorithms**: semantic, exact, hybrid

### Validation Error Response

When validation fails, the API returns:

**Status Code**: `400 Bad Request`

**Response Body**:
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
          "message": "Email is required",
          "code": "REQUIRED"
        },
        {
          "field": "password",
          "message": "Password must be at least 8 characters",
          "code": "MIN_LENGTH"
        },
        {
          "field": "password",
          "message": "Password must contain uppercase, lowercase, and number",
          "code": "PATTERN_MISMATCH"
        }
      ]
    }
  }
}
```

### Input Validation by Endpoint

#### POST /auth/register/

- **email**: Required, email format, max 255 chars, must be unique
- **password**: Required, min 8 chars, max 128 chars, must contain uppercase, lowercase, number
- **name**: Required, min 1 char, max 255 chars, alphanumeric + spaces/hyphens/underscores/dots
- **tenant_id**: Optional, UUID format

#### GET /auth/me/

- No input validation (no request body)

#### GET /scheduled-ingestions/{id}/credentials/

- **id**: Required, UUID format (path parameter)

#### POST /scheduled-ingestions/{id}/credentials/test/

- **id**: Required, UUID format (path parameter)

#### POST /ai/natural-language-search/

- **query**: Required, min 3 chars, max 500 chars
- **result_types**: Optional, array of enum values (assets, contracts, datasets, marketplace), default: [assets, contracts, datasets]
- **filters**: Optional, object with additionalProperties: true
- **limit**: Optional, integer, min 1, max 100, default 10

#### POST /ai/schema-matching/

- **source_schema**: Required, Schema object with fields array
- **target_schema**: Required, Schema object with fields array
- **matching_options**: Optional, object with:
  - **algorithm**: enum (semantic, exact, hybrid), default: hybrid
  - **min_confidence**: number, 0-1 range, default: 0.7
  - **include_reasoning**: boolean, default: true

#### POST /social/ratings/

- **asset_id**: Required, UUID format
- **rating**: Required, integer, 1-5 range

#### POST /social/reviews/

- **asset_id**: Required, UUID format
- **title**: Required, min 1 char, max 255 chars
- **content**: Required, min 10 chars, max 5000 chars
- **rating**: Optional, integer, 1-5 range

#### POST /social/comments/

- **asset_id**: Required, UUID format
- **content**: Required, min 1 char, max 2000 chars
- **parent_comment_id**: Optional, UUID format (for threading)

#### POST /social/communities/

- **name**: Required, min 1 char, max 255 chars, pattern `^[a-zA-Z0-9\s\-_\.]+$`
- **description**: Optional, max 1000 chars
- **community_id**: Optional, UUID format (to join existing)

#### GET /marketplace/listings/{id}/preview/

- **id**: Required, UUID format (path parameter)
- **sample_size**: Optional, integer, min 1, max 100, default 10 (query parameter)
- **include_quality_metrics**: Optional, boolean, default true (query parameter)
- **include_schema**: Optional, boolean, default true (query parameter)

#### GET /developer/plugins/

- **category**: Optional, enum (connector, transformation, quality_check, all) (query parameter)
- **type**: Optional, string (query parameter)
- **status**: Optional, enum (published, draft, deprecated) (query parameter)
- **search**: Optional, string (query parameter)
- **sort**: Optional, enum (popularity, rating, recency, name), default: popularity (query parameter)
- **page**: Optional, integer, min 1, default 1 (query parameter)
- **page_size**: Optional, integer, min 1, max 100, default 20 (query parameter)

#### GET /developer/sdk/

- **language**: Optional, enum (python, javascript, typescript, r, go, all), default: all (query parameter)
- **version**: Optional, string (query parameter)
- **include_examples**: Optional, boolean, default true (query parameter)

---

## Security Best Practices

### Client-Side Security

1. **Never Store Credentials**: Never store passwords or API keys in client-side code
2. **Use HTTPS Only**: Always use HTTPS for API requests
3. **Token Storage**: Store JWT tokens securely (httpOnly cookies or secure storage)
4. **Token Refresh**: Implement automatic token refresh before expiration
5. **API Key Rotation**: Rotate API keys regularly
6. **Input Sanitization**: Sanitize all user inputs before sending to API

### Server-Side Security

1. **HTTPS Enforcement**: All API endpoints require HTTPS in production
2. **CORS Configuration**: Proper CORS configuration for cross-origin requests
3. **Security Headers**: All responses include security headers (CSP, HSTS, X-Frame-Options, etc.)
4. **Credential Encryption**: All credentials encrypted at rest (AES-256)
5. **Audit Logging**: All security-relevant operations logged
6. **Rate Limiting**: Rate limiting enforced at multiple levels
7. **Input Validation**: All inputs validated server-side (never trust client)

### API Key Security

1. **Key Generation**: Use cryptographically secure random UUIDs
2. **Key Hashing**: Store hashed keys (SHA-256) in database
3. **Key Expiration**: Support key expiration dates
4. **Key Scopes**: Limit API key scopes to minimum required
5. **Key Rotation**: Support key rotation without downtime
6. **Key Revocation**: Support immediate key revocation

### JWT Token Security

1. **Token Expiration**: Short-lived access tokens (1 hour)
2. **Refresh Tokens**: Long-lived refresh tokens for renewal
3. **Token Revocation**: Support token revocation via token version
4. **Secure Storage**: Tokens stored securely (never in localStorage for sensitive apps)
5. **Token Validation**: Always validate token signature and expiration

---

## API-Specific Security Requirements

### Authentication APIs

#### POST /auth/register/

- **Authentication**: Not required (public endpoint)
- **Rate Limiting**: 10 requests per minute per IP address
- **Input Validation**: Email format, password strength, name format
- **Security**: 
  - Password hashed with bcrypt (cost factor 12)
  - Email verification required (optional)
  - Rate limiting prevents abuse

#### GET /auth/me/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Returns user's own information only
- **Rate Limiting**: 100 requests per 10 seconds (burst), 600 per minute (sustained)
- **Caching**: Response may be cached for 5 minutes

### Credential Management APIs

#### GET /scheduled-ingestions/{id}/credentials/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: User must own scheduled ingestion or have TENANT_ADMIN role
- **Rate Limiting**: 100 requests per 10 seconds (burst), 600 per minute (sustained)
- **Security**: 
  - Credentials never exposed (only masked versions returned)
  - Audit logging for all credential access
  - Tenant isolation enforced

#### POST /scheduled-ingestions/{id}/credentials/test/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: User must own scheduled ingestion or have TENANT_ADMIN role
- **Rate Limiting**: 10 requests per 10 seconds (burst), 30 per minute (sustained) - expensive operation
- **Security**: 
  - Credentials never exposed in request or response
  - Connection test timeout: 30 seconds
  - Audit logging for all credential tests

### AI/ML APIs

#### POST /ai/natural-language-search/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Any authenticated user (scope: `search:execute`)
- **Rate Limiting**: 10 requests per 10 seconds (burst), 20 per minute (sustained), 5,000 per day
- **Security**: 
  - Query input sanitized to prevent injection
  - LLM API keys stored securely
  - Query caching to reduce LLM API calls
  - Cost tracking and alerts

#### POST /ai/schema-matching/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: DATA_PROVIDER or TENANT_ADMIN role (scope: `ai:schema_matching`)
- **Rate Limiting**: 5 requests per 10 seconds (burst), 10 per minute (sustained), 2,000 per day
- **Security**: 
  - Schema input validated
  - AI service API keys stored securely
  - Cost tracking and alerts

### Social Feature APIs

#### POST /social/ratings/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Any authenticated user (scope: `social:rate`)
- **Rate Limiting**: 10 requests per 10 seconds (burst), 10 per minute (sustained), 1,000 per day - **Per user per asset: 10 per hour**
- **Security**: 
  - Rating value validated (1-5)
  - Duplicate rating prevention
  - Content moderation (optional)

#### POST /social/reviews/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Any authenticated user (scope: `social:review`)
- **Rate Limiting**: 5 requests per 10 seconds (burst), 20 per minute (sustained), 100 per day
- **Security**: 
  - Review content validated (min 10 chars, max 5000 chars)
  - Content moderation before publication
  - Spam detection

#### POST /social/comments/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Any authenticated user (scope: `social:comment`)
- **Rate Limiting**: 20 requests per 10 seconds (burst), 100 per minute (sustained), 5,000 per day
- **Security**: 
  - Comment content validated (min 1 char, max 2000 chars)
  - Threading support with parent_comment_id validation
  - Content moderation (optional)

#### POST /social/communities/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Any authenticated user (scope: `social:community`)
- **Rate Limiting**: 5 requests per 10 seconds (burst), 10 per minute (sustained), 100 per day
- **Security**: 
  - Community name validated (pattern: alphanumeric + spaces/hyphens/underscores/dots)
  - Duplicate community name prevention
  - Community moderation (optional)

### Advanced Marketplace APIs

#### GET /marketplace/listings/{id}/preview/

- **Authentication**: Required (JWT or API Key)
- **Authorization**: Any authenticated user (scope: `marketplace:preview`) - may require entitlement
- **Rate Limiting**: 20 requests per 10 seconds (burst), 50 per minute (sustained), 2,000 per day
- **Security**: 
  - Preview access control (entitlement check)
  - Preview expiration (1 hour)
  - Sample data generation (no sensitive data)
  - Audit logging for preview access

### Developer Experience APIs

#### GET /developer/plugins/

- **Authentication**: Optional (public endpoint, but authenticated users get personalized results)
- **Authorization**: None (public endpoint)
- **Rate Limiting**: 100 requests per 10 seconds (burst), 600 per minute (sustained) - **Per IP address**
- **Security**: 
  - Public endpoint (no sensitive data)
  - Input validation for query parameters
  - SQL injection prevention

#### GET /developer/sdk/

- **Authentication**: Optional (public endpoint)
- **Authorization**: None (public endpoint)
- **Rate Limiting**: 100 requests per 10 seconds (burst), 600 per minute (sustained) - **Per IP address**
- **Security**: 
  - Public endpoint (documentation only)
  - Input validation for query parameters

---

## Security Headers

All API responses include the following security headers:

- **Strict-Transport-Security (HSTS)**: `max-age=31536000; includeSubDomains`
- **X-Content-Type-Options**: `nosniff`
- **X-Frame-Options**: `DENY`
- **X-XSS-Protection**: `1; mode=block`
- **Content-Security-Policy**: `default-src 'self'`
- **Referrer-Policy**: `strict-origin-when-cross-origin`

---

## Security Audit Logging

All security-relevant operations are logged:

- **Authentication Events**: Login, logout, token refresh, API key usage
- **Authorization Events**: Permission denied, role checks, scope checks
- **Credential Operations**: Credential access, credential tests, credential updates
- **Rate Limiting Events**: Rate limit exceeded, rate limit headers
- **Input Validation Events**: Validation failures, suspicious inputs

---

## Compliance

### GDPR Compliance

- **Data Minimization**: Only collect necessary data
- **Right to be Forgotten**: Support data deletion requests
- **Data Portability**: Support data export
- **Consent Management**: Track user consent

### SOC 2 Compliance

- **Access Control**: Role-based and scope-based access control
- **Audit Logging**: Comprehensive audit trails
- **Encryption**: Data encryption at rest and in transit
- **Incident Response**: Security incident procedures

### ISO 27001 Compliance

- **Information Security Management**: Comprehensive security policies
- **Risk Management**: Security risk assessment
- **Access Control**: Multi-factor authentication support
- **Cryptography**: Strong encryption algorithms

---

## Security Testing

### Recommended Security Tests

1. **Authentication Tests**: 
   - Invalid token handling
   - Expired token handling
   - Token tampering detection
   - API key validation

2. **Authorization Tests**:
   - Role-based access control
   - Scope-based access control
   - Resource ownership checks
   - Permission escalation prevention

3. **Rate Limiting Tests**:
   - Rate limit enforcement
   - Rate limit header accuracy
   - Rate limit reset behavior
   - Multiple window enforcement

4. **Input Validation Tests**:
   - SQL injection prevention
   - XSS prevention
   - CSRF protection
   - Path traversal prevention

5. **Security Header Tests**:
   - All security headers present
   - Header values correct
   - HTTPS enforcement

---

## Summary

### Authentication Coverage

- ✅ **JWT Bearer Token**: Documented for all authenticated endpoints
- ✅ **API Key**: Documented for all authenticated endpoints
- ✅ **Public Endpoints**: Clearly marked (register, plugins, SDK)

### Authorization Coverage

- ✅ **Role-Based Access Control**: Documented for all endpoints
- ✅ **Scope-Based Access Control**: Documented for all endpoints
- ✅ **Resource Ownership**: Documented where applicable

### Rate Limiting Coverage

- ✅ **Per-Endpoint Limits**: Documented for all 14 endpoints
- ✅ **Multiple Time Windows**: BURST, SUSTAINED, DAILY documented
- ✅ **Rate Limit Headers**: Complete header documentation
- ✅ **Rate Limit Exceeded Response**: Complete error response documentation

### Input Validation Coverage

- ✅ **All Request Fields**: Validation rules documented
- ✅ **Validation Error Response**: Complete error response format
- ✅ **Field-Level Errors**: Detailed field error structure

---

**Status**: ✅ Complete  
**Last Updated**: 2025-12-13

