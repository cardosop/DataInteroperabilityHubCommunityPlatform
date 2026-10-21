# Meshant Search API

The Search API provides full-text and faceted search across all catalog
entities in the Meshant platform -- datasets, assets, contracts, and
marketplace listings. It supports autocomplete suggestions and
relevance-ranked results with highlighted matches.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/search/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /search/ | Full-text search across all resource types |
| GET | /search/suggest/ | Autocomplete suggestions for a partial query |
| GET | /search/facets/ | Return available facets and their value counts |
| POST | /search/advanced/ | Advanced search with structured filters |
| GET | /search/recent/ | List the current user's recent searches |
| DELETE | /search/recent/ | Clear the current user's recent search history |

## Request / Response Examples

### GET /search/?q=sales&type=dataset&domain=finance

**Response 200:**

```json
{
  "total": 3,
  "results": [
    {
      "id": "ds_abc123",
      "type": "dataset",
      "name": "Q1 Sales",
      "description": "Quarterly sales data for 2026-Q1",
      "domain": "finance",
      "score": 12.5,
      "highlights": {
        "name": ["Q1 <em>Sales</em>"]
      }
    }
  ],
  "facets": {
    "type": [{"value": "dataset", "count": 2}, {"value": "asset", "count": 1}],
    "domain": [{"value": "finance", "count": 3}]
  }
}
```

### GET /search/suggest/?q=cust

**Response 200:**

```json
{
  "suggestions": [
    {"text": "Customer Events", "type": "asset", "id": "ast_002"},
    {"text": "customer_email", "type": "column", "dataset_id": "ds_def456"}
  ]
}
```

## Common Parameters

- `q` (string) -- The search query string.
- `type` (string) -- Limit results to a resource type: `dataset`, `asset`, `contract`, `listing`.
- `domain` (string) -- Filter by business domain.
- `tags` (string) -- Comma-separated tag filter.
- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `sort` (string) -- Sort order: `relevance` (default), `created_at`, `name`.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `SEARCH_QUERY_INVALID` | Query string contains unsupported syntax |
| 400 | `SEARCH_FILTER_INVALID` | An advanced filter references an unknown field |
| 503 | `SEARCH_INDEX_UNAVAILABLE` | The search index is temporarily unreachable |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub search`](../cli-reference/search.md)
- SDK: [`SearchAPI`](../sdk-reference/python/search.md)
