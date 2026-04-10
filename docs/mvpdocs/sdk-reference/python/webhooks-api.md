# WebhooksAPI

`from datahub_interoperability import WebhooksAPI`

Manages webhook registrations, testing, and delivery log inspection.
WebhooksAPI lets you subscribe to platform events and receive HTTP
callbacks when assets, quality checks, or compliance scans change state.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.webhooks  # type: WebhooksAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20)` | List registered webhooks | `list[Webhook]` |
| `get(id)` | Get webhook by UUID | `Webhook` |
| `create(url, events, secret=None)` | Register a new webhook | `Webhook` |
| `update(id, **kwargs)` | Update webhook configuration | `Webhook` |
| `delete(id)` | Delete a webhook | `None` |
| `test(id)` | Send a test event to the webhook | `DeliveryResult` |
| `list_deliveries(webhook_id, page=1, page_size=20)` | List delivery attempts | `list[Delivery]` |

## Example

```python
wh = api.create(
    url="https://example.com/hooks/meshant",
    events=["asset.created", "dq.completed"],
    secret="whsec_abc123"
)
api.test(wh.id)
```

## Error Handling

```python
from datahub_interoperability import WebhooksAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/webhooks/`](../../api-reference/webhooks.md)
- CLI: [`datahub webhooks`](../../cli-reference/webhooks.md)
