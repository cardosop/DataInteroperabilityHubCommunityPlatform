# API Best Practices

## Endpoint patterns
Use standardized nested resource patterns:
- `/api/v1/compliance/runs/`
- `/api/v1/dq/runs/`

## Error responses
All error responses use a canonical shape with `code`, `detail`, and optional `errors` list.

## Pagination
List endpoints support `?page=` and `?page_size=` query parameters. Default page size is 20, max is 100.

## Rate limiting
Rate limits are per-tenant. Exceeding the limit returns HTTP 429 with a `Retry-After` header.

## Versioning
The API version is specified in the URL path (`/api/v1/`). Breaking changes require a new major version.
