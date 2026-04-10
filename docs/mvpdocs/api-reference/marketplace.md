# Meshant Marketplace API

The Marketplace API powers the Meshant data marketplace where tenants
can publish data products for discovery and consumption by other tenants.
It manages listings, ordering workflows, and entitlement enforcement
so that data producers retain control over access.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/marketplace/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /marketplace/listings/ | Browse published data product listings |
| GET | /marketplace/listings/{id}/ | Get listing details |
| POST | /marketplace/listings/ | Create a new listing (publisher only) |
| PUT | /marketplace/listings/{id}/ | Update listing metadata or pricing |
| DELETE | /marketplace/listings/{id}/ | Unpublish and remove a listing |
| POST | /marketplace/orders/ | Place an order for a listing |
| GET | /marketplace/orders/ | List orders for the current tenant |
| GET | /marketplace/orders/{id}/ | Get order details |
| POST | /marketplace/orders/{id}/approve/ | Approve a pending order (publisher) |
| POST | /marketplace/orders/{id}/reject/ | Reject a pending order (publisher) |
| GET | /marketplace/entitlements/ | List active entitlements |
| GET | /marketplace/entitlements/{id}/ | Get entitlement details |
| POST | /marketplace/entitlements/{id}/revoke/ | Revoke an entitlement |

## Request / Response Examples

### POST /marketplace/listings/

**Request body:**

```json
{
  "asset_id": "ast_001",
  "title": "Q1 Sales Data Product",
  "description": "Curated quarterly sales figures with daily granularity",
  "pricing_model": "free",
  "tags": ["sales", "finance"]
}
```

**Response 201:**

```json
{
  "id": "lst_aaa",
  "title": "Q1 Sales Data Product",
  "status": "published",
  "publisher_tenant_id": "tnt_xyz",
  "created_at": "2026-04-09T14:00:00Z"
}
```

### POST /marketplace/orders/

**Request body:**

```json
{
  "listing_id": "lst_aaa",
  "justification": "Need sales data for cross-team forecasting"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `search` (string) -- Full-text search on title and description.
- `tags` (string) -- Comma-separated tag filter.
- `pricing_model` (string) -- Filter: `free`, `subscription`, `per_request`.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 403 | `MARKETPLACE_NOT_PUBLISHER` | Caller is not a publisher for this listing |
| 404 | `MARKETPLACE_LISTING_NOT_FOUND` | Listing ID does not exist |
| 404 | `MARKETPLACE_ORDER_NOT_FOUND` | Order ID does not exist |
| 409 | `MARKETPLACE_ORDER_ALREADY_PROCESSED` | Order has already been approved or rejected |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub marketplace`](../cli-reference/marketplace.md)
- SDK: [`MarketplaceAPI`](../sdk-reference/python/marketplace.md)
