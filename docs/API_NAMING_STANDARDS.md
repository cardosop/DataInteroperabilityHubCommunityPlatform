# API Naming Standards

**Document Version**: 1.0.0
**Last Updated**: 2025-12-28
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

