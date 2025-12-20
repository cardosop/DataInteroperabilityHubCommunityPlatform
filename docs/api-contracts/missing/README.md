# Missing API OpenAPI Specifications

**Generated**: 2025-12-13  
**Task**: 0.4.1 - Create OpenAPI 3.0 specifications for missing APIs  
**Status**: ✅ Complete

---

## Overview

This directory contains OpenAPI 3.0 specifications for all missing APIs identified in the gap analysis. These specifications provide complete contract definitions for APIs that need to be implemented.

**Total Missing APIs**: 14
- **P0 - Critical**: 2 APIs
- **P1 - High**: 2 APIs
- **P2 - Medium**: 6 APIs
- **P3 - Low**: 3 APIs

---

## Directory Structure

```
docs/api-contracts/missing/
├── README.md                           # This file
├── auth/                               # Authentication APIs
│   ├── register.yaml                  # POST /api/v1/auth/register/
│   └── me.yaml                        # GET /api/v1/auth/me/
├── credentials/                        # Credential Management APIs
│   └── scheduled-ingestion-credentials.yaml  # GET/POST /api/v1/scheduled-ingestions/{id}/credentials/
├── ai-ml/                              # AI/ML APIs
│   ├── natural-language-search.yaml   # POST /api/v1/ai/natural-language-search/
│   └── schema-matching.yaml           # POST /api/v1/ai/schema-matching/
├── social/                             # Social Feature APIs
│   └── ratings-reviews-comments-communities.yaml  # POST /api/v1/social/{ratings,reviews,comments,communities}/
├── marketplace-advanced/               # Advanced Marketplace APIs
│   └── preview.yaml                    # GET /api/v1/marketplace/listings/{id}/preview/
└── developer/                          # Developer Experience APIs
    └── plugins-sdk.yaml                # GET /api/v1/developer/{plugins,sdk}/
```

---

## API Specifications by Category

### Authentication APIs (P0 - Critical)

**Priority**: P0 - Critical  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

#### POST `/api/v1/auth/register/`

**File**: `auth/register.yaml`

**Description**: Register new user account

**Key Features**:
- Email validation and uniqueness check
- Password strength validation (min 8 chars, uppercase, lowercase, number)
- Multi-tenant support
- Welcome email (optional)
- Rate limiting (10 requests/minute)

**Performance Target**: < 500ms p95

**Error Responses**:
- `400 Bad Request`: Validation errors, email already exists
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

---

#### GET `/api/v1/auth/me/`

**File**: `auth/me.yaml`

**Description**: Get current authenticated user information

**Key Features**:
- Current user information
- Roles and permissions
- Session information
- Tenant information
- Caching support (5 minutes)

**Performance Target**: < 200ms p95

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token
- `500 Internal Server Error`: Server error

---

### Credential Management APIs (P1 - High)

**Priority**: P1 - High  
**Phase**: Phase 1 (Phase 8: Weeks 12-13)  
**Timeline**: Weeks 5-24 (Core Features)

#### GET `/api/v1/scheduled-ingestions/{id}/credentials/`

**File**: `credentials/scheduled-ingestion-credentials.yaml`

**Description**: Get credentials (masked) for scheduled ingestion

**Key Features**:
- Never exposes actual credentials
- Returns masked credentials only
- Includes credential metadata
- Supports credential version tracking

**Performance Target**: < 200ms p95

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Scheduled ingestion not found
- `500 Internal Server Error`: Server error

---

#### POST `/api/v1/scheduled-ingestions/{id}/credentials/test/`

**File**: `credentials/scheduled-ingestion-credentials.yaml`

**Description**: Test connection with credentials

**Key Features**:
- Tests connection without exposing credentials
- Returns test result (success/failure)
- Includes error details if test fails
- Supports timeout (30 seconds)

**Performance Target**: < 5000ms p95

**Error Responses**:
- `400 Bad Request`: Invalid credentials
- `401 Unauthorized`: Invalid or missing token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Scheduled ingestion not found
- `500 Internal Server Error`: Server error
- `504 Gateway Timeout`: Connection test exceeded timeout

---

### AI/ML APIs (P2 - Medium)

**Priority**: P2 - Medium  
**Phase**: Phase 2 (Phase 15: Weeks 25-30)  
**Timeline**: Weeks 25-40 (Advanced Features)

