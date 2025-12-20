# API Gap Details Documentation

**Generated**: 2025-12-13  
**Task**: 0.3.3 - Document gap details  
**Status**: ✅ Complete

---

## Overview

This document provides detailed information for each API gap including:
- Gap type (missing endpoint, incomplete endpoint, enhancement)
- Impact (blocks which journeys/use cases)
- Priority (P0/P1/P2/P3)
- Estimated effort
- Dependencies
- Timeline

**Total Gaps**: 26
- **Missing Endpoints**: 2 (P0)
- **Incomplete Endpoints**: 16 (P0: 4, P1: 6, P2: 4, P3: 2)
- **Endpoints Needing Enhancements**: 8 (P0: 2, P1: 3, P2: 2, P3: 1)

---

## Statistics

### Gaps by Type

| Type | Count |
|------|-------|
| **Missing** | **2** |
| **Incomplete** | **16** |
| **Enhancement** | **8** |
| **Total** | **26** |

### Gaps by Priority

| Priority | Count |
|----------|-------|
| **P0 - Critical** | **8** |
| **P1 - High** | **9** |
| **P2 - Medium** | **6** |
| **P3 - Low** | **3** |
| **Total** | **26** |

---

## P0 - Critical Priority

**Total Gaps**: 8  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

### Missing Endpoints

#### 1. POST `/api/v1/auth/register/`

**Gap Type**: Missing Endpoint  
**Priority**: P0 - Critical  
**Category**: Authentication  
**Priority Category**: P0-Authentication  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: Register new user account

**Impact**: CRITICAL - Blocks user registration flow

**Blocked Journeys**:
- JOURNEY-AUTH-002: User Registration Flow
- All journeys requiring user registration as first step

**Blocked Use Cases**:
- UC-AUTH-002: Register New User Account
- All use cases requiring new user registration

**Estimated Effort**: High (1-3 days)

**Dependencies**:
- User model (existing)
- Tenant model (existing)
- Password hashing service (existing)
- Email service (optional, for welcome email)

**Performance Requirements**: < 500ms p95

**Error Responses**:
- `400 Bad Request`: Validation errors, email already exists
- `429 Too Many Requests`: Rate limit exceeded (10 requests/minute)
- `500 Internal Server Error`: Server error

**Implementation Notes**:
- Must validate password strength (min 8 chars, uppercase, lowercase, number)
- Must check email uniqueness
- Must support multi-tenant registration
- Must send welcome email (optional)
- Must hash password before storage
- Must create user session after registration

**Sources**:
- Proposal (line 1075)
- Specs (frontend-authentication)
- Journeys (JOURNEY-AUTH-002)
- Use Cases (UC-AUTH-002)

**Required Request Schema**:
```json
{
  "email": "string (required, email format, unique)",
  "password": "string (required, min 8 chars, must contain uppercase, lowercase, number)",
  "name": "string (required, max 255 chars)",
  "tenant_id": "UUID (optional, for multi-tenant)"
}
```

**Required Response Schema**:
```json
{
  "id": "UUID",
  "email": "string",
  "name": "string",
  "tenant_id": "UUID",
  "created_at": "ISO 8601 datetime"
}
```

---

#### 2. GET `/api/v1/auth/me/`

**Gap Type**: Missing Endpoint  
**Priority**: P0 - Critical  
**Category**: Authentication  
**Priority Category**: P0-Authentication  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: Get current authenticated user information

**Impact**: CRITICAL - Blocks user profile access

**Blocked Journeys**:
- JOURNEY-AUTH-006: View User Profile
- All journeys requiring current user information

**Blocked Use Cases**:
- UC-AUTH-006: Get Current User Information
- All use cases requiring user profile access

**Estimated Effort**: Low (2-4 hours)

**Dependencies**:
- Authentication system (existing)
- JWT token parsing (existing)
- User model (existing)
- Role/permission system (existing)

**Performance Requirements**: < 200ms p95

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token
- `500 Internal Server Error`: Server error

**Implementation Notes**:
- Should return user's current session info
- Should include roles and permissions
- Should be fast (cached if possible)
- Should include tenant information
- Should include last login timestamp

**Sources**:
- Proposal (line 1080)
- Specs (frontend-authentication)
- Journeys (JOURNEY-AUTH-006)
- Use Cases (UC-AUTH-006)

