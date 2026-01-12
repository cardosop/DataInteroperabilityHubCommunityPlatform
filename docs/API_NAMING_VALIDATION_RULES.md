# API Naming Validation Rules for CI/CD

**Document Version**: 1.0.0
**Last Updated**: 2025-12-28
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

