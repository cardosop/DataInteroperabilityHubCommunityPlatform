# Conventions

This page documents the REST conventions that apply across all Meshant API
endpoints.

## URL Structure

All API endpoints follow a consistent URL pattern:

```
https://meshant-internal.example.com/api/v1/{resource}/
https://meshant-internal.example.com/api/v1/{resource}/{id}/
https://meshant-internal.example.com/api/v1/{resource}/{id}/{sub-resource}/
```

- All URLs end with a trailing slash.
- Resource names use lowercase with hyphens for multi-word names
  (e.g., `marketplace-listings`).
- Sub-resources are nested under their parent (e.g., `/assets/{id}/versions/`).

## HTTP Methods

| Method | Usage | Idempotent |
|--------|-------|------------|
| `GET` | Retrieve a resource or list of resources | Yes |
| `POST` | Create a new resource or trigger an action | No (use Idempotency-Key) |
| `PUT` | Full replacement of a resource | Yes |
| `PATCH` | Partial update of a resource | Yes |
| `DELETE` | Remove a resource | Yes |

## Content Types

| Direction | Content-Type |
|-----------|-------------|
| Request body | `application/json` |
| Response body | `application/json` |
| File upload | `multipart/form-data` |
| File download | Varies (`application/octet-stream`, `text/csv`, etc.) |

## Identifiers

All resources use UUID v4 identifiers:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

UUIDs are generated server-side and returned in creation responses.

## Date and Time Format

All dates and times use ISO 8601 format in UTC:

```json
{
  "created_at": "2026-04-09T14:30:00Z",
  "updated_at": "2026-04-09T15:00:00Z"
}
```

- Timestamps always include the `Z` suffix (UTC).
- Date-only fields use `YYYY-MM-DD` format (e.g., `2026-04-09`).

## Filtering

List endpoints support filtering via query parameters:

```bash
GET /api/v1/assets/?status=published&created_after=2026-01-01
```

Common filter patterns:

| Pattern | Example | Description |
|---------|---------|-------------|
| Exact match | `?status=published` | Field equals the value |
| Date range | `?created_after=2026-01-01&created_before=2026-04-01` | Field within range |
| Search | `?search=customer` | Full-text search on name/description |
| Multiple values | `?status=draft&status=published` | Field matches any value |

## Sorting

List endpoints support sorting via the `ordering` query parameter:

```bash
GET /api/v1/assets/?ordering=-created_at
```

- Prefix with `-` for descending order.
- Multiple fields: `?ordering=-created_at,name`.
- Default ordering is `-created_at` (newest first).

## Response Envelope

Single-resource responses return the object directly:

```json
{
  "id": "a-123",
  "name": "customer_events",
  "status": "published"
}
```

List responses use the pagination envelope:

```json
{
  "count": 145,
  "next": "https://meshant-internal.example.com/api/v1/assets/?page=2",
  "previous": null,
  "results": [...]
}
```

## Versioning Policy

The API version is included in the URL path (`/api/v1/`). The versioning
policy follows these rules:

- **Non-breaking changes** (new fields, new endpoints) are added to the
  current version without a version bump.
- **Breaking changes** (removed fields, changed semantics) result in a
  new version (`/api/v2/`).
- Deprecated endpoints are announced at least 6 months before removal.
- The `X-API-Deprecation` header is included on deprecated endpoints.

## Empty Responses

Successful operations that return no body use HTTP `204 No Content`:

```
HTTP/1.1 204 No Content
```

This applies to `DELETE` operations and some action endpoints.

## Related

- [Pagination](pagination.md) -- pagination parameters and response envelope
- [Error Codes](error-codes.md) -- error response format
- [Authentication](authentication.md) -- required headers
- [Idempotency](idempotency.md) -- safe retries for POST/PUT