#### POST `/api/v1/ai/natural-language-search/`

**File**: `ai-ml/natural-language-search.yaml`

**Description**: Natural language search with query understanding

**Key Features**:
- Natural language query input
- Query understanding and translation
- Search execution across assets, contracts, datasets
- Results with explanation
- Query caching

**Performance Target**: < 3000ms p95

**Rate Limiting**: 20 requests per minute per user

**Error Responses**:
- `400 Bad Request`: Invalid query
- `401 Unauthorized`: Invalid or missing token
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: LLM service unavailable

---

#### POST `/api/v1/ai/schema-matching/`

**File**: `ai-ml/schema-matching.yaml`

**Description**: AI-powered schema matching with suggestions

**Key Features**:
- Schema comparison
- Field mapping suggestions with confidence scores
- Mapping visualization data
- Support for accepting/rejecting mappings
- Transformation suggestions

**Performance Target**: < 15000ms p95

**Rate Limiting**: 10 requests per minute per user

**Error Responses**:
- `400 Bad Request`: Invalid schemas
- `401 Unauthorized`: Invalid or missing token
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: AI service unavailable

---

### Social Feature APIs (P2 - Medium)

**Priority**: P2 - Medium  
**Phase**: Phase 2 (Phase 17: Weeks 37-40)  
**Timeline**: Weeks 25-40 (Advanced Features)

#### POST `/api/v1/social/ratings/`

**File**: `social/ratings-reviews-comments-communities.yaml`

**Description**: Submit rating (1-5 stars) for an asset

**Key Features**:
- Rating submission (1-5 stars)
- Rate limiting (10 ratings per hour per user per asset)
- Rating aggregation

**Rate Limiting**: 10 ratings per hour per user per asset

---

#### POST `/api/v1/social/reviews/`

**File**: `social/ratings-reviews-comments-communities.yaml`

**Description**: Submit review for an asset

**Key Features**:
- Written review submission
- Review moderation
- Rating association

---

#### POST `/api/v1/social/comments/`

**File**: `social/ratings-reviews-comments-communities.yaml`

**Description**: Submit comment (supports threading)

**Key Features**:
- Comment submission
- Threading support (replies)
- @mentions support

---

#### POST `/api/v1/social/communities/`

**File**: `social/ratings-reviews-comments-communities.yaml`

**Description**: Create or join a community

**Key Features**:
- Community creation
- Community joining
- Community management

---

### Advanced Marketplace APIs (P3 - Low)

**Priority**: P3 - Low  
**Phase**: Phase 3 (Phase 18: Weeks 41-44)  
**Timeline**: Weeks 41-64 (Strategic Differentiators)

#### GET `/api/v1/marketplace/listings/{id}/preview/`

**File**: `marketplace-advanced/preview.yaml`

**Description**: Preview data before purchase

**Key Features**:
- Sample data generation
- Quality metrics preview
- Schema preview
- Access control (entitlement check)
- Preview expiration

**Performance Target**: < 2000ms p95

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token
- `403 Forbidden`: Preview access not available
- `404 Not Found`: Listing not found
- `500 Internal Server Error`: Server error

---

### Developer Experience APIs (P3 - Low)

**Priority**: P3 - Low  
**Phase**: Phase 3 (Phase 24: Weeks 61-64)  
**Timeline**: Weeks 41-64 (Strategic Differentiators)

#### GET `/api/v1/developer/plugins/`

**File**: `developer/plugins-sdk.yaml`

**Description**: List available plugins

**Key Features**:
- Plugin discovery
- Filtering by category, type, status
- Sorting by popularity, rating, recency
- Search functionality
- Pagination

**Authentication**: Optional (public endpoint)

---

#### GET `/api/v1/developer/sdk/`

**File**: `developer/plugins-sdk.yaml`

**Description**: Get SDK documentation and examples

**Key Features**:
- SDK documentation for multiple languages
- Code examples and tutorials
- API reference
- Interactive API explorer integration

**Authentication**: Optional (public endpoint)

---

## OpenAPI Specification Standards

All specifications follow OpenAPI 3.0.3 standard and include:

### Required Components

1. **Info Section**:
   - Title, description, version
   - Contact information

2. **Servers**:
   - Production, staging, local development

3. **Paths**:
   - Complete endpoint definitions
   - Operation IDs
   - Request/response schemas
   - Error responses
   - Examples

