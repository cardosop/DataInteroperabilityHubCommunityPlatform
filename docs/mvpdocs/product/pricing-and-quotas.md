# Pricing and Quotas

Meshant offers three subscription tiers. Each tier defines resource
limits, API rate limits, and support levels. Quota enforcement is
automatic and fail-closed: operations that would exceed a limit are
rejected with a `429` or `403` response and a machine-readable error
body.

---

## Plan Tiers

| Dimension | Free | Professional | Enterprise |
|-----------|------|--------------|------------|
| Assets | 10 | 100 | Unlimited |
| Contracts | 5 | 50 | Unlimited |
| Datasets | 20 | 200 | Unlimited |
| Files | 50 | 500 | Unlimited |
| Max file upload size | 100 MB | 1 GB | 10 GB |
| API calls per month | 10,000 | 100,000 | Unlimited |
| DQ runs per month | 10 | 100 | Unlimited |
| Compliance scans per month | 5 | 50 | Unlimited |
| Marketplace listings | 2 | 20 | Unlimited |
| Webhook subscriptions | 5 | 50 | Unlimited |
| Retention policies | 5 | 50 | Unlimited |
| Access requests per month | 10 | 100 | Unlimited |
| Scheduled runs per month | 10 | 100 | Unlimited |
| Users per tenant | 5 | 25 | Unlimited |
| Support | Community | Email (48 h SLA) | Dedicated (4 h SLA) |

---

## Quota Enforcement

When a tenant reaches a plan limit the platform behaves as follows:

1. **Create / upload operations** return HTTP `403 Forbidden` with error
   code `PLAN_LIMIT_EXCEEDED` and a body that includes the limit key,
   the current usage, and the plan ceiling.

2. **API rate limits** return HTTP `429 Too Many Requests` with a
   `Retry-After` header indicating when the tenant may retry.

3. **File size limits** are checked at upload initiation. An upload that
   would exceed `max_file_size_bytes` is rejected before any bytes are
   stored.

4. **Read operations** are never blocked by quota limits. A tenant that
   has hit its asset cap can still list and retrieve existing assets.

5. **Downgrade validation**: when a tenant switches from a higher plan
   to a lower one, the platform checks whether current usage exceeds the
   new plan limits. If it does, the downgrade is rejected with error
   code `DOWNGRADE_LIMIT_EXCEEDED` and a list of dimensions that must be
   reduced first.

---

## Subscription Lifecycle

```
TRIALING --> ACTIVE       (payment confirmed)
TRIALING --> CANCELLED    (trial expired without payment)
ACTIVE   --> PAST_DUE     (payment failed)
PAST_DUE --> ACTIVE       (payment recovered)
PAST_DUE --> CANCELLED    (payment not recovered)
ACTIVE   --> CANCELLED    (immediate cancellation)
```

While a subscription is `PAST_DUE`, write operations are suspended but
read access continues so tenants can export their data.

---

## Billing API

Usage and subscription details are available through the billing API:

- `GET /api/v1/billing/subscription/` -- current plan, status, renewal date.
- `GET /api/v1/billing/usage/` -- current-period usage per limit key.
- `POST /api/v1/billing/subscription/change-plan/` -- request plan change.
- `POST /api/v1/billing/refunds/` -- admin-only refund processing.

See [Billing concept page](../concepts/billing.md) for details on
metering, Stripe integration, and webhook event handling.
