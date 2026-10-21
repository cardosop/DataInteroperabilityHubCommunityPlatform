"""
Phase 313.H.3 — tenants paid-layer hook degradation.

Onboarding's billing signal, the Stripe-customer resolution, and the
admin-dashboard billing widget resolve through commercial hooks.
Core-only mode (simulated by unregistering the paid providers — the
exact runtime shape of a core-only process):
* onboarding completion no longer depends on billing (vacuous truth);
* the Stripe-customer lookup returns None (bootstrap-not-complete);
* the billing widget returns the zeroed structure.

NO MOCKS at contract boundaries: real Postgres, real ORM, real
services.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from hub.apps.core import commercial_hooks
from hub.apps.tenants.admin_dashboard_summary import _aggregate_billing
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.tenants.onboarding import evaluate_onboarding_completion
from hub.apps.tenants.tax_id_service import _stripe_customer_id_for_tenant
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _import_paid_module(module_path: str):
    """GATE-29 — core-tree tests must not statically import paid modules.

    The dynamic import runs inside the test method that needs it: the paid
    apps ARE installed in the full-mode suite where these tests run, and
    core-only runs skip in setUp before ever reaching the call.
    """
    import importlib

    return importlib.import_module(module_path)


class OnboardingCoreModeTests(TestCase):
    """The billing onboarding signal is vacuously satisfied in core."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}",
            slug=f"t-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

    def _make_admin(self):
        user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=user, role=role, tenant=self.tenant)
        return user

    def test_core_only_onboarding_completes_with_admin_and_kyc(self):
        """No billing layer → admin + KYC are sufficient."""
        self._make_admin()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            completed = evaluate_onboarding_completion(self.tenant)
        assert completed is True

    def test_core_only_onboarding_requires_admin(self):
        """KYC alone is not enough — the tenant-admin signal stays core."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            completed = evaluate_onboarding_completion(self.tenant)
        assert completed is False


class StripeCustomerCoreModeTests(TestCase):
    """The Stripe-customer lookup returns None without the billing layer."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}",
            slug=f"t-{uid}",
            status=TenantStatus.ACTIVE,
        )

    def test_core_only_returns_none(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resolved = _stripe_customer_id_for_tenant(self.tenant)
        assert resolved is None

    def test_no_subscription_returns_none(self):
        """P.2c de-vacuum: the old "full-mode" test also passed in core-only
        (the provider returns None when no subscription exists — an outcome
        the core default cannot distinguish). Now an honest mode-independent
        no-subscription case; the discriminating full-mode pair lives in
        FullModeBillingHooksTests below."""
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("billing models absent in core-only mode")
        Subscription = _import_paid_module("hub.apps.billing.models").Subscription

        Subscription.objects.filter(tenant=self.tenant).delete()
        assert _stripe_customer_id_for_tenant(self.tenant) is None


class FullModeBillingHooksTests(TransactionTestCase):
    """P.2c — the billing hooks DISCRIMINATE in full mode.

    TransactionTestCase (not TestCase): the admin billing summary
    aggregates through ``Subscription.objects.using("admin")`` — a
    separate connection that never sees the outer atomic's uncommitted
    rows, so under TestCase the counts are residue-dependent (the
    test only passed when OTHER tests had left committed ACTIVE
    subscriptions behind). Committed rows make the assertion
    deterministic.

    Each assertion here is an outcome the core default cannot produce:
    * ``has_active_billing_setup`` → False without a subscription (core
      default is the vacuous True);
    * Stripe customer → resolved from a real subscription row;
    * admin billing summary → non-zero counts.
    """

    def setUp(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("billing hooks exist only in full mode")
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}",
            slug=f"t-{uid}",
            status=TenantStatus.ACTIVE,
        )

    def test_has_active_billing_setup_false_without_subscription(self):
        """The core default (True) cannot produce False — discrimination."""
        Subscription = _import_paid_module("hub.apps.billing.models").Subscription

        Subscription.objects.filter(tenant=self.tenant).delete()
        assert commercial_hooks.has_active_billing_setup(self.tenant) is False

    def test_has_active_billing_setup_true_with_active_subscription(self):
        from hub.apps.tenants.tests.factories import SubscriptionFactory

        SubscriptionFactory.create_subscription(tenant=self.tenant)
        assert commercial_hooks.has_active_billing_setup(self.tenant) is True

    def test_stripe_customer_resolved_from_subscription(self):
        from hub.apps.tenants.tests.factories import SubscriptionFactory

        subscription = SubscriptionFactory.create_subscription(tenant=self.tenant)
        assert subscription is not None
        subscription.stripe_customer_id = "cus_test_123"
        subscription.save(update_fields=["stripe_customer_id"])
        assert _stripe_customer_id_for_tenant(self.tenant) == "cus_test_123"

    def test_admin_billing_summary_counts_active_subscriptions(self):
        from hub.apps.tenants.tests.factories import SubscriptionFactory

        SubscriptionFactory.create_subscription(tenant=self.tenant)
        summary = _aggregate_billing()
        assert summary["active"] >= 1
        assert summary["plan_distribution"]["total_active"] >= 1


class AdminBillingSummaryCoreModeTests(TestCase):
    """The billing widget returns the zeroed structure in core."""

    def test_core_only_zeroed_summary(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            summary = _aggregate_billing()
        assert summary["active"] == 0
        assert summary["plan_distribution"] == {"by_tier": {}, "total_active": 0}
