# LineageAPI

`from datahub_interoperability import LineageAPI`

Queries and manages data lineage graphs that track how data flows between
assets, transformations, and consumers. LineageAPI supports upstream and
downstream traversal as well as impact analysis.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.lineage  # type: LineageAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `get_upstream(asset_id, depth=1)` | Get upstream lineage for an asset | `LineageGraph` |
| `get_downstream(asset_id, depth=1)` | Get downstream lineage for an asset | `LineageGraph` |
| `get_full(asset_id, depth=2)` | Get full lineage graph | `LineageGraph` |
| `add_edge(source_id, target_id, type=None)` | Register a lineage edge | `LineageEdge` |
| `delete_edge(edge_id)` | Remove a lineage edge | `None` |
| `impact_analysis(asset_id)` | Analyze downstream impact of changes | `list[ImpactResult]` |

## Example

```python
graph = api.get_downstream(asset_id="a-001", depth=3)
for node in graph.nodes:
    print(f"{node.name} ({node.type})")
```

## Error Handling

```python
from datahub_interoperability import LineageAPI, MVPGatedFeatureError

try:
    result = api.get_upstream(asset_id="a-001")
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/lineage/`](../../api-reference/lineage.md)
- CLI: [`datahub lineage`](../../cli-reference/lineage.md)
