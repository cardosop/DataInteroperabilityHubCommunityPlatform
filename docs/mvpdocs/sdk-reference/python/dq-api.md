# DQAPI

`from datahub_interoperability import DQAPI`

Runs data quality checks and profiling against datasets and assets.
DQAPI supports triggering checks, retrieving results, and viewing
historical quality trends to ensure data meets defined expectations.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.dq  # type: DQAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list_runs(page=1, page_size=20, asset_id=None)` | List DQ check runs | `list[DQRun]` |
| `get_run(id)` | Get a DQ run by ID | `DQRun` |
| `trigger(asset_id, checks=None)` | Trigger a DQ check on an asset | `DQRun` |
| `get_results(run_id)` | Get detailed results for a run | `list[DQResult]` |
| `profile(asset_id)` | Run data profiling on an asset | `Profile` |

## Example

```python
run = api.trigger(asset_id="a-123", checks=["completeness", "uniqueness"])
results = api.get_results(run.id)
for r in results:
    print(f"{r.check}: {r.status}")
```

## Error Handling

```python
from datahub_interoperability import DQAPI, MVPGatedFeatureError

try:
    result = api.list_runs()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/dq/`](../../api-reference/dq.md)
- CLI: [`datahub dq`](../../cli-reference/dq.md)
