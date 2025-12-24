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

