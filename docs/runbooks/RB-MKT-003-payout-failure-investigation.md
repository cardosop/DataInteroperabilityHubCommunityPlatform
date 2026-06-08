# RB-MKT-003 — Payout Failure Investigation

## Status

Stub created in Phase 271.0.5. Populate during Phase 271.2 (webhook handlers for `payout.*`), 271.3 (refund integration with `reverse_transfer=True`), and 271.4 (`Payout` cache + provider dashboard) as the underlying surfaces land. The stub is intentionally complete enough to triage with — the placeholder sections name the surface area each implementation phase will fill in.

## Purpose

Operational procedure for investigating a failed Stripe Connect payout — funds the platform attempted to settle to a provider's Connect balance did not arrive, OR a refund that should have reverse-transferred fee revenue did not complete on the Connect ledger. This runbook covers the post-KYB failure mode (the provider has a fully verified Connect Account but settlement still failed); the pre-KYB stuck-onboarding case is [`RB-MKT-001`](RB-MKT-001-stripe-connect-onboarding-failure.md).

## When this fires

- **Prometheus alert `ConnectPayoutFailureRate`** (defined in `monitoring/prometheus/alerts/connect.yml`, Phase 271.4) — fires when `>2%` of payouts in a 1h window reach the `payout.failed` terminal state.
- **Prometheus alert `ConnectWebhookFailureRate`** — fires when Connect webhook delivery error rate breaches the SLO; payout-related events are part of this denominator.
- **Provider support escalation** — provider sees `failed` status on their `ProviderRevenuePage` (Phase 271.4) and contacts Support.
- **Finance reconciliation flag** — Finance sees a mismatch between Hub-side `Order.provider_amount_cents` and the Stripe ledger entry; raised during month-end close.

## Scope

This runbook covers:

1. **Alert intake from `ConnectPayoutFailureRate`** — identify the impacted provider(s); separate "single-provider blast radius" from "platform-wide outage".
2. **Stripe-side payout state inspection** — populated at 271.4 (`GET /api/v1/billing/connect/payouts/`); cached fields `arrival_date`, `status`, `failure_code`, `failure_message`, `failure_balance_transaction`.
3. **Stripe Dashboard cross-check** — the Payouts tab on the Connect Account's Dashboard view is the source of truth. Hub-side `Payout` cache should match within the webhook-delivery latency budget.
4. **Refund-driven payout reversal diagnostics** — populated at 271.3 implementation; verify the `Refund` object on the original PaymentIntent has `reverse_transfer=true` + `refund_application_fee=true` AND that the corresponding `Transfer` reversal appears on the provider's Connect ledger.
5. **Identifying the failure mode** — common patterns:
   - **Bank account closed / invalid** (`failure_code=account_closed`, `bank_account_unusable`) — provider must re-add a bank account in their Express dashboard; manual intervention required.
   - **Insufficient Connect balance** (`failure_code=insufficient_funds`) — the provider has already withdrawn the funds; a refund or chargeback drove the balance negative; Stripe will recover via the next payout OR Hub absorbs (per D-271 Risks).
   - **Currency mismatch** (`failure_code=currency_disabled`) — multi-currency edge case (OQ271.2); provider's account doesn't support the platform's settlement currency.
   - **Stripe-platform-side rate limit / API failure** during the transfer reversal — webhook arrives late; reconcile via re-fetch from Stripe.
