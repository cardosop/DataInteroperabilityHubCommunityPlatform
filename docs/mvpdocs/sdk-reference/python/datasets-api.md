# DatasetsAPI

`from datahub_interoperability import DatasetsAPI`

Manages datasets including creation, schema inference, validation, and
metadata updates. Datasets represent the raw data files that back data
assets in Meshant.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.datasets  # type: DatasetsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20)` | List all datasets | `list[Dataset]` |
| `get(id)` | Get dataset by UUID | `Dataset` |
| `create(name, file_id, format=None)` | Create a dataset from an uploaded file | `Dataset` |
| `update(id, **kwargs)` | Update dataset metadata | `Dataset` |
| `infer_schema(id)` | Infer and attach a schema | `Schema` |
| `preview(id, rows=10)` | Preview first N rows | `list[dict]` |
| `delete(id)` | Delete a dataset | `None` |

## Example

```python
ds = api.create(name="events_2026", file_id="f-789")
schema = api.infer_schema(ds.id)
print(schema.columns)
```

## Error Handling

```python
from datahub_interoperability import DatasetsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/datasets/`](../../api-reference/datasets.md)
- CLI: [`datahub datasets`](../../cli-reference/datasets.md)
