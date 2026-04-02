"""
Tests for seed_default_plans management command.

Verifies idempotent behavior: creates plans when missing, skips when present,
and fixes slug when plan exists with same name but wrong slug (IntegrityError recovery).
"""
import pytest
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from hub.apps.tenants.models import PlanTier, TenantPlan


pytestmark = pytest.mark.django_db(transaction=True)


class SeedDefaultPlansCommandTest(TestCase):
    """Test seed_default_plans management command."""

    def test_creates_plans_when_none_exist(self):
        """Success: creates free, pro, enterprise when DB is empty."""
        from hub.apps.billing.models import Subscription
        Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()
        assert TenantPlan.objects.count() == 0
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        assert TenantPlan.objects.filter(slug="free").exists()
        assert TenantPlan.objects.filter(slug="pro").exists()
        assert TenantPlan.objects.filter(slug="enterprise").exists()
        assert "Created" in out.getvalue(), (
            f"Expected 'Created' in output when DB was empty, "
            f"got: {out.getvalue()}"
        )

    def test_skips_when_plans_exist_by_slug(self):
        """Success: skips when plans already exist with correct slug."""
        call_command("seed_default_plans")
        count_before = TenantPlan.objects.count()
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        assert TenantPlan.objects.count() == count_before
        assert "Skipped" in out.getvalue()

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
        assert not TenantPlan.objects.filter(slug="free").exists()
        out = StringIO()
        call_command("seed_default_plans", stdout=out)
        plan = TenantPlan.objects.get(name="Free Plan")
        assert plan.slug == "free"
        output = out.getvalue()
        assert "Fixed" in output, f"Expected 'Fixed' in output but got: {output}"

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
        assert plan.slug == "free"
        assert TenantPlan.objects.filter(slug="free").count() == 1