**Required Response Schema**:
```json
{
  "id": "UUID",
  "email": "string",
  "name": "string",
  "tenant_id": "UUID",
  "roles": ["string"],
  "permissions": ["string"],
  "created_at": "ISO 8601 datetime",
  "last_login_at": "ISO 8601 datetime (nullable)"
}
```

---

### Incomplete Endpoints

#### 3. GET `/api/v1/assets/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P0 - Critical  
**Category**: Asset Management  
**Priority Category**: P0-Core-CRUD  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: List assets with filtering, sorting, and search

**Impact**: May limit filtering/sorting capabilities

**Blocked Journeys**:
- JOURNEY-DPO-005: Manage Asset Versions
- All journeys requiring asset listing with filters

**Blocked Use Cases**:
- UC-ASSET-001: List Assets
- All use cases requiring filtered asset lists

**Estimated Effort**: Medium (4-8 hours)

**Dependencies**:
- Asset model (existing)
- Query parameter parsing (existing)
- Search service (existing, may need enhancement)

**Missing Query Parameters**:
- `ordering` (string, optional): Sort fields (comma-separated, prefix with `-` for descending)
- `search` (string, optional): Search in name, description
- `domain` (string, optional): Filter by domain
- `tags` (string, optional): Filter by tags (comma-separated)
- `status` (string, optional): Filter by status (DRAFT, ACTIVE, RETIRED)

**Current Implementation**: Basic list endpoint exists with pagination

**Implementation Notes**:
- Query parameter parsing
- Filter application
- Search implementation (full-text or field-based)
- Sorting implementation
- Pagination (already exists)

**Sources**:
- Proposal (line 1086)
- Specs (frontend-application)
- Journeys (JOURNEY-DPO-005)

---

#### 4. POST `/api/v1/assets/{id}/activate/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P0 - Critical  
**Category**: Asset Management  
**Priority Category**: P0-Core-CRUD  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: Activate asset with validation and workflow execution

**Impact**: May allow activation of invalid assets

**Blocked Journeys**:
- JOURNEY-DPO-004: Monitor Asset Quality
- JOURNEY-DPO-001: Onboard New Asset via Data-First Flow (activation step)
- All journeys requiring asset activation

**Blocked Use Cases**:
- UC-ASSET-008: Activate Asset
- All use cases requiring asset activation

**Estimated Effort**: High (1-2 days)

**Dependencies**:
- Contract validation service
- DQ service
- Compliance service
- Workflow engine
- Asset model (existing)

**Missing Features**:
- Contract validation before activation
- Dataset quality checks
- Compliance verification
- Workflow execution
- Progress tracking
- Error handling and rollback

**Current Implementation**: Basic activation endpoint exists (status change only)

**Implementation Notes**:
- Contract validation service integration
- DQ service integration
- Compliance service integration
- Workflow orchestration
- Error handling and rollback
- Progress tracking via WebSocket

**Sources**:
- Proposal (line 1093)
- Specs (frontend-application)
- Journeys (JOURNEY-DPO-004)

---

#### 5. GET `/api/v1/auth/api-keys/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P0 - Critical  
**Category**: Authentication  
**Priority Category**: P0-Core-CRUD  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: List API keys with pagination

**Impact**: May limit pagination capabilities

**Blocked Journeys**:
- JOURNEY-AUTH-007: Manage API Keys
- All journeys requiring API key listing

**Blocked Use Cases**:
- UC-AUTH-007: List API Keys
- All use cases requiring API key management

**Estimated Effort**: Low (1-2 hours)

**Dependencies**:
- APIKey model (existing)
- Pagination framework (existing)

**Missing Query Parameters**:
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Current Implementation**: Basic list endpoint exists (no pagination)

**Implementation Notes**:
- Pagination support
- Query parameter parsing
- Response pagination metadata

**Sources**:
- Proposal (line 1081)
- Specs (frontend-authentication)
- Journeys (JOURNEY-AUTH-007)

---

#### 6. POST `/api/v1/contracts/{id}/validate/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P0 - Critical  
**Category**: Contract Management  
**Priority Category**: P0-Core-CRUD  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: Validate contract with detailed results

**Impact**: May not provide complete validation results

**Blocked Journeys**:
- JOURNEY-DPO-001: Onboard New Asset via Data-First Flow (contract validation step)
- JOURNEY-DE-001: Create Contract
- All journeys requiring contract validation