6. **Recovery actions** — populated at 271.4 implementation:
   - **Replay the cached state from Stripe** (`stripe.Payout.retrieve(payout_id, stripe_account=<connected_account_id>)`) and force-update the `Payout` row.
   - **Re-trigger the payout** for transient failures (Stripe will retry automatically for most cases — manual retry is rarely needed).
   - **Negative balance collection** — when the provider's balance went negative (post-refund), follow Finance's debit-collection workflow (out-of-scope for this runbook; see Finance's reconciliation SOP).
   - **Provider notification** — Support template "PAYOUT_FAILED_BANK_INVALID" / "PAYOUT_FAILED_GENERIC".
7. **Postmortem evidence pack** — Stripe Dashboard screenshots of the Payouts tab + the Transfer reversal ledger (for refund cases); audit-event trail showing `PAYOUT_FAILED` events; resolution notes.

## Decision tree

```
ConnectPayoutFailureRate alert fires
        │
        ▼
Identify impacted providers — single or platform-wide?
        │
        ▼
┌─── Platform-wide? ─────┐
│                        │
YES                      NO (single provider)
│                        │
▼                        ▼
Likely Stripe-platform   Inspect provider's Connect Account state +
outage or our            payout failure_code. Match against the
StripeCircuitBreaker     "Recovery actions matrix" below.
opened. Check Stripe
status page; check                     │
StripeCircuitBreaker                   ▼
state via metric                Single-provider fix; loop closes when
`stripe_circuit_breaker_       `payout.paid` or replacement payout
state{service="connect"}`.      arrives.
Escalate per Phase 117
RB-AUTH-* runbook.
```

## Forensic queries (Django shell)

```python
# Populated at 271.2+ implementation. Placeholder shapes:
# - Payout.objects.filter(tenant_id=<uuid>, status="failed").order_by("-created_at")[:20]
# - StripeWebhookEvent.objects.filter(event_type__startswith="payout.").order_by("-created_at")[:20]
# - PaymentTransaction.objects.filter(kind="REFUND", transfer_reversed=False, created_at__gte=<recent>)
#   → refunds where the Connect transfer reversal hasn't completed yet
# - audit_events_total filter: action__in=("PAYOUT_FAILED", "PAYOUT_RETRIED", "TRANSFER_REVERSED")
```

## Recovery actions matrix

| `failure_code` | Likely cause | Recovery |
|---|---|---|
| `account_closed`, `bank_account_unusable` | Provider's bank account no longer accepts deposits | Support contacts provider → provider updates bank account in Express Dashboard → next payout retries automatically |
| `insufficient_funds` | Negative Connect balance (refund / chargeback exceeded next payout) | Finance debit-collection workflow; do NOT auto-retry (would just fail again) |
| `currency_disabled` | Multi-currency mismatch (OQ271.2) | Convert payout to provider's account currency manually OR escalate to Stripe Support |
| `debit_not_authorized` | Provider revoked authorisation | Re-trigger onboarding link (`POST /api/v1/billing/connect/onboarding-link/`); provider must re-authorise debits |
| `expired_card` (rare for Connect) | Card associated with old verification expired | Re-trigger onboarding; provider re-uploads card |
| `bank_account_restricted` | Compliance / regulatory restriction on the bank account | Escalate to Legal; this is rarely user-fixable |
| Webhook-handler error logged (`tenant_resolution_failed`) | Connect webhook arrived before `ConnectAccount` row persisted (race condition; D-271.3 fallback) | Re-process via management command (Phase 271.2 will define `replay_stripe_webhook <event_id>`) |

## Refund-driven payout-reversal diagnostics

When a refund on a destination charge triggers `stripe.Refund.create(reverse_transfer=True, refund_application_fee=True)`:

1. Verify the original PaymentIntent had `transfer_data.destination` set (Phase 271.3).
2. Verify the `Refund.charge` matches the original `PaymentIntent.latest_charge`.
3. On the provider's Connect ledger, a `Transfer` with negative amount should appear (the reversal).
4. The `application_fee_amount` reversal should appear as a credit on the platform's balance.
5. If any of (3) or (4) is missing, Stripe's processing is incomplete — wait for `transfer.reversed` webhook OR file a Stripe Connect support ticket.

## Related

- **Spec**: [`stripe-connect-mvp/spec.md`](../../openspec/changes/preprod01/specs/stripe-connect-mvp/spec.md) — `Refund Reverses Application Fee`, `Payout Settlement and Provider Dashboard`, `Connect Observability`.
- **Design**: [`design.md` — Phase 271](../../openspec/changes/preprod01/design.md) — D-271.2 (destination charges + refund reverse_transfer), D-271 Risks (negative-balance handling).
- **RACI**: [`docs/raci/stripe-connect-mvp.md`](../raci/stripe-connect-mvp.md) — Finance is ACCOUNTABLE for the platform-fee accounting; SRE is CONSULTED on alerting thresholds.
- **Code (populate at implementation time)**:
  - `hub/apps/billing/views.py` — `payout.*` + `transfer.*` webhook handlers (271.2).
  - `hub/apps/billing/models.py` — `Payout` cache model (271.4).
  - `hub/apps/marketplace/views.py` — refund endpoint with `reverse_transfer=True` (271.3.5).
  - `frontend/src/features/.../ProviderRevenuePage.tsx` — provider-side failure visibility (271.4).
- **Alerts**: `monitoring/prometheus/alerts/connect.yml` — `ConnectPayoutFailureRate`, `ConnectWebhookFailureRate`.
- **Dashboard**: `monitoring/grafana/dashboards/connect-onboarding-funnel.json` — payout-failure panel.
- **Cross-runbooks**: [`RB-MKT-001-stripe-connect-onboarding-failure.md`](RB-MKT-001-stripe-connect-onboarding-failure.md) — pre-KYB stuck path; [`RB-MKT-002-refund-discrepancy.md`](RB-MKT-002-refund-discrepancy.md) — refund vs payment reconciliation (Phase 270.A); [`RB-AUTH-004-internal-api-key-rotation.md`](RB-AUTH-004-internal-api-key-rotation.md) — Stripe Connect webhook secret rotation cadence (Phase 270.C.3).

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
