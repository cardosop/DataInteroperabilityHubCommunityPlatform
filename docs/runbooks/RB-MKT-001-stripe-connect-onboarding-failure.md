# RB-MKT-001 — Stripe Connect Onboarding Failure Investigation

## Status

Stub created in Phase 271.0.5. Populate during Phase 271.1, 271.2, and 271.5 implementation as the underlying surfaces land. The stub is intentionally complete enough to triage with — the placeholder sections name the surface area each implementation phase will fill in.

## Purpose

Operational procedure for investigating a tenant's Stripe Connect onboarding that has stalled, errored, or stuck in a KYB-pending state for >24h after the tenant clicked through the hosted onboarding link. This runbook is the operations-owned counterpart to D-271.5's deliberate "ops-owned, not auto-resolved" decision: KYB stuck states are rare enough that auto-retry doesn't change the outcome and obscures the real issue (missing document, mismatched address, rejected identity verification, etc.).

## When this fires

- **Prometheus alert `ConnectOnboardingStuck`** (defined in `monitoring/prometheus/alerts/connect.yml`, Phase 271.4) — fires when a `ConnectAccount` has `details_submitted=True AND charges_enabled=False` for >24h.
- **PLATFORM_ADMIN KYB review queue** (`GET /api/v1/admin/connect/review-queue/`, Phase 271.5) — Support agent surfaces an entry during routine triage; entry has lingered past the SLA threshold (24h soft, 72h hard).
- **Tenant support escalation** — provider calls Support saying "I completed Stripe onboarding but my listings still say I need to complete onboarding".

## Scope

This runbook covers:

1. **Listing publish flow** — tenant creates a marketplace listing via
   `POST /api/v1/marketplace/listings/`.  The publish gate validates:
   (a) ConnectAccount exists and `charges_enabled=True` (KYB gate, Phase 271.3),
   (b) compliance threshold met for the listing's asset, (c) listing content
   validation (title, description, pricing).  If any gate fails, the listing
   stays in `DRAFT` / `PENDING_REVIEW` rather than `PUBLISHED`.