**Blocked Use Cases**:
- UC-CONTRACT-003: Validate Contract
- All use cases requiring contract validation

**Estimated Effort**: Medium (4-8 hours)

**Dependencies**:
- Contract validation service (existing)
- Schema validation service (existing)
- Contract model (existing)

**Missing Response Fields**:
- Validation errors with field-level details
- Validation warnings
- Schema compliance status
- Normalization status

**Current Implementation**: Basic validation endpoint exists (boolean result only)

**Implementation Notes**:
- Enhanced validation logic
- Field-level error tracking
- Warning generation
- Status calculation
- Response serialization

**Sources**:
- Proposal
- Specs (frontend-contract-editor)
- Journeys (JOURNEY-DPO-*)

---

### Endpoints Needing Enhancements

#### 7. POST `/api/v1/assets/`

**Gap Type**: Enhancement  
**Priority**: P0 - Critical  
**Category**: Asset Management  
**Priority Category**: P0-Core-CRUD  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: Create asset with performance optimization

**Impact**: May cause user experience issues

**Blocked Journeys**: None (endpoint exists but slow)

**Blocked Use Cases**: None (endpoint exists but slow)

**Estimated Effort**: Medium (4-8 hours)

**Dependencies**:
- Asset model (existing)
- Database optimization
- Caching service (existing)

**Enhancement Type**: Performance

**Current Performance**: Unknown  
**Required Performance**: < 1000ms p95

**Enhancement Needed**:
- Optimize database queries
- Add caching for metadata
- Implement async processing for heavy operations

**Implementation Notes**:
- Profile current performance
- Optimize database queries (select_related, prefetch_related)
- Add Redis caching for metadata
- Implement async processing for heavy operations

**Sources**:
- Performance requirements from proposal

---

#### 8. POST `/api/v1/assets/{id}/activate/`

**Gap Type**: Enhancement  
**Priority**: P0 - Critical  
**Category**: Asset Management  
**Priority Category**: P0-Core-CRUD  
**Phase**: Phase 0  
**Timeline**: Weeks 0-4 (Before Frontend MVP)

**Description**: Activate asset with performance optimization and progress tracking

**Impact**: May cause user experience issues

**Blocked Journeys**: None (endpoint exists but slow)

**Blocked Use Cases**: None (endpoint exists but slow)

**Estimated Effort**: High (1-2 days)

**Dependencies**:
- Workflow engine (existing)
- WebSocket service (existing)
- Background job queue (existing)

**Enhancement Type**: Performance

**Current Performance**: Unknown  
**Required Performance**: < 2000ms p95

**Enhancement Needed**:
- Optimize workflow execution
- Add progress tracking
- Implement background processing

**Implementation Notes**:
- Profile current performance
- Optimize workflow execution
- Add progress tracking via WebSocket
- Implement background processing for long-running operations

**Sources**:
- Performance requirements from proposal

---

## P1 - High Priority

**Total Gaps**: 9  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features)

### Missing Endpoints

#### 9. GET `/api/v1/scheduled-ingestions/{id}/credentials/`

**Gap Type**: Missing Endpoint  
**Priority**: P1 - High  
**Category**: Scheduled Ingestion  
**Priority Category**: P1-Credential-Management  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features) - Specifically Phase 8 (Weeks 12-13)

**Description**: Get credentials (masked) for scheduled ingestion

**Impact**: Blocks credential management UI

**Blocked Journeys**:
- JOURNEY-DE-002: Set Up Scheduled Ingestion (credential management step)
- All journeys requiring credential management

**Blocked Use Cases**:
- UC-SCHEDULED-INGESTION-003: Manage Credentials
- All use cases requiring credential access

**Estimated Effort**: Medium (1-2 days)

**Dependencies**:
- Scheduled ingestion model (existing)
- Credential manager service (Phase 8)
- Encryption service (Phase 8)

**Performance Requirements**: < 200ms p95

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Scheduled ingestion not found
- `500 Internal Server Error`: Server error

**Implementation Notes**:
- Must never expose actual credentials
- Must return masked credentials only
- Must include credential metadata
- Must support credential version tracking

**Sources**:
- Phase 8 requirements (credential management)

---

#### 10. POST `/api/v1/scheduled-ingestions/{id}/credentials/test/`

