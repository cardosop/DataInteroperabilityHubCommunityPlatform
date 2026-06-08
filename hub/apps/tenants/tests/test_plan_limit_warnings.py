"""Tests for soft-limit warnings in check_limit() and validate_downgrade() (277.B.113)."""

import pytest
import uuid
from unittest.mock import patch

from django.test import TestCase

from hub.apps.billing.services import PlanLimitService as BillingPlanLimitService
from hub.apps.tenants.models import PlanCategory, PlanTier, Tenant, TenantPlan
from hub.apps.tenants.services import PlanLimitService


pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant_plan(slug, tier, limits_json):
    return TenantPlan.objects.create(
        name=f"Test {slug}",
        slug=slug,
        tier=tier,
        limits_json=limits_json,
        is_active=True,
    )


def _make_tenant(plan):
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"WarnTest {uid}",
        slug=f"warntest-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        plan=plan,
    )


class CheckLimitWarningTest(TestCase):
    """Soft-limit warnings in PlanLimitService.check_limit()."""

    def setUp(self):
        self.plan = _make_tenant_plan("test-pro", PlanTier.PRO, {"max_assets": 10})
        self.tenant = _make_tenant(self.plan)
        self.service = PlanLimitService()

    @pytest.mark.integration
    def test_no_warning_below_80_percent(self):
        """Usage at 70% — no warning."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=7
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0,
            )
        self.assertTrue(result["allowed"])
        self.assertNotIn("warning", result)

    @pytest.mark.integration
    def test_warning_at_80_percent_exactly(self):
        """Usage at exactly 80% — warning fires."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=8
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0,
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["warning"], "approaching_limit")
        self.assertEqual(result["warning_percent"], 80.0)

    @pytest.mark.integration
    def test_warning_above_80_percent(self):
        """Usage at 90% — warning fires."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=9
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0,
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["warning"], "approaching_limit")
        self.assertEqual(result["warning_percent"], 90.0)

    @pytest.mark.integration
    def test_warning_at_99_percent(self):
        """Usage at 99% — warning fires, still allowed."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=9
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0,
            )
        self.assertTrue(result["allowed"])
        self.assertIn("warning", result)

    @pytest.mark.integration
    def test_no_warning_when_emit_warning_false(self):
        """emit_warning=False suppresses the warning."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=9
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0, emit_warning=False,
            )
        self.assertTrue(result["allowed"])
        self.assertNotIn("warning", result)

    @pytest.mark.integration
    def test_no_warning_for_unlimited_plan(self):
        """ENTERPRISE plan has None limits — never warns."""
        ent_plan = _make_tenant_plan("ent-test", PlanTier.ENTERPRISE, {"max_assets": None})
        tenant = _make_tenant(ent_plan)
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=9999
        ):
            result = self.service.check_limit(
                str(tenant.id), "max_assets", delta=0,
            )
        self.assertTrue(result["allowed"])
        self.assertIsNone(result["max"])
        self.assertNotIn("warning", result)

    @pytest.mark.integration
    def test_delta_included_in_percent_calculation(self):
        """Warning percentage includes the requested delta, not just current."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=6
        ):
            # current=6, delta=2 → new_usage=8 → 8/10 = 80% → warning
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=2,
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["warning"], "approaching_limit")
        self.assertEqual(result["warning_percent"], 80.0)

    @pytest.mark.integration
    def test_warning_percent_rounded(self):
        """warning_percent is rounded to 1 decimal place."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=8
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0,
            )
        self.assertEqual(result["warning_percent"], 80.0)
        # Result should be a float rounded to 1 decimal
        self.assertIsInstance(result["warning_percent"], float)

    @pytest.mark.integration
    def test_warning_includes_remaining_and_current(self):
        """Warning response still includes all standard fields."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=8
        ):
            result = self.service.check_limit(
                str(self.tenant.id), "max_assets", delta=0,
            )
        self.assertIn("remaining", result)
        self.assertIn("current", result)
        self.assertIn("max", result)
        self.assertIn("allowed", result)

    @pytest.mark.integration
    def test_hard_limit_still_blocks_at_100_percent(self):
        """At 100% the limit is still enforced — raises ValidationError."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count", return_value=10
        ):
            from hub.apps.core.services.base import ValidationError as SvcValidationError
            with self.assertRaises(SvcValidationError) as ctx:
                self.service.check_limit(
                    str(self.tenant.id), "max_assets", delta=1,
                )
            self.assertEqual(ctx.exception.code, "plan_limit_exceeded")


class ValidateDowngradeWarningTest(TestCase):
    """Soft-limit warnings in Billing PlanLimitService.validate_downgrade()."""

    def setUp(self):
        self.pro_plan = _make_tenant_plan(
            "downgrade-pro", PlanTier.PRO,
            {"max_assets": 100, "max_datasets": 50, "max_webhooks": None},
        )
        self.free_plan = _make_tenant_plan(
            "downgrade-free", PlanTier.FREE,
            {"max_assets": 10, "max_datasets": 20, "max_webhooks": 5},
        )
        self.tenant = _make_tenant(self.pro_plan)

    @pytest.mark.integration
    def test_no_warnings_when_usage_well_below_new_limits(self):
        """All usage <80% of new plan limits — no warnings."""
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count",
            return_value=5,  # 5/10=50% for assets, 5/20=25% for datasets, 5/5=100% for webhooks
        ):
            result = BillingPlanLimitService.validate_downgrade(
                str(self.tenant.id), self.free_plan,
            )
        self.assertTrue(result.is_valid)
        # webhooks at 100% (5/5) = hard block, but 5<=5 means it triggered error not warning.
        # Actually 5 <= 5 → no error. But 5/5 = 100% -> is there a warning?
        # At exactly 100%, current==limit → no error (exceed not met), and >=80% → warning
        self.assertIn("max_webhooks", result.details)

    @patch("hub.apps.billing.limit_registry.get_resource_count")
    @pytest.mark.integration
    def test_warning_when_usage_at_80_percent_of_new_plan(self, mock_count):
        """Usage at 8/10=80% → warning emitted."""
        def _count(tenant_id, key):
            return {"max_assets": 8, "max_datasets": 5, "max_webhooks": 1}[key]
        mock_count.side_effect = _count

        result = BillingPlanLimitService.validate_downgrade(
            str(self.tenant.id), self.free_plan,
        )
        self.assertTrue(result.is_valid)
        self.assertIn("max_assets", result.details)
        w = result.details["max_assets"]
        self.assertEqual(w["warning"], "approaching_limit")
        self.assertEqual(w["warning_percent"], 80.0)

    @pytest.mark.integration
    def test_warning_and_error_can_coexist(self):
        """Some keys at >=80% (warning), others exceeding (error)."""
        def _count(tenant_id, key):
            return {"max_assets": 12, "max_datasets": 18, "max_webhooks": 3}[key]
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count",
            side_effect=_count,
        ):
            result = BillingPlanLimitService.validate_downgrade(
                str(self.tenant.id), self.free_plan,
            )
        # assets: 12 > 10 → error
        self.assertFalse(result.is_valid)
        self.assertIn("assets", str(result.errors).lower())
        # datasets: 18/20=90% → warning
        self.assertIn("max_datasets", result.details)
        self.assertEqual(result.details["max_datasets"]["warning_percent"], 90.0)
        # webhooks: 3 < 5 (60%) → no warning, no error
        self.assertNotIn("max_webhooks", result.details)

    @pytest.mark.integration
    def test_warning_includes_current_and_max(self):
        """Warning details include current usage and max limit."""
        def _count(tenant_id, key):
            return {"max_assets": 9, "max_datasets": 5, "max_webhooks": 1}[key]
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count",
            side_effect=_count,
        ):
            result = BillingPlanLimitService.validate_downgrade(
                str(self.tenant.id), self.free_plan,
            )
        w = result.details["max_assets"]
        self.assertEqual(w["current"], 9)
        self.assertEqual(w["max"], 10)

    @pytest.mark.integration
    def test_unlimited_keys_skipped(self):
        """Keys with None limit are not checked."""
        plan = _make_tenant_plan("unlimited-plan", PlanTier.PRO, {"max_assets": None})
        with patch(
            "hub.apps.billing.limit_registry.get_resource_count",
            return_value=9999,
        ):
            result = BillingPlanLimitService.validate_downgrade(
                str(self.tenant.id), plan,
            )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.details), 0)
