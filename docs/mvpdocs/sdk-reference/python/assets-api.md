# AssetsAPI

`from datahub_interoperability import AssetsAPI`

Manages the full lifecycle of data assets including creation via data-first
and contract-first flows, metadata updates, publishing, and retirement.
Assets are the central entity in Meshant connecting datasets, contracts,
and quality results.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.assets  # type: AssetsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, status=None)` | List all assets with optional status filter | `list[Asset]` |
| `get(id)` | Get asset by UUID | `Asset` |
| `create(name, dataset_id, contract_id=None)` | Create a new data asset | `Asset` |
| `update(id, **kwargs)` | Update asset metadata | `Asset` |
| `publish(id)` | Publish an asset to the marketplace | `Asset` |
| `retire(id)` | Retire an asset | `Asset` |
| `delete(id)` | Permanently delete a draft asset | `None` |

## Example

```python
asset = api.create(name="customer_events", dataset_id="d-123")
api.publish(asset.id)
```

## Error Handling

```python
from datahub_interoperability import AssetsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/assets/`](../../api-reference/assets.md)
- CLI: [`datahub assets`](../../cli-reference/assets.md)
