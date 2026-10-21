# ObservabilityAPI

`from datahub_interoperability import ObservabilityAPI`

Provides access to platform observability metrics, health checks, and
alerting configuration. ObservabilityAPI helps operators monitor system
health and configure alerts for anomalies.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.observability  # type: ObservabilityAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `health()` | Get platform health status | `HealthStatus` |
| `get_metrics(since=None, until=None)` | Get platform metrics | `MetricsReport` |
| `list_alerts(page=1, page_size=20)` | List configured alerts | `list[Alert]` |
| `create_alert(name, condition, channel)` | Create an alert rule | `Alert` |
| `update_alert(id, **kwargs)` | Update an alert rule | `Alert` |
| `delete_alert(id)` | Delete an alert rule | `None` |
| `list_incidents(page=1, page_size=20)` | List triggered incidents | `list[Incident]` |

## Example

```python
health = api.health()
print(f"Status: {health.status}, uptime: {health.uptime_seconds}s")
metrics = api.get_metrics(since="2026-04-01")
```

## Error Handling

```python
from datahub_interoperability import ObservabilityAPI, MVPGatedFeatureError

try:
    result = api.health()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/platform/`](../../api-reference/platform.md)
- CLI: [`datahub observability`](../../cli-reference/observability.md)
