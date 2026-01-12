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

**Last Updated**: 2025-01-15
**Version**: 1.0.0