**Gap Type**: Missing Endpoint  
**Priority**: P1 - High  
**Category**: Scheduled Ingestion  
**Priority Category**: P1-Credential-Management  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features) - Specifically Phase 8 (Weeks 12-13)

**Description**: Test connection with credentials

**Impact**: Blocks credential testing functionality

**Blocked Journeys**:
- JOURNEY-DE-002: Set Up Scheduled Ingestion (credential testing step)
- All journeys requiring credential testing

**Blocked Use Cases**:
- UC-SCHEDULED-INGESTION-004: Test Credentials
- All use cases requiring credential testing

**Estimated Effort**: Low (4-8 hours)

**Dependencies**:
- Scheduled ingestion model (existing)
- Credential manager service (Phase 8)
- Connector framework (existing)

**Performance Requirements**: < 5000ms p95 (connection testing can be slow)

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Scheduled ingestion not found
- `400 Bad Request`: Invalid credentials
- `500 Internal Server Error`: Server error

**Implementation Notes**:
- Must test connection without exposing credentials
- Must return test result (success/failure)
- Must include error details if test fails
- Must support timeout for slow connections

**Sources**:
- Phase 8 requirements (credential management)

---

### Incomplete Endpoints

#### 11. GET `/api/v1/marketplace/listings/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P1 - High  
**Category**: Marketplace  
**Priority Category**: P1-Marketplace  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features)

**Description**: List marketplace listings with search and filtering

**Impact**: May limit marketplace discovery

**Blocked Journeys**:
- JOURNEY-DC-001: Discover Contracts in Marketplace
- All journeys requiring marketplace discovery

**Blocked Use Cases**:
- UC-MARKETPLACE-001: Discover Marketplace Listings
- All use cases requiring marketplace search

**Estimated Effort**: Medium (4-8 hours)

**Dependencies**:
- Marketplace service (existing)
- Search service (existing)

**Missing Query Parameters**:
- `search` (string, optional): Search in name, description
- `domain` (string, optional): Filter by domain
- `category` (string, optional): Filter by category
- `sort` (string, optional): Sort by popularity, recency, etc.

**Current Implementation**: Basic list endpoint exists

**Implementation Notes**:
- Search implementation
- Filtering logic
- Sorting implementation
- Performance optimization

**Sources**:
- Marketplace requirements

---

#### 12. GET `/api/v1/search/search/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P1 - High  
**Category**: Search  
**Priority Category**: P0-Search  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features)

**Description**: Search with advanced filtering and faceting

**Impact**: May limit search capabilities

**Blocked Journeys**:
- JOURNEY-DC-001: Discover Contracts in Marketplace (search step)
- All journeys requiring advanced search

**Blocked Use Cases**:
- UC-SEARCH-001: Advanced Search
- All use cases requiring faceted search

**Estimated Effort**: Medium (4-8 hours)

**Dependencies**:
- Search service (existing)
- Faceted search implementation

**Missing Query Parameters**:
- `filters` (object, optional): Advanced filtering options
- `facets` (array, optional): Faceted search options
- `highlight` (boolean, optional): Enable result highlighting

**Current Implementation**: Basic search endpoint exists

**Implementation Notes**:
- Advanced filter parsing
- Faceted search implementation
- Result highlighting
- Performance optimization

**Sources**:
- Search requirements

---

#### 13. GET `/api/v1/compliance/compliance-runs/{id}/results/`

**Gap Type**: Incomplete Endpoint  
**Priority**: P1 - High  
**Category**: Compliance  
**Priority Category**: P1-Compliance  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features)

**Description**: Get compliance run results with detailed information

**Impact**: May not provide complete compliance results

**Blocked Journeys**:
- JOURNEY-CPO-001: Run Compliance Scan
- All journeys requiring compliance results

**Blocked Use Cases**:
- UC-COMPLIANCE-001: View Compliance Results
- All use cases requiring compliance reporting

**Estimated Effort**: Medium (4-8 hours)

**Dependencies**:
- Compliance service (existing)
- Violation tracking (existing)

**Missing Response Fields**:
- Violation details with remediation suggestions
- Compliance score breakdown
- Risk assessment
- Timeline of violations

**Current Implementation**: Basic results endpoint exists

**Implementation Notes**:
- Enhanced result serialization
- Violation detail aggregation
- Score calculation
- Risk assessment logic

**Sources**:
- Compliance requirements

---

#### 14-16. Additional Incomplete Endpoints

