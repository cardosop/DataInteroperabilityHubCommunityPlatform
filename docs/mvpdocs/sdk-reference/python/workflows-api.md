# WorkflowsAPI

`from datahub_interoperability import WorkflowsAPI`

Manages orchestration workflows that coordinate multi-step data operations.
WorkflowsAPI supports creating, triggering, and monitoring workflows that
chain ingestion, transformation, quality, and publishing steps.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.workflows  # type: WorkflowsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, status=None)` | List workflows | `list[Workflow]` |
| `get(id)` | Get workflow by UUID | `Workflow` |
| `create(name, steps)` | Create a workflow definition | `Workflow` |
| `update(id, **kwargs)` | Update a workflow | `Workflow` |
| `trigger(id, params=None)` | Trigger a workflow run | `WorkflowRun` |
| `get_run(run_id)` | Get a workflow run status | `WorkflowRun` |
| `cancel_run(run_id)` | Cancel a running workflow | `WorkflowRun` |
| `list_runs(workflow_id=None, page=1, page_size=20)` | List workflow runs | `list[WorkflowRun]` |

## Example

```python
wf = api.create(
    name="daily_ingest",
    steps=[
        {"type": "ingest", "source": "s3://bucket/raw/"},
        {"type": "dq_check", "checks": ["completeness"]},
        {"type": "publish"}
    ]
)
run = api.trigger(wf.id)
print(f"Run status: {run.status}")
```

## Error Handling

```python
from datahub_interoperability import WorkflowsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/workflows/`](../../api-reference/workflows.md)
- CLI: [`datahub workflows`](../../cli-reference/workflows.md)
