# Stripe Outage / Vendor Failure Runbook

## Impact
- Payments: new orders blocked, subscriptions cannot be created
- Connect KYB: onboarding links unavailable, webhook events delayed
- Tax: Stripe Tax calculations unavailable (falls back to manual)

## Detection
- `stripe_webhook_handler_error` log entries
- Stripe status page: https://status.stripe.com
- Prometheus: `stripe_api_error_total` counter spike

## Fallback
- Payments: queue pending orders; retry on Stripe recovery
- Connect: webhooks queued by Stripe for 72h; replay on recovery
- Tax: manual tax calculation using tenant tax_address

## Recovery
1. Confirm Stripe status page shows recovery
2. Replay missed webhooks via Stripe Dashboard
3. Retry queued pending orders
4. Notify affected tenants