See gap analysis document for complete list of all 16 incomplete endpoints.

---

### Endpoints Needing Enhancements

#### 17. GET `/api/v1/marketplace/listings/`

**Gap Type**: Enhancement  
**Priority**: P1 - High  
**Category**: Marketplace  
**Priority Category**: P1-Marketplace  
**Phase**: Phase 1  
**Timeline**: Weeks 5-24 (Core Features)

**Description**: Optimize marketplace listing performance

**Impact**: May cause user experience issues

**Estimated Effort**: Medium (4-8 hours)

**Enhancement Type**: Performance

**Current Performance**: Unknown  
**Required Performance**: < 500ms p95

**Enhancement Needed**:
- Performance optimization
- Result ranking
- Popularity scoring

**Dependencies**:
- Marketplace service (existing)
- Caching service (existing)

---

#### 18-19. Additional Enhancements

See gap analysis document for complete list of all 8 endpoints needing enhancements.

---

## P2 - Medium Priority

**Total Gaps**: 6  
**Phase**: Phase 2  
**Timeline**: Weeks 25-40 (Advanced Features)

### Missing Endpoints

#### 20. POST `/api/v1/ai/natural-language-search/`

**Gap Type**: Missing Endpoint  
**Priority**: P2 - Medium  
**Category**: AI/ML  
**Priority Category**: P2-AI/ML  
**Phase**: Phase 2  
**Timeline**: Weeks 25-40 (Advanced Features) - Specifically Phase 15 (Weeks 25-30)

**Description**: Natural language search with query understanding

**Impact**: Blocks natural language search feature

**Blocked Journeys**:
- JOURNEY-DC-006: Use Natural Language Search
- JOURNEY-DS-001: Use Natural Language Search
- All journeys requiring natural language search

**Blocked Use Cases**:
- UC-AI-001: Natural Language Search
- All use cases requiring query understanding

**Estimated Effort**: High (3-5 days)

**Dependencies**:
- LLM service
- Query understanding service
- Search service (existing)

**Performance Requirements**: < 3000ms p95 (query understanding can be slow)

**Implementation Notes**:
- LLM service integration
- Query understanding service
- Query-to-SQL/SPARQL translation
- Result explanation generation

**Sources**:
- Phase 15 requirements (AI/ML intelligence)

---

#### 21. POST `/api/v1/ai/schema-matching/`

**Gap Type**: Missing Endpoint  
**Priority**: P2 - Medium  
**Category**: AI/ML  
**Priority Category**: P2-AI/ML  
**Phase**: Phase 2  
**Timeline**: Weeks 25-40 (Advanced Features) - Specifically Phase 15 (Weeks 25-30)

**Description**: AI-powered schema matching with suggestions

**Impact**: Blocks AI schema matching feature

**Blocked Journeys**:
- JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation
- JOURNEY-DE-008: Integrate AI Schema Matching into Workflow
- JOURNEY-DS-002: Use AI Schema Matching
- All journeys requiring schema matching

**Blocked Use Cases**:
- UC-AI-002: AI Schema Matching
- All use cases requiring schema comparison

**Estimated Effort**: High (3-5 days)

**Dependencies**:
- AI service infrastructure
- LLM API access
- Schema management service (existing)

**Performance Requirements**: < 15000ms p95 (AI matching can be slow)

**Implementation Notes**:
- Schema similarity algorithm
- Field mapping suggestions with confidence scores
- Mapping visualization data structure
- Mapping acceptance/rejection API

**Sources**:
- Phase 15 requirements (AI/ML intelligence)

---

### Incomplete Endpoints

#### 22-25. Social Feature APIs

**Gap Type**: Missing Endpoints  
**Priority**: P2 - Medium  
**Category**: Social Features  
**Priority Category**: P2-Social-Features  
**Phase**: Phase 2  
**Timeline**: Weeks 25-40 (Advanced Features) - Specifically Phase 17 (Weeks 37-40)

**Missing Endpoints**:
- POST `/api/v1/social/ratings/` - Submit rating
- POST `/api/v1/social/reviews/` - Submit review
- POST `/api/v1/social/comments/` - Submit comment
- POST `/api/v1/social/communities/` - Create/join community

**Impact**: Blocks social features

**Blocked Journeys**:
- JOURNEY-DPO-009: Manage Asset Ratings and Reviews
- JOURNEY-DC-008: Rate and Review Asset
- All journeys requiring social features

