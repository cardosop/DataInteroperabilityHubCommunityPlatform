# AuditAPI

`from datahub_interoperability import AuditAPI`

Provides access to the platform audit trail. Every significant action in
Meshant generates an audit event that records who did what, when, and on
which resource. AuditAPI lets you query, filter, and export these events.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.audit  # type: AuditAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, actor=None, action=None, since=None)` | List audit events with optional filters | `list[AuditEvent]` |
| `get(id)` | Get a single audit event by UUID | `AuditEvent` |
| `export(format="csv", since=None, until=None)` | Export audit events to CSV or JSON | `bytes` |
| `summary(since=None, until=None)` | Get aggregated audit summary | `AuditSummary` |

## Example

```python
events = api.list(action="asset.published", page_size=50)
csv_data = api.export(format="csv", since="2026-01-01")
```

## Error Handling

```python
from datahub_interoperability import AuditAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/audit/`](../../api-reference/audit.md)
- CLI: [`datahub audit`](../../cli-reference/audit.md)
