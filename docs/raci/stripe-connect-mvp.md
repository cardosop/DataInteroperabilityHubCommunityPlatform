# RACI matrix — Phase 271 Stripe Connect MVP (Provider Payouts)

**Phase**: 271.0.4 / D-271
**Status**: Authoritative
**Owners**: Marketplace EM, Phase 271 Driver
**Capability spec**: [`openspec/changes/preprod01/specs/stripe-connect-mvp/spec.md`](../../openspec/changes/preprod01/specs/stripe-connect-mvp/spec.md)
**Design**: [`openspec/changes/preprod01/design.md` — Phase 271](../../openspec/changes/preprod01/design.md) (D-271.1 through D-271.5)

## Purpose

Stripe Connect MVP introduces revenue settlement to providers, which crosses Engineering, Product, Security, Legal (KYB liability), Finance (fee accounting, reconciliation), Support (provider onboarding queries), and SRE (webhook reliability, Stripe API circuit breakers). This matrix front-loads the conversation: every phase × stakeholder cell is one of R / A / C / I:

- **R — Responsible**: does the work.
- **A — Accountable**: signs off on completion (single accountable owner per row).
- **C — Consulted**: input solicited before decisions are made.
- **I — Informed**: kept aware; no decision authority.

## Stakeholders

| Code | Stakeholder |
|---|---|
| **Eng** | Marketplace Engineering team (backend + frontend + SDK) |
| **EM** | Marketplace Engineering Manager |
| **PM** | Product Manager |
| **Sec** | Security Engineering |
| **Legal** | Legal Counsel (KYB liability, Stripe Connect Services Agreement review) |
| **Finance** | Finance / Controller (fee accounting, refund reconciliation, 1099-K / tax forms) |
| **Support** | Customer Support / Customer Success (provider onboarding queries, KYB-stuck escalations) |
| **SRE** | Site Reliability Engineering (webhook reliability, payout monitoring, circuit-breaker tuning) |
| **Director** | Engineering Director (escalation path) |

## Matrix

| Phase / sub-phase | Eng | EM | PM | Sec | Legal | Finance | Support | SRE | Director |
|---|---|---|---|---|---|---|---|---|---|
| **271.0** OpenSpec / RACI / runbooks / Stripe partner-tier confirmation | R | A | C | I | **C** | C | I | I | I |
| **271.1** `ConnectAccount` model + onboarding endpoint | R | A | C | C | C | I | I | I | I |
| **271.2** Connect webhook handlers + tenant resolution | R | A | I | **C** | I | C | I | **C** | I |
| **271.3** Revenue split + KYB gate + refund integration | R | A | C | C | **C** | **A** | C | C | I |
| **271.4** Payout cache + provider dashboard + CLI/SDK | R | A | C | I | I | C | C | C | I |
| **271.5** KYB review queue + manual ops process | R | A | C | C | C | I | **R** | I | C |
| **271.6** Gradual rollout (per-tenant flag, 30-day window) | R | A | C | I | C | C | C | C | C |

## Stakeholder responsibilities by sub-phase

### Eng (Marketplace Engineering)
- **All sub-phases** RESPONSIBLE for implementation.
- **271.1** owns the `ConnectAccount` model + RLS policy + onboarding endpoint; coordinates with Sec on the Stripe-account-id surface area (the field is sensitive — leaking it gives an attacker the address of a Stripe object they could probe).
- **271.2** owns the webhook handlers including the `_resolve_tenant_for_connect_event()` helper that closes the Phase 260 CC-3 cross-tenant resolution requirement.
- **271.3** owns the destination-charge wiring (`application_fee_amount` + `transfer_data.destination`); pairs with Finance on the 10% fee math + Phase 270.A refund integration (`reverse_transfer=True` + `refund_application_fee=True`).
- **271.5** implements the admin queue endpoint; Support owns the operational workflow on top of it.

### EM (Engineering Manager)
- **All sub-phases** ACCOUNTABLE — signs off on each sub-phase PR before merge to staging.
- **271.6** ACCOUNTABLE for the rollout sequence (new-tenant default-on; existing-tenant 30-day notice + opt-out per D-271.4).

### PM (Product Manager)
- **271.0** consulted on the requirement scope (which of the 11 ADDED Requirements to include in MVP vs defer).
- **271.3** consulted on the platform-fee default (`MARKETPLACE_PLATFORM_FEE_BPS=1000` = 10%); pricing is a Product decision.
- **271.4** consulted on the provider-dashboard UX (`ProviderRevenuePage.tsx` information architecture).
- **271.5** consulted on the operational workflow signage (banners, status badges, support-ticket templates).
- **271.6** consulted on the rollout cadence (which tenant cohorts come online when).

### Sec (Security Engineering)
- **271.1** CONSULTED on the `ConnectAccount.stripe_account_id` field handling (PII-adjacent — Stripe-account-id is a stable identifier that lets an attacker enumerate Stripe objects).
- **271.2** CONSULTED on webhook signature verification (`STRIPE_CONNECT_WEBHOOK_SECRET` separate from `STRIPE_WEBHOOK_SECRET`; secret rotation on the same 90-day cadence as INTERNAL_API_KEY per Phase 270.C.3).
- **271.3** consulted on the KYB gate: must not leak the existence of another tenant's `ConnectAccount` (cross-tenant existence-leak check, same shape as Phase 250.5.C).
- **271.5** consulted on the admin queue endpoint authorisation (PLATFORM_ADMIN only; admin queue must not surface raw Stripe-account-ids to non-admin operators).

