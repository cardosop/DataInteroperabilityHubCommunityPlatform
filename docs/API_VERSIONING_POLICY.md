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

**Last Updated**: 2025-01-15  
**Maintainer**: Engineering Team  
**Status**: ✅ Complete
