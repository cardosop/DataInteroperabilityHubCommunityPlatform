# BillingAPI

`from datahub_interoperability import BillingAPI`

Manages subscriptions, invoices, usage metering, and quota enforcement.
BillingAPI integrates with the platform payment layer to provide
programmatic access to all billing operations within a tenant.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.billing  # type: BillingAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `get_subscription()` | Get current tenant subscription | `Subscription` |
| `list_invoices(page=1, page_size=20)` | List invoices | `list[Invoice]` |
| `get_invoice(id)` | Get invoice by ID | `Invoice` |
| `get_usage(period=None)` | Get usage metrics for billing period | `UsageReport` |
| `list_quotas()` | List quota limits and current usage | `list[Quota]` |
| `update_subscription(plan_id)` | Change subscription plan | `Subscription` |

## Example

```python
usage = api.get_usage(period="2026-03")
print(f"API calls: {usage.api_calls}")
```

## Error Handling

```python
from datahub_interoperability import BillingAPI, MVPGatedFeatureError

try:
    result = api.get_subscription()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/billing/`](../../api-reference/billing.md)
- CLI: [`datahub billing`](../../cli-reference/billing.md)
