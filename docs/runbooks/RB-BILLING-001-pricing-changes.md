# RB-BILLING-001 — Plan Pricing Changes & Stripe Reconciliation

**Date:** 2026-05-20
**Feature flags:** `baas_enabled` (Billing-as-a-Service GA)
**Audit events:** `PLAN_PRICE_CHANGED`, `RECONCILE_PRICE_FIX`, `RECONCILE_STATUS_FIX`, `PLAN_TIER_CHANGED`

## 1. Overview

This runbook covers the operational procedures for plan pricing changes and
Stripe reconciliation within the Meshant billing system. It addresses five
core operational workflows:

1. **Adding a new plan tier** — creating a new `TenantPlan` with Stripe Product/Price.
2. **Changing a plan price** — modifying `price_amount_cents` (>$1,000/mo requires two-person approval).
3. **Syncing plan metadata to Stripe** — ensuring Stripe-side Product/Price objects match local state.
4. **Backfilling Enterprise plan limits** — updating `limits_json` for existing Enterprise tenants.
5. **Monthly reconciliation** — verifying local ↔ Stripe consistency for all active paid subscriptions.

This runbook is the operations-owned complement to `PlanPriceChangeApproval`
(285.13.9.3) and `reconcile_stripe` (285.13.15.4).

## 2. When This Runbook Fires

- **Prometheus alert `PlanPricingDrift`** — `plan_price_drift_total` incremented within a 5-minute window. Defined in `monitoring/prometheus/alerts/billing.yml`.
- **Prometheus alert `ZeroPriceSubscription`** — a non-FREE tier upgrade recorded without a corresponding payment event.
- **Prometheus alert `StripeProductSyncMismatch`** — `stripe_product_sync_mismatch_total` incremented within 15 minutes.
- **Scheduled monthly reconciliation** — run by the `reconcile-stripe` CronJob on the 1st of each month.
- **Manual trigger** — operator-initiated price change, plan creation, or Stripe product audit.

## 3. Scope

This runbook covers:

1. **Adding a new plan tier** (§4) — Django shell procedure; Stripe Product + Price creation; `TierProfile` seeding; plan limit defaults.
2. **Changing a plan price** (§5) — `PlanPriceChangeApproval` workflow; two-person rule for >$1,000/mo changes; Stripe Price update; tenant communication.
3. **Syncing plan metadata to Stripe** (§6) — using `reconcile_stripe --fix` to push local → Stripe; using Stripe Dashboard to pull Stripe → local.
4. **Backfilling Enterprise plan limits** (§7) — updating `limits_json` for existing Enterprise tenants after a plan definition change.
5. **Rollback procedure** (§8) — reverting a price change; restoring previous `price_amount_cents`; Stripe Price rollback.
6. **Monthly reconciliation** (§9) — `reconcile_stripe` execution; interpreting output; handling drift; audit trail review.
7. **Tenant communication template** (§10) — email/Slack template for notifying tenants of upcoming price changes.

## 4. Adding a New Plan Tier

### 4.1 — Pre-flight checklist

- [ ] Plan name, slug, tier, category, and order are defined in the product spec.
- [ ] `limits_json` keys are all present in `TenantPlan.KNOWN_LIMIT_KEYS`.
- [ ] `price_amount_cents` and `price_currency` are finalised.
- [ ] `billing_interval` (`month` / `year`) is decided.
- [ ] `marketplace_take_rate_bps` is set (default 1500 = 15%).
- [ ] `TierProfile` headline, description, and feature highlights are drafted.
- [ ] If the plan is ML_AI category, confirm no BASE subscription already has a conflicting Stripe product.

### 4.2 — Create the plan in Django

```python
# python manage.py shell
from hub.apps.tenants.models import TenantPlan, TierProfile, PlanTier, PlanCategory

plan = TenantPlan.objects.create(
    name="Scale Plan",
    slug="scale",
    tier=PlanTier.SCALE,
    category=PlanCategory.BASE,
    order=40,  # FREE=0, STARTER=10, GROWTH=20, PRO=30, SCALE=40
    limits_json={
        "max_assets": 500,
        "max_datasets": 100,
        "max_contracts": 200,
        "max_webhooks": 50,
        "max_mesh_domains": 10,
        "max_users": 50,
        "max_marketplace_listings": 50,
        "max_marketplace_connections": 100,
        "max_marketplace_orders_per_month": 500,
        "max_virtual_datasets": 50,
        "max_scheduled_ingestions": 25,
        "max_scheduled_exports": 25,
        "max_api_calls_per_month": 500000,
        "max_compliance_runs_per_month": 500,
        "max_dq_runs_per_month": 500,
        "max_storage_gb": 500,
    },
    price_amount_cents=49900,   # $499.00/mo
    price_currency="usd",
    billing_interval="month",
    marketplace_take_rate_bps=1200,  # 12%
)
```

