# API Versioning and Deprecation

**Last Updated**: 2026-02-03

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