### Legal
- **271.0** CONSULTED on Stripe Connect Services Agreement — Express type means Stripe holds KYB liability but Hub is still merchant-of-record under destination-charge model (D-271.2). Confirm clean of conflicts with Hub's existing ToS.
- **271.3** CONSULTED on the platform-fee disclosure on the consumer-facing receipt + provider's payout statement; tax-relevant.
- **271.5** consulted on the KYB review queue retention policy (we hold the onboarding diagnostics for X days post-resolution).
- **271.6** consulted on the 30-day opt-out notice content for existing tenants.

### Finance / Controller
- **271.0** CONSULTED on the fee accounting model (destination charge with `application_fee_amount` produces a single line on the Stripe ledger; reconciliation cadence and account mapping).
- **271.3** ACCOUNTABLE for the platform-fee accounting contract: fee revenue, refund reversals, partial-refund pro-rata math; signs off on the `Order.platform_fee_cents` + `Order.provider_amount_cents` schema before migration.
- **271.4** consulted on the provider dashboard payout reconciliation; the `Payout` cache must round-trip to Finance's accounting system.
- **271.6** consulted on the rollout cadence's impact on month-end close (avoid first-of-month rollouts that fragment fee-revenue lines).

### Support
- **271.3** CONSULTED on the KYB-gate user messaging (the inline banner copy on `ListingPublishPage` — provider sees this when they hit publish without completing onboarding).
- **271.4** consulted on the `ConnectStatusBadge` semantics (pending / verified / restricted / disabled — Support agents need a shared vocabulary).
- **271.5** RESPONSIBLE for the manual KYB review process: ops follows RB-MKT-001 to inspect Stripe Dashboard, identify required documents, contact the tenant, re-trigger the onboarding link.
- **271.6** consulted on the 30-day opt-out comms (Support fields the inbound questions).

### SRE
- **271.2** CONSULTED on the Connect webhook reliability target (same SLA as the main Stripe webhook; circuit breaker covers Connect calls per Phase 117 D-117.X).
- **271.3** consulted on the destination-charge latency budget (extra Stripe API call vs the existing single PaymentIntent).
- **271.4** consulted on the `Payout` cache freshness contract (how stale can the cache be before the provider dashboard misleads).
- **271.5** consulted on the admin-queue alerting threshold (`ConnectKYBStaleQueue` Prometheus alert from `monitoring/prometheus/alerts/connect.yml`).
- **271.6** consulted on the rollout monitoring (`ConnectOnboardingStuck`, `ConnectWebhookTenantUnresolved`, `ConnectWebhookFailureRate` alerts).

### Director
- **271.5** consulted on the operations-owned KYB-review contract (the trade-off the spec settles in D-271.5).
- **271.6** consulted on the rollout sequence — the "new-tenant default-on; existing-tenant 30-day opt-out" contract sets a precedent for future opt-in features.

## Open dependencies (OQs feeding this RACI)

- **OQ271.1** Stripe Connect partnership tier confirmation — Legal + Finance + Eng triad consultation BEFORE week-1 271.1 kickoff. If Stripe requires a "Connect Platform" tier with different fees, that re-opens the Finance accountability on 271.3.
- **OQ271.2** Multi-currency provider accounts — Product + Finance consultation; the design recommends yes (Express handles automatically) but the user-docs surface needs Product sign-off.

## Sign-offs

| Sub-phase | EM | PM | Finance | Sec | Legal | Date |
|---|---|---|---|---|---|---|
| 271.0 (kickoff) | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | — |
| 271.1 (model + onboarding) | _pending_ | _pending_ | n/a | _pending_ | _pending_ | — |
| 271.2 (webhooks) | _pending_ | n/a | _pending_ | _pending_ | n/a | — |
| 271.3 (revenue split + KYB gate) | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | — |
| 271.4 (payout dashboard) | _pending_ | _pending_ | _pending_ | n/a | n/a | — |
| 271.5 (KYB review queue) | _pending_ | _pending_ | n/a | _pending_ | _pending_ | — |
| 271.6 (rollout) | _pending_ | _pending_ | _pending_ | n/a | _pending_ | — |

Sign-offs are recorded inline in this file as each sub-phase closes (mirror of `asset-creation-hardening-signoffs.md` pattern from Phase 250).

## Cross-references

- Spec: [`openspec/changes/preprod01/specs/stripe-connect-mvp/spec.md`](../../openspec/changes/preprod01/specs/stripe-connect-mvp/spec.md) — 11 ADDED Requirements.
- Design: [`openspec/changes/preprod01/design.md` — Phase 271](../../openspec/changes/preprod01/design.md) — D-271.1 (Express type), D-271.2 (destination charges), D-271.3 (webhook tenant resolution), D-271.4 (two-level rollback), D-271.5 (ops-owned KYB review).
- Tasks: [`openspec/changes/preprod01/tasks.md` — 271.0 through 271.6](../../openspec/changes/preprod01/tasks.md).
- Runbooks: [`RB-MKT-001-stripe-connect-onboarding-failure.md`](../runbooks/RB-MKT-001-stripe-connect-onboarding-failure.md), [`RB-MKT-003-payout-failure-investigation.md`](../runbooks/RB-MKT-003-payout-failure-investigation.md), [`RB-MKT-002-refund-discrepancy.md`](../runbooks/RB-MKT-002-refund-discrepancy.md) (cross-referenced from Phase 270.A refund flow).
- Phase 270 cross-references: 270.A.1 refund endpoint (Phase 271.3.5 extends it with `reverse_transfer=True`); 270.C.3 INTERNAL_API_KEY rotation (Phase 271.2.4 adopts the same 90-day cadence for `STRIPE_CONNECT_WEBHOOK_SECRET`).
