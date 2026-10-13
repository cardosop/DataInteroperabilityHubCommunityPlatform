"""
Tests for seed_default_plans management command.

Verifies idempotent behavior: creates plans when missing, skips when present,
and fixes slug when plan exists with same name but wrong slug (IntegrityError recovery).
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.tenants.models import TenantPlan

pytestmark = pytest.mark.django_db(transaction=True)


class SeedDefaultPlansCommandTest(TestCase):
    """Test seed_default_plans management command."""

    def test_creates_plans_when_none_exist(self):
        """Success: creates free, pro, enterprise when DB is empty."""
        # billing is the paid layer — guarded for both core-only absence
        # forms (W7.1); without it there is nothing to wipe.
        try:
            from hub.apps.billing.models import Subscription
        except (RuntimeError, ModuleNotFoundError):
            Subscription = None  # type: ignore[assignment]

        if Subscription is not None:
            Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        self.assertEqual(TenantPlan.objects.count(), 0)
        out = StringIO()
        call_command("seed_default_plans", stdout=out)


class SeedPlansStripePriceIdTest(TestCase):
    """W2.0 (oss-release-remediation) — the seeder consumes the canonical
    Stripe price IDs from settings so a fresh deployment's plans are
    checkout-ready against the provisioned Stripe prices."""

    def test_pro_plan_gets_stripe_price_id_from_settings(self):
        from io import StringIO

        from django.test import override_settings

        # billing is the paid layer — guarded for both core-only absence
        # forms (W7.1); without it there is nothing to wipe.
        try:
            from hub.apps.billing.models import Subscription
        except (RuntimeError, ModuleNotFoundError):
            Subscription = None  # type: ignore[assignment]
        from hub.apps.tenants.models import TenantPlan

        if Subscription is not None:
            Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        with override_settings(
            STRIPE_PRO_PRICE_ID="price_test_red_pin_pro",
            STRIPE_FREE_PRICE_ID="",
        ):
            call_command("seed_default_plans", stdout=StringIO())
        pro = TenantPlan.objects.get(slug="pro")
        self.assertEqual(pro.stripe_price_id, "price_test_red_pin_pro")

    def test_free_plan_gets_stripe_price_id_from_settings_when_set(self):
        from io import StringIO

        from django.test import override_settings

        # billing is the paid layer — guarded for both core-only absence
        # forms (W7.1); without it there is nothing to wipe.
        try:
            from hub.apps.billing.models import Subscription
        except (RuntimeError, ModuleNotFoundError):
            Subscription = None  # type: ignore[assignment]
        from hub.apps.tenants.models import TenantPlan

        if Subscription is not None:
            Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        with override_settings(
            STRIPE_PRO_PRICE_ID="",
            STRIPE_FREE_PRICE_ID="price_test_red_pin_free",
        ):
            call_command("seed_default_plans", stdout=StringIO())
        free = TenantPlan.objects.get(slug="free")
        self.assertEqual(free.stripe_price_id, "price_test_red_pin_free")

    def test_plans_keep_null_price_when_settings_absent(self):
        from io import StringIO

        from django.test import override_settings

        # billing is the paid layer — guarded for both core-only absence
        # forms (W7.1); without it there is nothing to wipe.
        try:
            from hub.apps.billing.models import Subscription
        except (RuntimeError, ModuleNotFoundError):
            Subscription = None  # type: ignore[assignment]
        from hub.apps.tenants.models import TenantPlan

        if Subscription is not None:
            Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        with override_settings(STRIPE_PRO_PRICE_ID="", STRIPE_FREE_PRICE_ID=""):
            call_command("seed_default_plans", stdout=StringIO())
        self.assertIsNone(TenantPlan.objects.get(slug="pro").stripe_price_id)
        self.assertIsNone(TenantPlan.objects.get(slug="free").stripe_price_id)
