# SearchAPI

`from datahub_interoperability import SearchAPI`

Provides full-text search, faceted filtering, and autocomplete across all
indexed resources in Meshant. SearchAPI queries the platform search index
to help users discover assets, datasets, contracts, and listings.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.search  # type: SearchAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `query(q, page=1, page_size=20, filters=None)` | Full-text search across resources | `SearchResults` |
| `autocomplete(q, limit=10)` | Get autocomplete suggestions | `list[Suggestion]` |
| `facets(q=None, fields=None)` | Get facet counts for a query | `dict[str, list[Facet]]` |
| `reindex(resource_type=None)` | Trigger a reindex (admin only) | `Job` |

## Example

```python
results = api.query("customer transactions", filters={"type": "asset"})
for hit in results.items:
    print(f"{hit.name} (score: {hit.score})")
```

## Error Handling

```python
from datahub_interoperability import SearchAPI, MVPGatedFeatureError

try:
    result = api.query("test")
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/search/`](../../api-reference/search.md)
- CLI: [`datahub search`](../../cli-reference/search.md)
