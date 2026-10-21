# JobsAPI

`from datahub_interoperability import JobsAPI`

Tracks background jobs spawned by asynchronous operations such as DQ checks,
compliance scans, and data exports. JobsAPI lets you poll job status, retrieve
results, and cancel running jobs.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.jobs  # type: JobsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, status=None, type=None)` | List background jobs | `list[Job]` |
| `get(id)` | Get job by UUID | `Job` |
| `cancel(id)` | Cancel a running or queued job | `Job` |
| `wait(id, timeout=300, poll_interval=5)` | Block until job completes | `Job` |
| `get_result(id)` | Get the output of a completed job | `dict` |

## Example

```python
jobs = api.list(status="running")
completed = api.wait(jobs[0].id, timeout=120)
result = api.get_result(completed.id)
```

## Error Handling

```python
from datahub_interoperability import JobsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/jobs/`](../../api-reference/jobs.md)
- CLI: [`datahub jobs`](../../cli-reference/jobs.md)
