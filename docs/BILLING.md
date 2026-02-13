# Billing and Subscription Management

**Last Updated**: 2026-02-03

This document describes the billing and subscription system, including plans, limits, Stripe integration, webhooks, and usage metering.

---

## Overview

The platform uses Stripe for subscription management and billing. Each tenant can subscribe to a plan (FREE, PRO, or ENTERPRISE) with specific resource limits.

### Key Components

- **TenantPlan**: Defines subscription plans with limits
- **Subscription**: Tracks tenant subscriptions to plans (Stripe integration)
- **UsageRecord**: Records usage metrics for billing
- **Invoice**: Tracks invoices from Stripe

---

## Plans and Limits

### Default Plans

Three default plans are seeded via `python manage.py seed_default_plans`:

#### FREE Plan
- **max_assets**: 10
- **max_datasets**: 20
- **max_api_calls_per_month**: 10,000
- **max_scheduled_ingestions**: 5
- **max_scheduled_runs_per_month**: 50
- **max_scheduled_exports**: 5
- **max_export_runs_per_month**: 20
- **max_storage_gb**: 1

#### PRO Plan
- **max_assets**: 100
- **max_datasets**: 500
- **max_api_calls_per_month**: 100,000
- **max_scheduled_ingestions**: 50
- **max_scheduled_runs_per_month**: 1,000
- **max_scheduled_exports**: 50
- **max_export_runs_per_month**: 500
- **max_storage_gb**: 100

#### ENTERPRISE Plan
- All limits: **Unlimited** (None in limits_json)

### Plan Limits Enforcement

Plan limits are enforced via `PlanLimitService.check_limit()`:

- **Asset creation**: Checks `max_assets` limit
- **Dataset creation**: Checks `max_datasets` limit
- **Scheduled ingestion creation**: Checks `max_scheduled_ingestions` limit
- **Scheduled export creation**: Checks `max_scheduled_exports` limit

When a limit is exceeded, a `403 Forbidden` response is returned with:
```json
{
  "error": "Plan limit exceeded for max_assets",
  "code": "plan_limit_exceeded",
  "details": {
    "limit_key": "max_assets",
    "current": 10,
    "max": 10,
    "requested_delta": 1,
    "new_usage": 11,
    "plan_slug": "free",
    "plan_tier": "FREE"
  }
}
```

---

## Stripe Integration

### Configuration

Set the following environment variables:

```bash
STRIPE_SECRET_KEY=sk_test_...  # Stripe secret key (use test key for development)
STRIPE_WEBHOOK_SECRET=whsec_...  # Webhook signing secret
```

### Creating Subscriptions

#### 1. Create Stripe Customer

```python
from hub.apps.billing.services import SubscriptionService
from hub.apps.tenants.models import Tenant

service = SubscriptionService()
result = service.create_customer(tenant=tenant, email="user@example.com")
stripe_customer_id = result['stripe_customer_id']
```

#### 2. Create Subscription

```python
from hub.apps.tenants.models import TenantPlan

plan = TenantPlan.objects.get(slug='pro')
subscription = service.create_subscription(
    tenant=tenant,
    plan=plan,
    payment_method_id='pm_...',  # Optional: Stripe payment method ID
    trial_days=14  # Optional: Trial period in days
)
```

### Subscription Status

Subscriptions can have the following statuses:

- **ACTIVE**: Subscription is active and paid
- **TRIAL**: Subscription is in trial period
- **PAST_DUE**: Payment failed, subscription is past due
- **CANCELED**: Subscription has been canceled
- **UNPAID**: Subscription is unpaid
- **INCOMPLETE**: Subscription setup incomplete
- **INCOMPLETE_EXPIRED**: Subscription setup expired

### Subscription Lifecycle

1. **Trial**: New subscriptions start with TRIAL status (if trial_days > 0)
2. **Active**: After trial or payment, status becomes ACTIVE
3. **Past Due**: If payment fails, status becomes PAST_DUE
4. **Suspended**: After 3 failed payments, tenant is SUSPENDED (read-only)
5. **Canceled**: User cancels subscription (can be immediate or at period end)

---

## Stripe Webhooks

### Webhook Endpoint

**POST** `/api/v1/billing/webhooks/stripe/`

### Supported Events

#### customer.subscription.updated
- Updates subscription status and period dates
- Suspends tenant if status is PAST_DUE

#### customer.subscription.deleted
- Marks subscription as CANCELED
- Sets canceled_at timestamp

#### invoice.payment_failed
- Creates or updates invoice record
- After 3 failed payments, suspends tenant

#### invoice.paid
- Marks invoice as paid
- Reactivates tenant if was suspended

### Webhook Signature Verification

All webhooks are verified using Stripe's signature verification:

```python
event = stripe.Webhook.construct_event(
    payload, sig_header, STRIPE_WEBHOOK_SECRET
)
```

Invalid signatures return `400 Bad Request`.

### Idempotency

Webhook handlers are idempotent:
- Subscription updates: Updates existing subscription (no duplicates)
- Invoice creation: Creates invoice if doesn't exist, updates if exists

---

## Usage Metering

### Recording Usage

Usage is recorded via `BillingService.record_usage()`:

```python
from hub.apps.billing.services import BillingService
from decimal import Decimal

service = BillingService()
usage_record = service.record_usage(
    tenant_id=tenant_id,
    metric_key='api_calls',
    quantity=Decimal('100'),
    period_start=month_start,
    period_end=month_end
)
```

### Syncing to Stripe

Usage records can be synced to Stripe metering:

```python
service.sync_usage_to_stripe(usage_record_id=str(usage_record.id))
```

