"""
Unit tests for PlanLimitService.

Tests use real DB, no mocks/stubs per Phase 25 requirements.
Updated for Phase 113.B new check_limit() signature:
  check_limit(tenant_id, limit_key, delta=1)
  — no more current_usage parameter; count is queried internally.
"""

import uuid

import pytest
from django.db import transaction
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan
from hub.apps.tenants.services import PlanLimitService

pytestmark = pytest.mark.django_db(transaction=True)


def _uid():
    return uuid.uuid4().hex[:8]


def _make_plan(*, name_prefix="Plan", tier=PlanTier.FREE, limits=None, slug_prefix=None):
    uid = _uid()
    slug_prefix = slug_prefix or name_prefix.lower().replace(" ", "-")
    plan, _ = TenantPlan.objects.get_or_create(
        slug=f"{slug_prefix}-{uid}",
        defaults={
            "name": f"{name_prefix} {uid}",
            "tier": tier,
            "limits_json": limits or {},
            "is_active": True,
        },
    )
    return plan


def _make_tenant(*, plan=None, name_prefix="Tenant"):
    uid = _uid()
    return Tenant.objects.create(
        name=f"{name_prefix} {uid}",
        slug=f"{name_prefix.lower()}-{uid}",
        plan=plan,
    )


class PlanLimitServiceTest(TestCase):
    """Test PlanLimitService with the 113.B self-contained check_limit API."""

    def setUp(self):
        """Set up test data."""
        self.free_plan = _make_plan(
            name_prefix="Free",
            slug_prefix="free-test",
            tier=PlanTier.FREE,
            limits={
                "max_assets": 10,
                "max_datasets": 20,
                "max_api_calls_per_month": 10000,
            },
        )
        self.pro_plan = _make_plan(
            name_prefix="Pro",
            slug_prefix="pro-test",
            tier=PlanTier.PRO,
            limits={
                "max_assets": 100,
                "max_datasets": 500,
                "max_api_calls_per_month": 100000,
            },
        )
        self.enterprise_plan = _make_plan(
            name_prefix="Enterprise",
            slug_prefix="ent-test",
            tier=PlanTier.ENTERPRISE,
            limits={
                "max_assets": None,
                "max_datasets": None,
                "max_api_calls_per_month": None,
            },
        )

        self.tenant = _make_tenant(plan=self.free_plan)
        self.service = PlanLimitService(tenant_id=str(self.tenant.id))

    # ── Within limit ──

    def test_check_limit_within_limit(self):
        """Success: tenant has 0 assets, limit 10, delta 1 → allowed."""
        with transaction.atomic():
            result = self.service.check_limit(
                tenant_id=str(self.tenant.id),
                limit_key="max_assets",
                delta=1,
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 0)
        self.assertEqual(result["max"], 10)
        self.assertEqual(result["remaining"], 9)
        self.assertEqual(result["limit_key"], "max_assets")

    def test_check_limit_at_limit_delta_zero(self):
        """At limit with delta=0 → allowed, remaining=0."""
        # Create 10 assets to fill the limit
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{_uid()}",
                name=f"Asset {i}",
            )

        with transaction.atomic():
            result = self.service.check_limit(
                tenant_id=str(self.tenant.id),
                limit_key="max_assets",
                delta=0,
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 10)
        self.assertEqual(result["max"], 10)
        self.assertEqual(result["remaining"], 0)

    # ── Exceeded ──

    def test_check_limit_exceeded(self):
        """Failure: 10 assets exist, limit 10, delta 1 → raises plan_limit_exceeded."""
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{_uid()}",
                name=f"Asset {i}",
            )

        with self.assertRaises(ValidationError) as cm:
            with transaction.atomic():
                self.service.check_limit(
                    tenant_id=str(self.tenant.id),
                    limit_key="max_assets",
                    delta=1,
                )

        error = cm.exception
        self.assertEqual(error.code, "plan_limit_exceeded")
        self.assertEqual(error.http_status, 403)
        self.assertEqual(error.details["limit_key"], "max_assets")
        self.assertEqual(error.details["current"], 10)
        self.assertEqual(error.details["max"], 10)
        self.assertEqual(error.details["requested_delta"], 1)
        self.assertEqual(error.details["new_usage"], 11)

    # ── Enterprise (unlimited) ──

    def test_check_limit_unlimited_enterprise(self):
        """Enterprise plan: max=None → always allowed."""
        self.tenant.plan = self.enterprise_plan
        self.tenant.save()

        with transaction.atomic():
            result = self.service.check_limit(
                tenant_id=str(self.tenant.id),
                limit_key="max_assets",
                delta=1000,
            )

        self.assertTrue(result["allowed"])
        self.assertIsNone(result["max"])
        self.assertIsNone(result["remaining"])
        self.assertEqual(result["plan_tier"], PlanTier.ENTERPRISE)

    # ── Default to FREE ──

    def test_check_limit_tenant_without_plan_defaults_to_free(self):
        """Tenant without a plan → defaults to FREE plan."""
        tenant_no_plan = _make_tenant(name_prefix="NoPlan")

        service = PlanLimitService(tenant_id=str(tenant_no_plan.id))

        with transaction.atomic():
            result = service.check_limit(
                tenant_id=str(tenant_no_plan.id),
                limit_key="max_assets",
                delta=1,
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["plan_slug"], "free")
        # Verify max matches the free plan's actual limit
        from hub.apps.tenants.models import TenantPlan
        free_plan = TenantPlan.objects.get(slug="free")
        self.assertEqual(result["max"], free_plan.get_limit("max_assets"))

    # ── Tenant not found ──

    def test_check_limit_tenant_not_found(self):
        """Non-existent tenant → NotFoundError."""
        service = PlanLimitService()

        with self.assertRaises(NotFoundError):
            with transaction.atomic():
                service.check_limit(
                    tenant_id="00000000-0000-0000-0000-000000000000",
                    limit_key="max_assets",
                )

    # ── PRO plan higher limits ──

    def test_check_limit_pro_plan_higher_limits(self):
        """PRO plan allows up to 100 assets."""
        self.tenant.plan = self.pro_plan
        self.tenant.save()

        with transaction.atomic():
            result = self.service.check_limit(
                tenant_id=str(self.tenant.id),
                limit_key="max_assets",
                delta=5,
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["max"], 100)

    # ── Different limit keys ──

    def test_check_limit_different_limit_keys(self):
        """check_limit works for max_datasets and max_api_calls_per_month."""
        with transaction.atomic():
            result = self.service.check_limit(
                tenant_id=str(self.tenant.id),
                limit_key="max_datasets",
                delta=1,
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["max"], 20)

    # ── No FREE plan exists ──

    def test_check_limit_no_default_free_plan_raises_error(self):
        """Tenant without plan + no FREE plan in DB → NotFoundError."""
        from hub.apps.billing.models import Subscription
        tenant_no_plan = _make_tenant(name_prefix="OrphanTenant")
        # Delete subscriptions first (RESTRICT FK), then the free plan
        Subscription.objects.filter(plan__slug="free").delete()
        TenantPlan.objects.filter(slug="free").delete()

        service = PlanLimitService(tenant_id=str(tenant_no_plan.id))

        with self.assertRaises(NotFoundError) as cm:
            with transaction.atomic():
                service.check_limit(
                    tenant_id=str(tenant_no_plan.id),
                    limit_key="max_assets",
                    delta=1,
                )

        self.assertEqual(cm.exception.code, "PLAN_NOT_FOUND")

    # ── Soft-deleted assets don't count ──

    def test_retired_assets_excluded_from_count(self):
        """RETIRED assets are excluded from the max_assets count."""
        # Create 9 active + 5 retired = 14 total, but only 9 should count
        for i in range(9):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"active-{_uid()}",
                name=f"Active {i}",
                status="ACTIVE",
            )
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"retired-{_uid()}",
                name=f"Retired {i}",
                status="RETIRED",
            )

        with transaction.atomic():
            result = self.service.check_limit(
                tenant_id=str(self.tenant.id),
                limit_key="max_assets",
                delta=1,
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 9)
        self.assertEqual(result["remaining"], 0)
