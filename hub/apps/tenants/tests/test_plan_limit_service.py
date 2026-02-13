"""
Unit tests for PlanLimitService.

Tests use real DB, no mocks/stubs per Phase 25 requirements.
"""

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan
from hub.apps.tenants.services import PlanLimitService

pytestmark = pytest.mark.django_db(transaction=True)


class PlanLimitServiceTest(TestCase):
    """Test PlanLimitService"""

    def setUp(self):
        """Set up test data"""
        # Create test plans
        self.free_plan = TenantPlan.objects.create(
            name="Free Plan",
            slug="free",
            tier=PlanTier.FREE,
            limits_json={
                "max_assets": 10,
                "max_datasets": 20,
                "max_api_calls_per_month": 10000,
            },
        )

        self.pro_plan = TenantPlan.objects.create(
            name="Pro Plan",
            slug="pro",
            tier=PlanTier.PRO,
            limits_json={
                "max_assets": 100,
                "max_datasets": 500,
                "max_api_calls_per_month": 100000,
            },
        )

        self.enterprise_plan = TenantPlan.objects.create(
            name="Enterprise Plan",
            slug="enterprise",
            tier=PlanTier.ENTERPRISE,
            limits_json={
                "max_assets": None,  # Unlimited
                "max_datasets": None,  # Unlimited
                "max_api_calls_per_month": None,  # Unlimited
            },
        )

        # Create test tenant with FREE plan
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", plan=self.free_plan
        )

        self.service = PlanLimitService(tenant_id=str(self.tenant.id))

    def test_check_limit_within_limit(self):
        """Success: check_limit returns allowed=True when usage + delta within max."""
        result = self.service.check_limit(
            tenant_id=str(self.tenant.id), limit_key="max_assets", current_usage=5, delta=2
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 5)
        self.assertEqual(result["max"], 10)
        self.assertEqual(result["remaining"], 3)
        self.assertEqual(result["limit_key"], "max_assets")
        self.assertEqual(result["plan_slug"], "free")

    def test_check_limit_at_limit(self):
        """Test check_limit when usage is at limit"""
        result = self.service.check_limit(
            tenant_id=str(self.tenant.id), limit_key="max_assets", current_usage=10, delta=0
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 10)
        self.assertEqual(result["max"], 10)
        self.assertEqual(result["remaining"], 0)

    def test_check_limit_exceeded(self):
        """Failure: check_limit raises ValidationError with code plan_limit_exceeded when over limit."""
        with self.assertRaises(ValidationError) as cm:
            self.service.check_limit(
                tenant_id=str(self.tenant.id), limit_key="max_assets", current_usage=10, delta=1
            )

        error = cm.exception
        self.assertEqual(error.code, "plan_limit_exceeded")
        self.assertEqual(error.http_status, 403)
        self.assertEqual(error.details["limit_key"], "max_assets")
        self.assertEqual(error.details["current"], 10)
        self.assertEqual(error.details["max"], 10)
        self.assertEqual(error.details["requested_delta"], 1)
        self.assertEqual(error.details["new_usage"], 11)

    def test_check_limit_unlimited_enterprise(self):
        """Test check_limit with unlimited enterprise plan"""
        # Update tenant to enterprise plan
        self.tenant.plan = self.enterprise_plan
        self.tenant.save()

        result = self.service.check_limit(
            tenant_id=str(self.tenant.id), limit_key="max_assets", current_usage=1000, delta=1000
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 1000)
        self.assertIsNone(result["max"])
        self.assertIsNone(result["remaining"])
        self.assertEqual(result["plan_tier"], PlanTier.ENTERPRISE)

    def test_check_limit_tenant_without_plan_defaults_to_free(self):
        """Test check_limit when tenant has no plan, defaults to FREE"""
        # Create tenant without plan
        tenant_no_plan = Tenant.objects.create(name="No Plan Tenant", slug="no-plan-tenant")

        service = PlanLimitService(tenant_id=str(tenant_no_plan.id))

        # Should default to FREE plan
        result = service.check_limit(
            tenant_id=str(tenant_no_plan.id), limit_key="max_assets", current_usage=5, delta=2
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["plan_slug"], "free")
        self.assertEqual(result["max"], 10)

    def test_check_limit_tenant_not_found(self):
        """Test check_limit when tenant doesn't exist"""
        service = PlanLimitService()

        with self.assertRaises(NotFoundError):
            service.check_limit(
                tenant_id="00000000-0000-0000-0000-000000000000",
                limit_key="max_assets",
                current_usage=0,
            )

    def test_check_limit_pro_plan_higher_limits(self):
        """Test check_limit with PRO plan has higher limits"""
        self.tenant.plan = self.pro_plan
        self.tenant.save()

        # Should allow up to 100 assets
        result = self.service.check_limit(
            tenant_id=str(self.tenant.id), limit_key="max_assets", current_usage=90, delta=5
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["max"], 100)
        self.assertEqual(result["plan_slug"], "pro")

    def test_check_limit_different_limit_keys(self):
        """Test check_limit with different limit keys"""
        # Test max_datasets
        result = self.service.check_limit(
            tenant_id=str(self.tenant.id), limit_key="max_datasets", current_usage=15, delta=3
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["max"], 20)

        # Test max_api_calls_per_month
        result = self.service.check_limit(
            tenant_id=str(self.tenant.id),
            limit_key="max_api_calls_per_month",
            current_usage=5000,
            delta=2000,
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["max"], 10000)

    def test_check_limit_no_default_free_plan_raises_error(self):
        """Test check_limit when tenant has no plan and FREE plan doesn't exist"""
        # Delete FREE plan
        self.free_plan.delete()

        # Create tenant without plan
        tenant_no_plan = Tenant.objects.create(name="No Plan Tenant", slug="no-plan-tenant-2")

        service = PlanLimitService(tenant_id=str(tenant_no_plan.id))

        with self.assertRaises(NotFoundError) as cm:
            service.check_limit(
                tenant_id=str(tenant_no_plan.id), limit_key="max_assets", current_usage=0
            )

        error = cm.exception
        self.assertEqual(error.code, "PLAN_NOT_FOUND")
