# RB-MKT-002 — Refund Discrepancy Investigation

## Status

Stub created in Phase 270.0. Populate during Phase 270.A implementation.

## Purpose

Operational procedure for investigating discrepancies between Stripe-side
refund state (`charge.refunded` events / Stripe Dashboard) and the
hub-side `PaymentTransaction` / `Order` state introduced by the
Phase 270.A seller-initiated refund endpoint (D-270.4).

## Scope

- Alert intake from the `MarketplaceOrderRefundMismatch` Prometheus alert
- `PaymentTransaction.idempotency_key` deduplication contract
  (`f"{order_id}:refund:{amount_cents}"`) — duplicate POST vs.
  Stripe-side `stripe_refund_id` dedup paths
- Reconciling partial-refund pro-rata math (Phase 270.A vs. Phase 271
  Connect `reverse_transfer=True` + `refund_application_fee=True`)
- Webhook re-delivery: replay vs. idempotent skip; how to identify a
  webhook that arrived BEFORE the seller-initiated refund response
- Forensic queries:
  - `PaymentTransaction.objects.filter(order_id=..., kind="REFUND")`
  - Stripe Dashboard cross-check on `stripe_refund_id`
  - Audit-event search for `PAYMENT_REFUNDED` / `PAYMENT_REFUND_FAILED`
- Recovery actions:
  - Manual reconciliation via Django shell (re-emit webhook payload)
  - Roll forward vs. compensate with a counter-charge
  - Customer communication template
- Postmortem evidence pack (Stripe Dashboard screenshots, audit-event
  trail, idempotency-key collision log)

## Related

- Spec: [`marketplace-tax-compliance-deltas/spec.md`](../../openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md) §
  *Seller-Initiated Refund Endpoint*
- Design: [`design.md#decision-d-2704`](../../openspec/changes/preprod01/design.md) (D-270.4)
- Code (populate at implementation time): `hub/apps/marketplace/views.py`
  (refund endpoint), `hub/apps/marketplace/webhook_views.py`
  (`charge.refunded` handler), `hub/apps/marketplace/models.py`
  (`PaymentTransaction.idempotency_key`)
- Alerts: `monitoring/prometheus/alerts/marketplace-compliance-deltas.yml`

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
