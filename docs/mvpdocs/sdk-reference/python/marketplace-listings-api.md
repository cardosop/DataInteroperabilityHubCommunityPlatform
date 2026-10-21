# MarketplaceListingsAPI

`from datahub_interoperability import MarketplaceListingsAPI`

Manages marketplace data product listings, orders, and entitlements.
MarketplaceListingsAPI allows producers to list data products and consumers
to discover, order, and access them through the Meshant marketplace.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.marketplace_listings  # type: MarketplaceListingsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, category=None)` | List marketplace listings | `list[Listing]` |
| `get(id)` | Get listing by UUID | `Listing` |
| `create(name, asset_id, price=None, description=None)` | Create a new listing | `Listing` |
| `update(id, **kwargs)` | Update listing details | `Listing` |
| `publish(id)` | Publish a draft listing | `Listing` |
| `place_order(listing_id)` | Place an order for a listing | `Order` |
| `list_orders(page=1, page_size=20)` | List orders for the current tenant | `list[Order]` |
| `get_order(id)` | Get order details | `Order` |

## Example

```python
listings = api.list(category="financial")
order = api.place_order(listings[0].id)
print(f"Order status: {order.status}")
```

## Error Handling

```python
from datahub_interoperability import MarketplaceListingsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/marketplace/`](../../api-reference/marketplace.md)
- CLI: [`datahub marketplace`](../../cli-reference/marketplace.md)