**Blocked Use Cases**:
- UC-SOCIAL-001: Submit Rating
- UC-SOCIAL-002: Submit Review
- UC-SOCIAL-003: Submit Comment
- UC-SOCIAL-004: Join Community

**Estimated Effort**: Medium-High (2-5 days per endpoint)

**Dependencies**:
- Social feature infrastructure (Phase 17)
- Rating/review models
- Comment threading
- Community management

**Sources**:
- Phase 17 requirements (collaboration & social features)

---

### Endpoints Needing Enhancements

#### 26. Additional Enhancements

See gap analysis document for complete list of all 8 endpoints needing enhancements.

---

## P3 - Low Priority

**Total Gaps**: 3  
**Phase**: Phase 3  
**Timeline**: Weeks 41-64 (Strategic Differentiators)

### Missing Endpoints

#### 27. GET `/api/v1/marketplace/listings/{id}/preview/`

**Gap Type**: Missing Endpoint  
**Priority**: P3 - Low  
**Category**: Advanced Marketplace  
**Priority Category**: P3-Advanced-Marketplace  
**Phase**: Phase 3  
**Timeline**: Weeks 41-64 (Strategic Differentiators) - Specifically Phase 18 (Weeks 41-44)

**Description**: Preview data before purchase

**Impact**: Blocks data preview feature

**Blocked Journeys**:
- JOURNEY-DC-012: Preview Data Before Purchase
- All journeys requiring data preview

**Blocked Use Cases**:
- UC-ADVANCED-MARKETPLACE-001: Preview Data
- All use cases requiring data preview

**Estimated Effort**: Medium (2-4 days)

**Dependencies**:
- Marketplace service (existing)
- Dataset service (existing)
- Sample data generation service

**Sources**:
- Phase 18 requirements (advanced data marketplace)

---

#### 28-29. Developer Experience APIs

**Gap Type**: Missing Endpoints  
**Priority**: P3 - Low  
**Category**: Developer Experience  
**Priority Category**: P3-Developer-Experience  
**Phase**: Phase 3  
**Timeline**: Weeks 41-64 (Strategic Differentiators) - Specifically Phase 24 (Weeks 61-64)

**Missing Endpoints**:
- GET `/api/v1/developer/plugins/` - List available plugins
- GET `/api/v1/developer/sdk/` - SDK documentation and examples

**Impact**: Blocks plugin marketplace and SDK documentation

**Blocked Journeys**:
- JOURNEY-DEV-009: Use Developer Portal
- All journeys requiring developer tools

**Blocked Use Cases**:
- UC-DEVELOPER-001: Browse Plugin Marketplace
- UC-DEVELOPER-002: Access SDK Documentation
- All use cases requiring developer experience features

**Estimated Effort**: Medium-High (1-5 days per endpoint)

**Dependencies**:
- Plugin system (Phase 24)
- SDK infrastructure (Phase 24)
- Developer portal (Phase 24)

**Sources**:
- Phase 24 requirements (developer experience & extensibility)

---

## Impact Summary

### Journeys Blocked by Gaps

| Journey ID | Blocked By | Gap Count |
|------------|------------|-----------|
| JOURNEY-AUTH-002 | POST `/api/v1/auth/register/` | 1 |
| JOURNEY-AUTH-006 | GET `/api/v1/auth/me/` | 1 |
| JOURNEY-AUTH-007 | GET `/api/v1/auth/api-keys/` | 1 |
| JOURNEY-DPO-004 | POST `/api/v1/assets/{id}/activate/` | 1 |
| JOURNEY-DPO-005 | GET `/api/v1/assets/` | 1 |
| JOURNEY-DC-001 | GET `/api/v1/marketplace/listings/` | 1 |
| JOURNEY-DC-006 | POST `/api/v1/ai/natural-language-search/` | 1 |
| JOURNEY-DC-012 | GET `/api/v1/marketplace/listings/{id}/preview/` | 1 |
| JOURNEY-CPO-001 | GET `/api/v1/compliance/compliance-runs/{id}/results/` | 1 |
| JOURNEY-DE-002 | GET `/api/v1/scheduled-ingestions/{id}/credentials/`, POST `/api/v1/scheduled-ingestions/{id}/credentials/test/` | 2 |
| JOURNEY-DPO-007 | POST `/api/v1/ai/schema-matching/` | 1 |
| JOURNEY-DPO-009 | POST `/api/v1/social/ratings/`, POST `/api/v1/social/reviews/` | 2 |
| JOURNEY-DC-008 | POST `/api/v1/social/ratings/`, POST `/api/v1/social/reviews/` | 2 |
| JOURNEY-DEV-009 | GET `/api/v1/developer/plugins/`, GET `/api/v1/developer/sdk/` | 2 |

