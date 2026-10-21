# VersioningAPI

`from datahub_interoperability import VersioningAPI`

Manages resource versioning and history tracking for contracts, assets, and
datasets. VersioningAPI lets you list historical versions, compare changes
between versions, and restore previous states.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.versioning  # type: VersioningAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list_versions(resource_type, resource_id)` | List all versions of a resource | `list[Version]` |
| `get_version(resource_type, resource_id, version)` | Get a specific version | `Version` |
| `compare(resource_type, resource_id, v1, v2)` | Compare two versions | `VersionDiff` |
| `restore(resource_type, resource_id, version)` | Restore a previous version | `Version` |
| `tag(resource_type, resource_id, version, label)` | Tag a version with a label | `Version` |

## Example

```python
versions = api.list_versions("contract", "c-123")
diff = api.compare("contract", "c-123", v1=1, v2=3)
print(diff.changes)
```

## Error Handling

```python
from datahub_interoperability import VersioningAPI, MVPGatedFeatureError

try:
    result = api.list_versions("contract", "c-123")
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/versioning/`](../../api-reference/versioning.md)
- CLI: [`datahub versioning`](../../cli-reference/versioning.md)