**Note**: Stripe metering requires subscription items with metered pricing. This is typically configured in Stripe Dashboard.

### Usage Metrics

Common metric keys:
- `api_calls`: API call count
- `storage_gb`: Storage usage in GB
- `compute_hours`: Compute hours used
- `scheduled_runs`: Scheduled ingestion/export runs

---

## API Endpoints

### Get Subscription

**GET** `/api/v1/billing/subscription/`

Returns current subscription for tenant.

**Response**:
```json
{
  "id": "uuid",
  "tenant": "tenant-uuid",
  "plan": "plan-uuid",
  "plan_name": "Pro Plan",
  "plan_slug": "pro",
  "plan_tier": "PRO",
  "status": "ACTIVE",
  "stripe_subscription_id": "sub_...",
  "stripe_customer_id": "cus_...",
  "current_period_start": "2026-02-01T00:00:00Z",
  "current_period_end": "2026-03-01T00:00:00Z",
  "trial_end": null,
  "canceled_at": null,
  "cancel_at_period_end": false
}
```

### List Invoices

**GET** `/api/v1/billing/invoices/`

Returns list of invoices for tenant.

**Response**:
```json
{
  "count": 5,
  "results": [
    {
      "id": "uuid",
      "tenant": "tenant-uuid",
      "subscription": "subscription-uuid",
      "stripe_invoice_id": "in_...",
      "amount_due": "99.00",
      "amount_paid": "99.00",
      "currency": "usd",
      "status": "paid",
      "invoice_pdf_url": "https://...",
      "hosted_invoice_url": "https://...",
      "period_start": "2026-02-01T00:00:00Z",
      "period_end": "2026-03-01T00:00:00Z",
      "due_date": "2026-03-01T00:00:00Z",
      "paid_at": "2026-02-15T10:30:00Z"
    }
  ]
}
```

### Get Invoice Detail

**GET** `/api/v1/billing/invoices/{id}/`

Returns invoice detail.

---

## Subscription Status Enforcement

### Middleware

`TenantSuspensionMiddleware` (enhanced in Phase 25.2.4) blocks write operations when:

1. **Tenant is SUSPENDED**: All write operations blocked
2. **Subscription is PAST_DUE or UNPAID**: Write operations blocked

**Response** (403 Forbidden):
```json
{
  "error": "Subscription is inactive. Write operations are not allowed.",
  "code": "subscription_inactive",
  "details": {
    "subscription_id": "uuid",
    "status": "PAST_DUE"
  }
}
```

### Grace Period

- **Read operations**: Always allowed (GET, HEAD, OPTIONS)
- **Write operations**: Blocked when subscription inactive or tenant suspended
- **Grace period**: Not currently implemented (all writes blocked immediately)

---

## Failed Payments and Manual Override

### Automatic Suspension

After **3 failed payment attempts**, tenant is automatically suspended:
- Tenant status set to `SUSPENDED`
- All write operations blocked
- Read operations still allowed

### Manual Override

Platform admins can manually override subscription status:

```python
from hub.apps.billing.models import Subscription, SubscriptionStatus

subscription = Subscription.objects.get(id=subscription_id)
subscription.status = SubscriptionStatus.ACTIVE
subscription.save()

# Reactivate tenant
tenant = subscription.tenant
tenant.status = TenantStatus.ACTIVE
tenant.save()
```

### Runbook

See `runbooks/RB-BILLING-001.md` (to be created) for:
- Handling failed payments
- Manual subscription reactivation
- Tenant suspension override
- Stripe webhook troubleshooting

---

## Testing

### Stripe Test Mode

All tests use Stripe test mode:

```python
# Set in test settings
STRIPE_SECRET_KEY = 'sk_test_...'
STRIPE_WEBHOOK_SECRET = 'whsec_test_...'
```

### Test Cards

Use Stripe test cards:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires authentication**: `4000 0025 0000 3155`

### Mocking

**No mocks allowed** per Phase 25 requirements:
- Tests use real Stripe test mode
- Real database transactions
- Real service layer calls

---

---

## Rate Limit Overrides (Phase 25.7.2)

### Per-Tenant Rate Limits

Rate limits can be overridden per tenant via `TenantConfig.rate_limits`:

```python
tenant_config.rate_limits = {
    'assets': {
        'burst_per_10s': 20,
        'sustained_per_min': 100,
        'daily_cap': 10000
    },
    'datasets': {
        'burst_per_10s': 10,
        'sustained_per_min': 50,
        'daily_cap': 5000
    }
}
```

### Per-Plan Rate Limits

Rate limits can also be defined in plan `limits_json`:

```json
{
  "max_assets": 100,
  "max_datasets": 500,
  "rate_limits": {
    "assets": {
      "burst_per_10s": 20,
      "sustained_per_min": 100
    }
  }
}
```

### Override Priority

1. **TenantConfig.rate_limits**: Highest priority (tenant-specific override)
2. **Plan limits_json.rate_limits**: Medium priority (plan default)
3. **Platform defaults**: Lowest priority (fallback)

### Configuration

Rate limits are configured via:

- **TenantConfig API**: `PATCH /api/v1/tenants/{id}/config/` with `rate_limits` field
- **Plan limits_json**: Set during plan creation or update
- **Platform defaults**: Defined in `hub.apps.tenants.validators.get_platform_defaults()`

---

## Related Documentation

- `docs/DATA_RESIDENCY.md` - Data residency and regional considerations
- `docs/TENANT_ISOLATION.md` - Tenant isolation and multi-tenancy (includes plan limits and suspension)
- `docs/ONBOARDING.md` - Self-service tenant onboarding
