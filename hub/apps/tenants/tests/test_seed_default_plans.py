"""
Tests for seed_default_plans management command.

Verifies idempotent behavior: creates plans when missing, skips when present,
and fixes slug when plan exists with same name but wrong slug (IntegrityError recovery).
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.tenants.models import PlanTier, TenantPlan

pytestmark = pytest.mark.django_db(transaction=True)


class SeedDefaultPlansCommandTest(TestCase):
    """Test seed_default_plans management command."""

    def test_creates_plans_when_none_exist(self):
        """Success: creates free, pro, enterprise when DB is empty."""
        from hub.apps.billing.models import Subscription

        Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        self.assertEqual(TenantPlan.objects.count(), 0)
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        self.assertTrue(TenantPlan.objects.filter(slug="free").exists())
        self.assertTrue(TenantPlan.objects.filter(slug="pro").exists())
        self.assertTrue(TenantPlan.objects.filter(slug="enterprise").exists())

        self.assertIn(
            "Created",
            out.getvalue(),
            f"Expected 'Created' in output when DB was empty, got: {out.getvalue()}",
        )

    def test_skips_when_plans_exist_by_slug(self):
        """Success: skips when plans already exist with correct slug."""
        call_command("seed_default_plans")
        count_before = TenantPlan.objects.count()
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        self.assertEqual(TenantPlan.objects.count(), count_before)
        self.assertIn("Skipped", out.getvalue())

    def test_fixes_slug_when_name_exists_but_slug_wrong(self):
        """Success: when plan has name 'Free Plan' but slug not 'free', fixes slug."""
        from hub.apps.billing.models import Subscription

        Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        # Create plan with wrong slug (simulates migration/migration artifact)
        TenantPlan.objects.create(
            name="Free Plan",
            slug="free-wrong",
            tier=PlanTier.FREE,
            limits_json={"max_assets": 10},
            is_active=True,
        )
        self.assertFalse(TenantPlan.objects.filter(slug="free").exists())
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        plan = TenantPlan.objects.get(name="Free Plan")
        self.assertEqual(plan.slug, "free")
        output = out.getvalue()
        self.assertIn("Fixed", output, f"Expected 'Fixed' in output but got: {output}")

    def test_skips_when_name_and_slug_match_race(self):
        """Success: when IntegrityError but plan already has correct slug, skips."""
        from hub.apps.billing.models import Subscription

        Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        # Plan exists with correct slug (race: another process created it)
        TenantPlan.objects.create(
            name="Free Plan",
            slug="free",
            tier=PlanTier.FREE,
            limits_json={"max_assets": 10},
            is_active=True,
        )
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        plan = TenantPlan.objects.get(name="Free Plan")
        self.assertEqual(plan.slug, "free")
        self.assertEqual(TenantPlan.objects.filter(slug="free").count(), 1)
