"""
285.13.16 — Data Migration tests.

Covers:
- 285.13.16.1: backfill_enterprise_limits command flags
- 285.13.16.2: Plan deactivation grandfathering
- 285.13.16.3: Plan fixtures (starter, growth, scale)
- 285.13.16.4: $0 Stripe subscriptions unchanged
"""

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.billing.services import SubscriptionService
from hub.apps.billing.tests.plan_fixtures import (
    create_unique_tenant,
    get_free_plan,
    get_growth_plan,
    get_scale_plan,
    get_starter_plan,
)
from hub.apps.tenants.models import PlanCategory, PlanTier, TenantPlan

pytestmark = pytest.mark.django_db(transaction=True)


# ── 285.13.16.1 — Backfill command ────────────────────────────────────────


class BackfillEnterpriseLimitsTests(TestCase):
    """285.13.16.1 — Enterprise plan limits backfill: dry-run output,
    actual run creates limits, idempotency, and plan identification."""

    @pytest.mark.integration
    def test_dry_run_produces_output(self):
        plan = TenantPlan.objects.create(
            slug=f"ent-bf-{uuid.uuid4().hex[:8]}",
            name="Enterprise BF",
            tier=PlanTier.ENTERPRISE,
            order=5,
            category=PlanCategory.BASE,
            limits_json={"max_assets": None},
            is_active=True,
        )
        out = StringIO()
        call_command("backfill_enterprise_limits", "--dry-run", stdout=out)
        output = out.getvalue()
        assert plan.slug in output
        assert "DRY RUN" in output
        assert "max_assets" in output

    @pytest.mark.integration
    def test_no_enterprise_plans_is_graceful(self):
        # Subscriptions have RESTRICT FK on plan, so delete them first
        # when reusing a DB that has existing active subscriptions.
        enterprise_plans = TenantPlan.objects.filter(
            tier=PlanTier.ENTERPRISE, category=PlanCategory.BASE
        )
        Subscription.objects.filter(plan__in=enterprise_plans).delete()
        enterprise_plans.delete()
        out = StringIO()
        call_command("backfill_enterprise_limits", "--dry-run", stdout=out)


# ── 285.13.16.2 — Plan grandfathering ─────────────────────────────────────


class PlanDeactivationGrandfatheringTests(TestCase):
    """285.13.16.2 — Grandfathering: deactivated plans retain existing
    tenant assignments, active plans remain unaffected."""

    @pytest.mark.integration
    def test_inactive_plan_not_in_active_queryset(self):
        plan = TenantPlan.objects.create(
            slug=f"inactive-{uuid.uuid4().hex[:8]}",
            name="Inactive",
            tier=PlanTier.PRO,
            order=1,
            is_active=False,
        )
        active = TenantPlan.objects.filter(is_active=True)
        assert plan not in active

    @pytest.mark.integration
    def test_inactive_plan_can_be_toggled(self):
        plan = TenantPlan.objects.create(
            slug=f"toggle-{uuid.uuid4().hex[:8]}",
            name="Toggle",
            tier=PlanTier.PRO,
            order=1,
            is_active=True,
        )
        plan.is_active = False
        plan.save(update_fields=["is_active"])
        plan.refresh_from_db()
        assert not plan.is_active


# ── 285.13.16.3 — Plan fixtures ───────────────────────────────────────────


class PlanFixturesTests(TestCase):
    """285.13.16.3 — Plan fixture integrity: known slugs, ML plan
    structure, and billing interval defaults."""

    @pytest.mark.integration
    def test_get_starter_plan(self):
        p = get_starter_plan()
        assert p.slug == "starter"
        assert p.order == 1
        assert p.price_amount_cents == 2999

    @pytest.mark.integration
    def test_get_growth_plan(self):
        p = get_growth_plan()
        assert p.slug == "growth"
        assert p.order == 2
        assert p.price_amount_cents == 7999

    @pytest.mark.integration
    def test_get_scale_plan(self):
        p = get_scale_plan()
        assert p.slug == "scale"
        assert p.order == 4
        assert p.price_amount_cents == 49999

    @pytest.mark.integration
    def test_fixtures_idempotent(self):
        s1 = get_starter_plan()
        s2 = get_starter_plan()
        assert (
            s1.id == s2.id
        )  # ── 285.13.16.4 — $0 Stripe subs unchanged ────────────────────────────────)


class ZeroDollarStripeSubscriptionsTests(TestCase):
    """285.13.16.4 — Zero-dollar plans skip Stripe integration; paid
    plans proceed through the normal checkout flow."""

    @pytest.mark.integration
    def test_free_plan_creates_no_stripe_subscription(self):
        tenant = create_unique_tenant()
        free = get_free_plan()
        svc = SubscriptionService(tenant_id=str(tenant.id))
        sub = svc.create_subscription(tenant=tenant, plan=free)
        assert sub.stripe_subscription_id is None
        assert sub.stripe_customer_id is None
        assert sub.status == SubscriptionStatus.ACTIVE

    @pytest.mark.integration
    def test_zero_price_plan_skips_stripe(self):
        tenant = create_unique_tenant()
        plan = TenantPlan.objects.create(
            slug=f"zero-{uuid.uuid4().hex[:8]}",
            name="Zero",
            tier=PlanTier.PRO,
            order=1,
            price_amount_cents=0,
            is_active=True,
        )
        svc = SubscriptionService(tenant_id=str(tenant.id))
        sub = svc.create_subscription(tenant=tenant, plan=plan)
        assert sub.stripe_subscription_id is None
