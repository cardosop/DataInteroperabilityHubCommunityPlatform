# Meshant Billing API

The Billing API manages subscriptions, invoices, usage metering, and
quota enforcement for Meshant tenants. It integrates with the platform's
plan tiers to track consumption of API calls, storage, and compute
resources, and exposes billing history for financial reconciliation.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/billing/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /billing/subscription/ | Get the current tenant's subscription details |
| PUT | /billing/subscription/ | Change the subscription plan |
| POST | /billing/subscription/cancel/ | Cancel the subscription at period end |
| GET | /billing/invoices/ | List invoices for the current tenant |
| GET | /billing/invoices/{id}/ | Get invoice details |
| GET | /billing/invoices/{id}/pdf/ | Download invoice as PDF |
| GET | /billing/usage/ | Get current billing-period usage summary |
| GET | /billing/usage/history/ | Get historical usage across billing periods |
| GET | /billing/quotas/ | Get current quota limits and consumption |
| POST | /billing/payment-method/ | Add or update the payment method |
| GET | /billing/payment-method/ | Get the current payment method on file |
| DELETE | /billing/payment-method/ | Remove the payment method |

## Request / Response Examples

### GET /billing/subscription/

**Response 200:**

```json
{
  "tenant_id": "tnt_xyz",
  "plan": "professional",
  "status": "active",
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "cancel_at_period_end": false
}
```

### GET /billing/quotas/

**Response 200:**

```json
{
  "plan": "professional",
  "quotas": {
    "api_calls_per_month": {"limit": 100000, "used": 42300, "remaining": 57700},
    "storage_gb": {"limit": 500, "used": 128.4, "remaining": 371.6},
    "datasets": {"limit": 1000, "used": 87, "remaining": 913},
    "members": {"limit": 50, "used": 12, "remaining": 38}
  }
}
```

### GET /billing/usage/

**Response 200:**

```json
{
  "period_start": "2026-04-01T00:00:00Z",
  "period_end": "2026-05-01T00:00:00Z",
  "api_calls": 42300,
  "storage_gb": 128.4,
  "compute_minutes": 340,
  "estimated_cost_usd": 89.50
}
```

## Common Parameters

- `page` (int) -- Page number for pagination (invoices list).
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `since` (datetime) -- Start of usage reporting window (ISO 8601).
- `until` (datetime) -- End of usage reporting window (ISO 8601).
- `granularity` (string) -- Usage aggregation: `daily`, `monthly`.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 402 | `BILLING_PAYMENT_REQUIRED` | Payment method is missing or declined |
| 403 | `BILLING_FORBIDDEN` | Caller lacks billing management permission |
| 404 | `BILLING_INVOICE_NOT_FOUND` | Invoice ID does not exist |
| 409 | `BILLING_PLAN_DOWNGRADE_BLOCKED` | Current usage exceeds the target plan's limits |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub billing`](../cli-reference/billing.md)
- SDK: [`BillingAPI`](../sdk-reference/python/billing.md)
