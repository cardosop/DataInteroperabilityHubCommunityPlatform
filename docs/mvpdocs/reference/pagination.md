# Pagination

All list endpoints in the Meshant API return paginated responses. Two
pagination strategies are supported: offset-based (default) and cursor-based
(for large datasets).

## Offset-Based Pagination

The default pagination method uses `page` and `page_size` query parameters.

### Request Parameters

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| `page` | `int` | `1` | -- | Page number (1-indexed) |
| `page_size` | `int` | `50` | `100` | Number of results per page |

### Example Request

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://meshant-internal.example.com/api/v1/assets/?page=2&page_size=10"
```

### Response Envelope

```json
{
  "count": 145,
  "next": "https://meshant-internal.example.com/api/v1/assets/?page=3&page_size=10",
  "previous": "https://meshant-internal.example.com/api/v1/assets/?page=1&page_size=10",
  "results": [
    { "id": "a-011", "name": "..." },
    { "id": "a-012", "name": "..." }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Total number of results across all pages |
| `next` | `string \| null` | URL of the next page, or `null` on last page |
| `previous` | `string \| null` | URL of the previous page, or `null` on first page |
| `results` | `array` | Array of resource objects for the current page |

### SDK Usage

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="msh_live_...")

# Fetch page 2 with 10 results per page
assets = client.assets.list(page=2, page_size=10)

# Iterate all pages automatically
for asset in client.assets.list_all():
    print(asset.name)
```

## Cursor-Based Pagination

For endpoints that return very large result sets (e.g., audit events, search),
cursor-based pagination provides stable iteration without skipping or
duplicating records during concurrent writes.

### Request Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `cursor` | `string` | Opaque cursor from the previous response |
| `page_size` | `int` | Number of results per page (default 50, max 100) |

### Example Request

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://meshant-internal.example.com/api/v1/audit/?cursor=eyJpZCI6MTIzfQ&page_size=50"
```

### Response Envelope

```json
{
  "next_cursor": "eyJpZCI6MTczfQ",
  "has_more": true,
  "results": [
    { "id": "evt-051", "action": "asset.created" }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `next_cursor` | `string \| null` | Cursor for the next page, or `null` if no more results |
| `has_more` | `bool` | Whether more results exist after this page |
| `results` | `array` | Array of resource objects |

### SDK Usage

```python
# Cursor-based iteration (automatic)
for event in client.audit.list_all():
    print(event.action)
```

## Best Practices

- Use the default `page_size` of 50 unless you need more results per request.
- Do not use `page_size` greater than 100; the API will cap it silently.
- For large exports, prefer cursor-based pagination to avoid inconsistencies
  from concurrent inserts or deletes.
- Cache the `count` value if you need the total; do not re-request it on
  every page.

## Related

- [Conventions](conventions.md) -- query parameter conventions
- [Rate Limits](rate-limits.md) -- request rate considerations for batch reads