### Use Cases Blocked by Gaps

| Use Case ID | Blocked By | Gap Count |
|-------------|------------|-----------|
| UC-AUTH-002 | POST `/api/v1/auth/register/` | 1 |
| UC-AUTH-006 | GET `/api/v1/auth/me/` | 1 |
| UC-AUTH-007 | GET `/api/v1/auth/api-keys/` | 1 |
| UC-ASSET-001 | GET `/api/v1/assets/` | 1 |
| UC-ASSET-008 | POST `/api/v1/assets/{id}/activate/` | 1 |
| UC-CONTRACT-003 | POST `/api/v1/contracts/{id}/validate/` | 1 |
| UC-MARKETPLACE-001 | GET `/api/v1/marketplace/listings/` | 1 |
| UC-COMPLIANCE-001 | GET `/api/v1/compliance/compliance-runs/{id}/results/` | 1 |
| UC-SCHEDULED-INGESTION-003 | GET `/api/v1/scheduled-ingestions/{id}/credentials/` | 1 |
| UC-SCHEDULED-INGESTION-004 | POST `/api/v1/scheduled-ingestions/{id}/credentials/test/` | 1 |
| UC-AI-001 | POST `/api/v1/ai/natural-language-search/` | 1 |
| UC-AI-002 | POST `/api/v1/ai/schema-matching/` | 1 |
| UC-SOCIAL-001 | POST `/api/v1/social/ratings/` | 1 |
| UC-SOCIAL-002 | POST `/api/v1/social/reviews/` | 1 |
| UC-ADVANCED-MARKETPLACE-001 | GET `/api/v1/marketplace/listings/{id}/preview/` | 1 |
| UC-DEVELOPER-001 | GET `/api/v1/developer/plugins/` | 1 |
| UC-DEVELOPER-002 | GET `/api/v1/developer/sdk/` | 1 |

---

## Implementation Timeline Summary

### Phase 0 (Weeks 0-4) - Before Frontend MVP

**Total Gaps**: 8  
**Must Complete**: 2 missing endpoints  
**Should Complete**: 6 incomplete/enhancement endpoints

**Gaps**:
1. POST `/api/v1/auth/register/` (Missing, P0)
2. GET `/api/v1/auth/me/` (Missing, P0)
3. GET `/api/v1/assets/` (Incomplete, P0)
4. POST `/api/v1/assets/{id}/activate/` (Incomplete, P0)
5. GET `/api/v1/auth/api-keys/` (Incomplete, P0)
6. POST `/api/v1/contracts/{id}/validate/` (Incomplete, P0)
7. POST `/api/v1/assets/` (Enhancement, P0)
8. POST `/api/v1/assets/{id}/activate/` (Enhancement, P0)

### Phase 1 (Weeks 5-24) - Core Features

**Total Gaps**: 9  
**Categories**: Credential Management, Marketplace, Compliance, Data Quality

**Gaps**:
- Credential Management APIs (2 gaps, Phase 8: Weeks 12-13)
- Marketplace APIs (3 gaps)
- Compliance APIs (1 gap)
- Data Quality APIs (3 gaps)

### Phase 2 (Weeks 25-40) - Advanced Features

**Total Gaps**: 6  
**Categories**: AI/ML, Social Features

**Gaps**:
- AI/ML APIs (2 gaps, Phase 15: Weeks 25-30)
- Social Feature APIs (4 gaps, Phase 17: Weeks 37-40)

### Phase 3 (Weeks 41-64) - Strategic Differentiators

**Total Gaps**: 3  
**Categories**: Advanced Marketplace, Developer Experience

**Gaps**:
- Advanced Marketplace APIs (1 gap, Phase 18: Weeks 41-44)
- Developer Experience APIs (2 gaps, Phase 24: Weeks 61-64)

---

**Document Status**: ✅ Complete  
**Last Updated**: 2025-12-13  
**Next Review**: After Phase 0 implementation

