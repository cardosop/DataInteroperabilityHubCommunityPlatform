# SemanticAPI

`from datahub_interoperability import SemanticAPI`

Provides semantic URI resolution, SPARQL query execution, and JSON-LD
context management. SemanticAPI enables linked-data interoperability by
exposing assets as semantic resources with machine-readable metadata.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.semantic  # type: SemanticAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `resolve(uri)` | Resolve a semantic URI to a resource | `SemanticResource` |
| `sparql(query)` | Execute a SPARQL query | `SPARQLResult` |
| `list_contexts(page=1, page_size=20)` | List JSON-LD contexts | `list[Context]` |
| `get_context(id)` | Get a JSON-LD context by ID | `Context` |
| `create_context(name, definition)` | Create a JSON-LD context | `Context` |
| `delete_context(id)` | Delete a JSON-LD context | `None` |

## Example

```python
resource = api.resolve("meshant://assets/customer-events")
result = api.sparql("SELECT ?s WHERE { ?s a dcat:Dataset } LIMIT 10")
for row in result.bindings:
    print(row["s"])
```

## Error Handling

```python
from datahub_interoperability import SemanticAPI, MVPGatedFeatureError

try:
    result = api.resolve("meshant://assets/test")
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/semantic/`](../../api-reference/semantic.md)
- CLI: [`datahub semantic`](../../cli-reference/semantic.md)
