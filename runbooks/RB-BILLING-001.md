# RB-BILLING-001: Billing System Troubleshooting

**Severity**: P2 (service degradation) to P1 (billing failure)
**Last Updated**: 2026-03-22
**Owner**: Platform Team

---

## B6: Stripe Circuit Breaker

### Symptoms

- Billing operations return 503
- Logs show: `StripeCircuitBreaker: circuit OPEN`
- Stripe API calls timing out or returning 5xx

### Diagnosis

```bash
# Check circuit breaker state
docker exec hub-test-api python /app/hub/manage.py shell -c "
from django.core.cache import cache
state = cache.get('stripe_circuit_breaker_state', 'CLOSED')
failures = cache.get('stripe_circuit_breaker_failures', 0)
print(f'State: {state}, Failures: {failures}')
"
```

### Resolution

1. **Wait for auto-recovery**: Circuit opens for 30 seconds, then half-opens (allows 1 test request)
2. **Check Stripe status**: https://status.stripe.com/
3. **Force reset** (if Stripe is healthy):

```bash
docker exec hub-test-api python /app/hub/manage.py shell -c "
from django.core.cache import cache
cache.delete('stripe_circuit_breaker_state')
cache.delete('stripe_circuit_breaker_failures')
print('Circuit breaker reset')
"
```

### Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Failure threshold | 5 | Failures before circuit opens |
| Failure window | 60s | Window for counting failures |
| Open duration | 30s | How long circuit stays open |

---

## B5: Stripe Reconciliation Drift

### Symptoms

- Subscription status in Hub doesn't match Stripe
- Invoices missing or amount mismatch
- Usage records not synced

### Diagnosis

```bash
# Run reconciliation check (dry run)
docker exec hub-test-api python /app/hub/manage.py reconcile_stripe --dry-run

# Check specific tenant
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.billing.models import Subscription
from hub.apps.tenants.models import Tenant
tenant = Tenant.objects.get(slug='<tenant-slug>')
sub = Subscription.objects.filter(tenant=tenant).first()
print(f'Local: {sub.status}, Stripe ID: {sub.stripe_subscription_id}')
"
```

### Resolution

1. **Dry run first**: `reconcile_stripe --dry-run` to see diffs
2. **Fix drift**: `reconcile_stripe` (no --dry-run) to sync from Stripe
3. **Verify**: Check subscription status matches after sync

---

## B3: Refund Processing

### When to Use

- Customer requests refund for overcharge
- Duplicate charge detected
- Service credit needed

### Process

```bash
# Process refund (admin-only)
curl -X POST http://localhost:8000/api/v1/billing/refunds/ \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "<sub-id>",
    "amount": 1999,
    "reason": "Overcharge on March invoice",
    "currency": "USD"
  }'
```

### Validation Rules

- Amount must not exceed original charge
- Refund reason is required
- Only admin users can process refunds
- `BILLING.REFUND_PROCESSED` audit event created

### Rollback

Refunds are processed via Stripe and cannot be reversed. If issued in error, create a new charge instead.