4. **Components**:
   - Request/response schemas
   - Error response schemas
   - Security schemes
   - Reusable components

5. **Security**:
   - Authentication requirements
   - Authorization requirements
   - Security schemes (JWT, API Key)

6. **Error Responses**:
   - Standard error format
   - Error codes and messages
   - HTTP status codes
   - Error details

### Schema Standards

- **UUID Format**: All IDs use UUID format
- **Date-Time Format**: ISO 8601 format for all timestamps
- **Error Envelope**: Standard error response format
- **Pagination**: Standard pagination format
- **Validation**: Request validation rules
- **Examples**: Comprehensive examples for all endpoints

---

## Usage

### Validating Specifications

```bash
# Validate with Spectral
spectral lint docs/api-contracts/missing/**/*.yaml

# Validate with OpenAPI Validator
openapi-validator docs/api-contracts/missing/**/*.yaml
```

### Generating Code

```bash
# Generate TypeScript types
openapi-typescript docs/api-contracts/missing/**/*.yaml --output src/types/api/

# Generate Python client
openapi-generator generate -i docs/api-contracts/missing/**/*.yaml -g python -o sdk/python/
```

### Viewing in Swagger UI

```bash
# Serve with Swagger UI
docker run -p 8080:8080 -v $(pwd)/docs/api-contracts/missing:/specs swaggerapi/swagger-ui
# Then open http://localhost:8080
```

---

## Implementation Checklist

### P0 - Critical (Weeks 0-4)

- [ ] Implement POST `/api/v1/auth/register/`
- [ ] Implement GET `/api/v1/auth/me/`

### P1 - High (Weeks 5-24)

- [ ] Implement GET `/api/v1/scheduled-ingestions/{id}/credentials/` (Phase 8)
- [ ] Implement POST `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Phase 8)

### P2 - Medium (Weeks 25-40)

- [ ] Implement POST `/api/v1/ai/natural-language-search/` (Phase 15)
- [ ] Implement POST `/api/v1/ai/schema-matching/` (Phase 15)
- [ ] Implement POST `/api/v1/social/ratings/` (Phase 17)
- [ ] Implement POST `/api/v1/social/reviews/` (Phase 17)
- [ ] Implement POST `/api/v1/social/comments/` (Phase 17)
- [ ] Implement POST `/api/v1/social/communities/` (Phase 17)

### P3 - Low (Weeks 41-64)

- [ ] Implement GET `/api/v1/marketplace/listings/{id}/preview/` (Phase 18)
- [ ] Implement GET `/api/v1/developer/plugins/` (Phase 24)
- [ ] Implement GET `/api/v1/developer/sdk/` (Phase 24)

---

## File Summary

| Category | File | Endpoints | Priority |
|----------|------|-----------|----------|
| **Authentication** | `auth/register.yaml` | POST `/auth/register/` | P0 |
| **Authentication** | `auth/me.yaml` | GET `/auth/me/` | P0 |
| **Credentials** | `credentials/scheduled-ingestion-credentials.yaml` | GET/POST `/scheduled-ingestions/{id}/credentials/` | P1 |
| **AI/ML** | `ai-ml/natural-language-search.yaml` | POST `/ai/natural-language-search/` | P2 |
| **AI/ML** | `ai-ml/schema-matching.yaml` | POST `/ai/schema-matching/` | P2 |
| **Social** | `social/ratings-reviews-comments-communities.yaml` | POST `/social/{ratings,reviews,comments,communities}/` | P2 |
| **Marketplace** | `marketplace-advanced/preview.yaml` | GET `/marketplace/listings/{id}/preview/` | P3 |
| **Developer** | `developer/plugins-sdk.yaml` | GET `/developer/{plugins,sdk}/` | P3 |

**Total Files**: 8  
**Total Endpoints**: 14

---

## Next Steps

1. **Validate Specifications**: Run validation tools to ensure all specs are valid
2. **Generate Types**: Generate TypeScript/Python types from specifications
3. **Implement APIs**: Use specifications as implementation contracts
4. **Test Against Specs**: Validate implementations against OpenAPI specs
5. **Update Documentation**: Keep specs in sync with implementations

---

**Document Status**: ✅ Complete  
**Last Updated**: 2025-12-13  
**Next Review**: After API implementation