2. **Alert intake from `ConnectOnboardingStuck`** — confirm the row in the KYB review queue; identify whether this is a soft-stuck (Stripe still working) or a hard-stuck (Stripe has rejected and is waiting on the tenant).
2. **`ConnectAccount` state inspection** — populated at 271.1.4 (`GET /api/v1/billing/connect/status/`); fields `charges_enabled`, `payouts_enabled`, `requirements.currently_due`, `requirements.eventually_due`, `requirements.past_due`, `requirements.disabled_reason`.
3. **Stripe Dashboard cross-check** — populated at 271.1 implementation; the Dashboard URL for the specific Connect Account is the source of truth. Requirements list on the Dashboard MUST match the cached `ConnectAccount.requirements_json` (Phase 271.2 webhook handlers keep this fresh).
4. **Webhook-handler diagnostics** — populated at 271.2; verify `account.updated` events were received recently; check `StripeWebhookEvent.processing_error` for tenant-resolution failures (the Phase 260 CC-3 fallback path).
5. **Identifying the blocker** — common patterns:
   - Missing document upload (Stripe's `currently_due` includes `individual.verification.document` or `business_profile.tax_id`).
   - Mismatched address between Hub-side `Tenant.tax_address` and Stripe's KYB capture.
   - Stripe rejected ID document (`requirements.disabled_reason=requirements.past_due` + a `verification.document.rejected_reason` field).
   - Bank account verification failed (micro-deposit timeout or wrong account number).
6. **Recovery actions** — populated at 271.5 implementation:
   - Re-trigger the onboarding link (`POST /api/v1/billing/connect/onboarding-link/`) so the tenant lands back in Stripe's hosted flow.
   - Contact the tenant via Support template (template stored in Support's CRM, not in repo).
   - Manual document upload via Stripe Dashboard if the tenant cannot self-serve (e.g. legacy enterprise customer with a dedicated CSM).
   - Mark the row as `ops_resolution_notes=<free text>` so the audit trail captures what unstuck it.
7. **Postmortem evidence pack** — Stripe Dashboard screenshots of the Requirements panel + the rejection reason; audit-event trail showing `CONNECT_ONBOARDING_LINK_ISSUED` + `account.updated` event timestamps; the resolution notes.

## Decision tree

```
ConnectOnboardingStuck alert fires
        │
        ▼
Look up ConnectAccount.requirements_json
        │
        ▼
┌─── currently_due is non-empty? ───┐
│                                    │
YES                                  NO
│                                    │
▼                                    ▼
Tenant has a document / field to    Stripe's KYB processing is the
provide. Re-trigger onboarding      bottleneck. Wait 4–12h for Stripe
link, contact tenant. Track in      to update; if no movement at 72h,
KYB queue.                          file a Stripe Connect support ticket
                                    with the Account ID.
        │                                    │
        ▼                                    ▼
   After tenant re-submits, the         Stripe responds via `account.updated`
   `account.updated` webhook fires      with a new requirements list; loop back
   and clears `currently_due`; the      to "currently_due is non-empty" check.
   KYB queue row auto-clears.
```

## Forensic queries (Django shell)

```python
# Populated at 271.1+ implementation. Placeholder shapes:
# - ConnectAccount.objects.get(tenant_id=<uuid>) → snapshot of cached state
# - StripeWebhookEvent.objects.filter(event_type__startswith="account.").order_by("-created_at")[:10]
# - audit_events_total filter: action__in=("CONNECT_ONBOARDING_LINK_ISSUED", "CONNECT_ACCOUNT_CREATED", "CONNECT_KYB_BLOCKED")
```

## Recovery actions matrix

| Symptom | Likely cause | Recovery |
|---|---|---|
| `currently_due` includes `individual.verification.document` | Tenant hasn't uploaded ID | Re-trigger onboarding link → contact tenant |
| `currently_due` includes `business_profile.tax_id` | Tax ID format invalid | Support template "TAX_ID_FORMAT" → tenant re-enters |
| `charges_enabled=False, payouts_enabled=False, currently_due=[]` | Stripe KYB processing pending | Wait 4–12h, escalate to Stripe at 72h |
| `requirements.disabled_reason=rejected.fraud` | Stripe fraud rejection | Escalate to Legal — KYB rejection is rarely reversible |
| `requirements.past_due` non-empty | Tenant missed Stripe's grace window | Re-trigger onboarding immediately; if not resolved in 24h, Connect Account is disabled |
| Webhook handler logged `tenant_resolution_failed` | Onboarding race condition (D-271.3 fallback fired) | Inspect the `metadata.tenant_id` on the Stripe object; manually associate the ConnectAccount row if metadata is intact |

## Related

- **Spec**: [`stripe-connect-mvp/spec.md`](../../openspec/changes/preprod01/specs/stripe-connect-mvp/spec.md) — `KYB Manual Review Process`, `Connect Webhook Tenant Resolution`, `Express Onboarding Flow`.
- **Design**: [`design.md` — Phase 271](../../openspec/changes/preprod01/design.md) — D-271.1 (Express type), D-271.3 (webhook tenant resolution), D-271.5 (ops-owned KYB review).
- **RACI**: [`docs/raci/stripe-connect-mvp.md`](../raci/stripe-connect-mvp.md) — Support is RESPONSIBLE for the manual KYB review workflow.
- **Code (populate at implementation time)**:
  - `hub/apps/billing/models.py` — `ConnectAccount` model (271.1).
  - `hub/apps/billing/views.py` — webhook handlers including `account.updated` (271.2).
  - `hub/apps/marketplace/models.py` — `Listing.clean()` KYB gate (271.3).
  - PLATFORM_ADMIN endpoint `GET /api/v1/admin/connect/review-queue/` (271.5).
- **Alerts**: `monitoring/prometheus/alerts/connect.yml` — `ConnectOnboardingStuck`, `ConnectKYBStaleQueue`.
- **Dashboard**: `monitoring/grafana/dashboards/connect-onboarding-funnel.json` — onboarding funnel panel + stuck-state count.
- **Cross-runbook**: [`RB-MKT-003-payout-failure-investigation.md`](RB-MKT-003-payout-failure-investigation.md) — the symmetric runbook for the post-KYB failure mode.

## Maintenance

- **Owner**: Billing Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