### 4.3 — Create the Stripe Product and Price

If Stripe is not auto-provisioned (the plan's `stripe_product_id` and `stripe_price_id` are null), create them manually or let `reconcile_stripe --fix` handle it:

```bash
python manage.py reconcile_stripe --fix
```

To create manually via the Django shell:

```python
import stripe
api_key = "sk_live_..."  # from AWS SM or env

product = stripe.Product.create(
    name=plan.name,
    metadata={"plan_slug": plan.slug, "plan_tier": plan.tier},
    api_key=api_key,
)
plan.stripe_product_id = product.id

price = stripe.Price.create(
    product=product.id,
    unit_amount=plan.price_amount_cents,
    currency=plan.price_currency,
    recurring={"interval": plan.billing_interval},
    metadata={"plan_slug": plan.slug},
    api_key=api_key,
)
plan.stripe_price_id = price.id
plan.save(update_fields=["stripe_product_id", "stripe_price_id"])
```

### 4.4 — Create the TierProfile

```python
TierProfile.objects.create(
    plan=plan,
    headline="For scaling data teams",
    description="Everything in Pro plus advanced orchestration, higher limits, and priority support.",
    feature_highlights=[
        "500 assets",
        "50 webhooks",
        "500k API calls/month",
        "Priority support",
    ],
    is_public=True,
    cta_text="Contact Sales",
)
```

### 4.5 — Post-creation validation

- [ ] `stripe_product_id` and `stripe_price_id` are non-null.
- [ ] Stripe Dashboard → Products → the new product has correct name, metadata, and price.
- [ ] TierProfile appears on the public pricing page.
- [ ] New tenant provisioning picks up the plan in the plan dropdown.
- [ ] Run `python manage.py reconcile_stripe --dry-run` to confirm no immediate drift.

## 5. Changing a Plan Price

### 5.1 — Determine if two-person approval is required

Two-person approval is required when `|new_price - old_price| > 100000` (i.e., >$1,000/mo delta). This is enforced in `PlanAdminViewSet.perform_update()`.

**Small change (≤$1,000/mo):** A single PLATFORM_ADMIN can update `price_amount_cents` directly via the admin API:

```bash
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/admin/plans/{plan_id}/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price_amount_cents": 59900, "reason": "Annual price adjustment per Q2 review"}'
```

**Large change (>$1,000/mo):** Two-person approval is required.

### 5.2 — Two-person approval workflow (>$1,000/mo)

#### Step 1: First PLATFORM_ADMIN creates a PlanPriceChangeApproval

```bash
curl -X POST https://api.stagingmeshant-internal.example.com/api/v1/admin/plan-price-change-approvals/ \
  -H "Authorization: Bearer $ADMIN1_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_plan_id": "<plan-uuid>",
    "old_price_cents": 49900,
    "new_price_cents": 79900,
    "reason": "Market repositioning: Scale tier price increase to align with Enterprise value prop. FLSC analysis attached in PRD-442."
  }'
```

#### Step 2: Second PLATFORM_ADMIN approves

```bash
curl -X POST https://api.stagingmeshant-internal.example.com/api/v1/admin/plan-price-change-approvals/{approval_id}/approve/ \
  -H "Authorization: Bearer $ADMIN2_TOKEN"
```

This triggers:
1. `PlanPriceChangeApproval.status` → `APPROVED`
2. `TenantPlan.price_amount_cents` → new value
3. Audit event: `PLAN_PRICE_CHANGED` with old/new cents and both approver IDs
4. Stripe Price is NOT automatically updated — see §5.3.

### 5.3 — Update the Stripe Price

After the local price is changed, the Stripe Price object must be updated to match. Stripe Price objects are immutable — you must create a NEW Stripe Price and archive the old one:

```python
import stripe
from django.conf import settings

api_key = settings.STRIPE_SECRET_KEY
plan = TenantPlan.objects.get(slug="scale")

# Create new Stripe Price with updated amount
new_price = stripe.Price.create(
    product=plan.stripe_product_id,
    unit_amount=plan.price_amount_cents,
    currency=plan.price_currency,
    recurring={"interval": plan.billing_interval},
    metadata={"plan_slug": plan.slug},
    api_key=api_key,
)

# Archive old price
old_price_id = plan.stripe_price_id
if old_price_id:
    stripe.Price.modify(old_price_id, active=False, api_key=api_key)

# Update local reference
plan.stripe_price_id = new_price.id
plan.save(update_fields=["stripe_price_id"])

print(f"Stripe Price updated: {old_price_id} → {new_price.id}")
```

**Important:** Existing subscriptions retain the old Stripe Price until they renew. Stripe does not automatically migrate subscriptions to the new Price. To migrate active subscriptions, use the Stripe Dashboard or the Stripe API to update each subscription's items.

### 5.4 — Post-change validation

- [ ] `TenantPlan.price_amount_cents` reflects the new value.
- [ ] `PlanPriceChangeApproval` row is in `APPROVED` status.
- [ ] `PLAN_PRICE_CHANGED` audit event emitted.
- [ ] New Stripe Price created with correct `unit_amount`.
- [ ] Old Stripe Price archived (`active=false`).
- [ ] `python manage.py reconcile_stripe --dry-run` shows zero price drift for this plan.
- [ ] Active subscriptions on the old price are flagged for migration.

## 6. Syncing Plan Metadata to Stripe

### 6.1 — Detect mismatches

```bash
# Dry-run report: shows all mismatches without modifying anything
python manage.py reconcile_stripe --dry-run
```

The command emits JSON lines. Key events to watch for:

| Event | Meaning |
|---|---|
| `price_drift` | Local `price_amount_cents` ≠ Stripe `unit_amount` |
| `product_mismatch` | Stripe Product `metadata.plan_slug` ≠ local `slug`, or Product `name` ≠ local `name` |
| `stripe_price_missing` | Local plan has `price_amount_cents > 0` but no `stripe_price_id` |
| `stripe_product_missing` | Local plan has `price_amount_cents > 0` but no `stripe_product_id` |

### 6.2 — Fix mismatches (local → Stripe)

```bash
# Auto-fix: updates Stripe-side to match local state
python manage.py reconcile_stripe --fix
```

The `--fix` flag performs these corrections automatically:
1. **Price drift (`stripe_higher` / `stripe_lower`):** Creates a new Stripe Price with the correct `unit_amount`, archives the old one, and updates `stripe_price_id` on the `TenantPlan`.
2. **Product name mismatch:** Updates `stripe.Product.modify(name=local_name)`.
3. **Metadata mismatch:** Updates `stripe.Product.modify(metadata={plan_slug: local_slug})`.
4. **Missing Stripe Price:** Creates a new Stripe Price from the local `price_amount_cents`.
5. **Missing Stripe Product:** Creates a new Stripe Product, then a Price under it.

Each fix emits a `RECONCILE_PRICE_FIX` audit event.

### 6.3 — Fix mismatches (Stripe → local)

When Stripe is the source of truth (e.g., price was updated in the Stripe Dashboard directly):

```python
# python manage.py shell
from hub.apps.tenants.models import TenantPlan
import stripe
from django.conf import settings

api_key = settings.STRIPE_SECRET_KEY

for plan in TenantPlan.objects.filter(price_amount_cents__gt=0, stripe_price_id__isnull=False):
    stripe_price = stripe.Price.retrieve(plan.stripe_price_id, api_key=api_key)
    stripe_amount = stripe_price.get("unit_amount", 0)
    if stripe_amount != plan.price_amount_cents:
        print(f"DRIFT: plan={plan.slug} local={plan.price_amount_cents} stripe={stripe_amount}")
        # To fix local → Stripe:
        plan.price_amount_cents = stripe_amount
        plan.save(update_fields=["price_amount_cents"])
```

## 7. Backfilling Enterprise Plan Limits

When an Enterprise plan's `limits_json` is updated (e.g., adding a new limit key or increasing an existing limit), existing Enterprise tenants on that plan must be evaluated for backfill.

### 7.1 — Identify tenants needing backfill

```sql
SELECT t.id, t.name, t.slug, tp.slug AS plan_slug, tp.limits_json
FROM tenants_tenant t
JOIN tenant_plans tp ON t.plan_id = tp.id
WHERE tp.tier = 'ENTERPRISE'
  AND t.status = 'ACTIVE'
ORDER BY t.name;
```

### 7.2 — Backfill procedure

Enterprise plan limits that are `null` (unlimited) do not require backfill — the absence of a limit key is equivalent to unlimited.

For new limit keys added to the Enterprise plan with a concrete value:

```python
# python manage.py shell
from hub.apps.tenants.models import Tenant, TenantPlan

enterprise_plan = TenantPlan.objects.get(slug="enterprise")
new_limits = enterprise_plan.limits_json

# Enterprise tenants with custom overrides may need manual review.
# Tenants without overrides inherit the plan defaults automatically
# at enforcement time (limit_registry reads plan.limits_json).
# No explicit backfill is needed unless the tenant has a
# tenant_limits_json override that shadows a new plan-level key.

for tenant in Tenant.objects.filter(plan=enterprise_plan, status="ACTIVE"):
    tenant_limits = tenant.tenant_limits_json or {}
    plan_limits = enterprise_plan.limits_json or {}

    # Identify new plan-level keys not present in tenant overrides
    new_keys = set(plan_limits.keys()) - set(tenant_limits.keys())
    if new_keys:
        print(f"Tenant {tenant.slug}: new plan limits to review: {new_keys}")
        # Tenant automatically gets the plan-level limit for un-overridden keys.
        # No action needed unless the tenant requires a custom value.
```

### 7.3 — Enterprise custom limits

Some Enterprise tenants have custom `tenant_limits_json` overrides negotiated during sales. Before backfilling:

- [ ] Review the tenant's signed order form for custom limit agreements.
- [ ] Compare `tenant_limits_json` against the updated `plan.limits_json`.
- [ ] If the plan limit was increased but the tenant has a custom *lower* limit: the tenant's override takes precedence — no action needed.
- [ ] If the plan limit was increased and the tenant has no override: the tenant automatically benefits from the new plan limit — no action needed.
- [ ] If the plan limit was decreased (rare): contact the tenant's CSM before applying.

## 8. Rollback Procedure

### 8.1 — Roll back a price change

If a price change needs to be reverted:

```python
# python manage.py shell
from hub.apps.tenants.models import TenantPlan
import stripe
from django.conf import settings

api_key = settings.STRIPE_SECRET_KEY
plan = TenantPlan.objects.get(slug="scale")

# Restore the old price
old_price_cents = 49900  # The previous value (documented in PlanPriceChangeApproval)
plan.price_amount_cents = old_price_cents
plan.save(update_fields=["price_amount_cents"])

# Revert Stripe Price
new_price = stripe.Price.create(
    product=plan.stripe_product_id,
    unit_amount=old_price_cents,
    currency=plan.price_currency,
    recurring={"interval": plan.billing_interval},
    metadata={"plan_slug": plan.slug},
    api_key=api_key,
)
old_stripe_price = plan.stripe_price_id
plan.stripe_price_id = new_price.id
plan.save(update_fields=["stripe_price_id"])
stripe.Price.modify(old_stripe_price, active=False, api_key=api_key)

print(f"Rollback complete: {plan.slug} price restored to {old_price_cents}c")
```

### 8.2 — Create a reversal approval record

For audit trail completeness, create a new `PlanPriceChangeApproval` documenting the reversal:

```python
from hub.apps.tenants.models import PlanPriceChangeApproval

PlanPriceChangeApproval.objects.create(
    tenant_plan=plan,
    old_price_cents=new_price_cents,   # The price being reverted
    new_price_cents=old_price_cents,   # The restored price
    status="APPROVED",
    requested_by=requesting_admin,
    approved_by=approving_admin,
    reason="Rollback: <reason for reversal, e.g., 'customer complaint', 'pricing error'>",
)
```

## 9. Monthly Reconciliation

### 9.1 — Scheduled execution

The `reconcile-stripe` CronJob runs on the 1st of each month at 06:00 UTC:

```yaml
# In deploy/helm/templates/cronjob-reconcile-stripe.yaml
schedule: "0 6 1 * *"
```

It executes:
```bash
python manage.py reconcile_stripe  # status reconciliation
```

### 9.2 — Manual execution

```bash
# Dry-run: report only, no changes
python manage.py reconcile_stripe --dry-run

# Full reconciliation with auto-fix for status drift
python manage.py reconcile_stripe

# Full reconciliation with auto-fix for status + price drift
python manage.py reconcile_stripe --fix

# Large tenant bases: use batching
python manage.py reconcile_stripe --batch-size 25
```

### 9.3 — Interpreting output

The command emits structured JSON to stdout. Key metrics:

| Output key | Meaning |
|---|---|
| `reconcile_start` | Total subscriptions to check; `dry_run` flag |
| `drift_detected` | Status mismatch (local vs Stripe) |
| `price_drift` | Price mismatch — `local_cents` vs `stripe_unit_amount` |
| `product_mismatch` | Product metadata mismatch |
| `zero_price_on_paid_plan` | Paid plan with Stripe-side unit_amount=0 on active subscription |
| `subscription_price_stale` | Subscription uses an older Stripe Price than the plan's current cached price |
| `stripe_not_found` | Subscription deleted on Stripe side |
| `stripe_error` | Transient Stripe API error |
| `reconcile_complete` | Summary: `checked`, `drifted`, `errors`, `price_drifts_fixed`, `zero_price_on_paid_plan`, `stale_subscription_prices` |

### 9.4 — Post-reconciliation audit

After each monthly reconciliation:

- [ ] `reconcile_complete` shows `errors=0`.
- [ ] All `drift_detected` entries have been resolved (re-run until `drifted=0`).
- [ ] All `price_drift` entries have been fixed or escalated.
- [ ] `RECONCILE_STATUS_FIX` and `RECONCILE_PRICE_FIX` audit events are reviewed.
- [ ] Zero `stripe_not_found` events for subscriptions expected to be active.
- [ ] Grafana "Billing — Upgrade Funnel" dashboard shows expected monthly trends.

### 9.5 — Escalation thresholds

| Condition | Action |
|---|---|
| `errors > 10%` of total | Escalate to billing on-call — possible Stripe API degradation |
| `price_drifts > 0` after `--fix` | Manual investigation — auto-fix could not resolve all mismatches |
| `stripe_not_found > 5` | Review for accidental subscription deletion on Stripe side |
| Reconciliation not completed by 12:00 UTC on the 1st | Escalate to Platform Lead |

## 10. Tenant Communication Template

### 10.1 — Price increase notification (>$1,000/mo delta)

**Subject:** Upcoming change to your Meshant plan pricing

```
Hi {tenant_contact_name},

We're writing to let you know about an upcoming change to your
{plan_name} plan pricing.

Effective {effective_date, 30+ days from now}, your monthly
subscription will change from {old_price_formatted} to
{new_price_formatted} per month.

Why this change:
{one-paragraph business justification from PlanPriceChangeApproval.reason}

What this means for you:
- Your current limits and features remain unchanged.
- The new price takes effect on your next billing cycle after {effective_date}.
- No action is required on your end — your subscription will update automatically.

If you have questions, please reply to this email or contact your
account manager at {cs_contact_email}.

Thank you,
The Meshant Team
```

### 10.2 — New plan tier available

**Subject:** New {plan_name} plan now available on Meshant

```
Hi {tenant_contact_name},

We're excited to announce the {plan_name} plan is now available on Meshant.

What's included:
{bullet list of key features and limits}

Pricing: {price_formatted}/month

You can upgrade in your workspace settings at:
https://{tenant_slug}meshant-internal.example.com/settings/billing

If you'd like a personalised walkthrough, reply to this email and
we'll schedule a call.

Thank you,
The Meshant Team
```

### 10.3 — Enterprise limit backfill notification

**Subject:** Your Enterprise plan limits have been updated

```
Hi {tenant_contact_name},

We've updated the default limits on your Enterprise plan to reflect
our latest platform capabilities.

Changes:
{bullet list: "max_assets: 1000 → 2000", etc.}

These changes are effective immediately and require no action on
your end. Your custom limits (if any) remain unchanged.

If you have any questions, please contact your account manager.

Thank you,
The Meshant Team
```

## 11. Forensic Queries (Django Shell)

### 11.1 — Check all active paid subscriptions and their Stripe state

```python
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import TenantPlan

active_paid = Subscription.objects.filter(
    status=SubscriptionStatus.ACTIVE,
).exclude(
    plan__price_amount_cents=0,
).select_related("tenant", "plan")

for sub in active_paid:
    print(
        f"tenant={sub.tenant.slug} "
        f"plan={sub.plan.slug} "
        f"local_cents={sub.plan.price_amount_cents} "
        f"stripe_sub_id={sub.stripe_subscription_id} "
        f"stripe_price_id={sub.plan.stripe_price_id}"
    )
```

### 11.2 — Find all price change approvals

```python
from hub.apps.tenants.models import PlanPriceChangeApproval

for approval in PlanPriceChangeApproval.objects.select_related(
    "tenant_plan", "requested_by", "approved_by"
).order_by("-created_at")[:20]:
    print(
        f"plan={approval.tenant_plan.slug} "
        f"{approval.old_price_cents}→{approval.new_price_cents} "
        f"status={approval.status} "
        f"by={approval.requested_by}"
    )
```

### 11.3 — Verify Stripe-side unit_amount for all paid plans

```python
import stripe
from django.conf import settings

api_key = settings.STRIPE_SECRET_KEY
from hub.apps.tenants.models import TenantPlan

for plan in TenantPlan.objects.filter(
    price_amount_cents__gt=0, stripe_price_id__isnull=False
):
    try:
        sp = stripe.Price.retrieve(plan.stripe_price_id, api_key=api_key)
        match = "OK" if sp.unit_amount == plan.price_amount_cents else "DRIFT"
        print(
            f"{match}: plan={plan.slug} "
            f"local={plan.price_amount_cents} "
            f"stripe={sp.unit_amount} "
            f"currency={sp.currency}"
        )
    except Exception as e:
        print(f"ERROR: plan={plan.slug} stripe_price_id={plan.stripe_price_id} error={e}")
```

### 11.4 — Find subscriptions using a stale Stripe Price

```python
# python manage.py shell
import stripe
from django.conf import settings
from hub.apps.billing.models import Subscription, SubscriptionStatus

api_key = settings.STRIPE_SECRET_KEY

for sub in Subscription.objects.filter(
    status__in=(
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.TRIAL,
        SubscriptionStatus.PAST_DUE,
    ),
    plan__price_amount_cents__gt=0,
    stripe_subscription_id__isnull=False,
).exclude(stripe_subscription_id=""):
    stripe_sub = stripe.Subscription.retrieve(
        sub.stripe_subscription_id, api_key=api_key,
    )
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        sub_price_id = items[0].get("price", {}).get("id")
        plan_price_id = sub.plan.stripe_price_id
        if sub_price_id != plan_price_id:
            print(
                f"STALE: tenant={sub.tenant.slug} "
                f"plan={sub.plan.slug} "
                f"sub_price={sub_price_id} "
                f"plan_price={plan_price_id}"
            )
```

### 11.5 — Audit trail for pricing events

```
GET /api/v1/audit/events/?action__in=PLAN_PRICE_CHANGED,RECONCILE_PRICE_FIX,RECONCILE_STATUS_FIX&since=30d
```

## 12. Related

- **Spec**: [`preprod01/specs/billing-pricing/spec.md`](../../openspec/changes/preprod01/specs/billing-pricing/spec.md) — Plan tier expansion, pricing fields, two-person approval.
- **Design**: [`design.md`](../../openspec/changes/preprod01/design.md) — 285.13 (Billing & Pricing Expansion).
- **Code**:
  - `hub/apps/tenants/models.py` — `TenantPlan`, `PlanPriceChangeApproval` (285.13.9.3)
  - `hub/apps/billing/services.py` — `SubscriptionService`, `StripeCircuitBreaker`
  - `hub/apps/billing/management/commands/reconcile_stripe.py` — reconciliation command (285.13.15.4)
  - `hub/apps/billing/metrics.py` — billing metrics (285.13.15.3)
  - `hub/apps/billing/tests/test_metrics_285_13_15.py` — unit tests for metrics, reconcile command, service wiring
- **Alerts**: `monitoring/prometheus/alerts/billing.yml` — `PlanPricingDrift`, `ZeroPriceSubscription`, `StripeProductSyncMismatch`, `HighPlanUpgradeFailureRate`, `PaymentFailureSpike`
- **Dashboard**: `monitoring/grafana/dashboards/billing-upgrade-funnel.json` — upgrade funnel, price drift, payment failure, zero-price, stale-price panels.
- **Cross-runbook**:
  - [`RB-MKT-001-stripe-connect-onboarding-failure.md`](RB-MKT-001-stripe-connect-onboarding-failure.md) — Stripe Connect onboarding triage.
  - [`RB-MKT-002-refund-discrepancy.md`](RB-MKT-002-refund-discrepancy.md) — refund reconciliation.
  - [`vendor-failure-stripe.md`](vendor-failure-stripe.md) — Stripe vendor outage procedures.

## 13. Maintenance

- **Owner**: Billing Team
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
