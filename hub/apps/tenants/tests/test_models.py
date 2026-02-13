"""
Unit tests for Tenant model.

Covers success, failure, and edge cases with real DB. TDD-style assertions.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TenantModelTest(TestCase):
    """Test Tenant model"""

    def test_create_tenant_success(self):
        """Success: tenant creation sets default status and kyc_status."""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.assertEqual(tenant.name, "Test Tenant")
        self.assertEqual(tenant.slug, "test-tenant")
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        self.assertIsNone(tenant.deleted_at)
        self.assertIsNotNone(tenant.id)

    def test_tenant_status_choices(self):
        """Test tenant status enum"""
        tenant = Tenant.objects.create(name="Test", slug="test")

        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)

        tenant.status = TenantStatus.DELETED
        tenant.save()
        self.assertEqual(tenant.status, TenantStatus.DELETED)

    def test_kyc_status_choices(self):
        """Test KYC status enum"""
        tenant = Tenant.objects.create(name="Test", slug="test")

        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save()
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)

    def test_tenant_is_active(self):
        """Test is_active method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertTrue(tenant.is_active())

        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertFalse(tenant.is_active())

    def test_tenant_is_suspended(self):
        """Test is_suspended method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertFalse(tenant.is_suspended())

        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertTrue(tenant.is_suspended())

    def test_tenant_is_deleted(self):
        """Test is_deleted method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertFalse(tenant.is_deleted())

        tenant.status = TenantStatus.DELETED
        tenant.save()
        self.assertTrue(tenant.is_deleted())

    def test_can_publish_to_marketplace(self):
        """Test can_publish_to_marketplace method"""
        tenant = Tenant.objects.create(name="Test", slug="test")

        # Unverified tenant cannot publish
        self.assertFalse(tenant.can_publish_to_marketplace())

        # Verified but suspended cannot publish
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertFalse(tenant.can_publish_to_marketplace())

        # Verified and active can publish
        tenant.status = TenantStatus.ACTIVE
        tenant.save()
        self.assertTrue(tenant.can_publish_to_marketplace())

    def test_suspend_tenant(self):
        """Test suspend method"""
        tenant = Tenant.objects.create(name="Test", slug="test")

        tenant.suspend()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)

        # Cannot suspend deleted tenant
        tenant.status = TenantStatus.DELETED
        tenant.save()
        with self.assertRaises(ValueError):
            tenant.suspend()

    def test_reactivate_tenant(self):
        """Test reactivate method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        tenant.suspend()

        tenant.reactivate()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)

        # Can only reactivate suspended tenants
        tenant.status = TenantStatus.ACTIVE
        tenant.save()
        with self.assertRaises(ValueError):
            tenant.reactivate()

    def test_soft_delete_tenant(self):
        """Test soft_delete method"""
        tenant = Tenant.objects.create(name="Test", slug="test")

        tenant.soft_delete()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)

    def test_slug_uniqueness_failure(self):
        """Failure: duplicate slug raises IntegrityError."""
        Tenant.objects.create(name="Test 1", slug="test-tenant")
        with self.assertRaises(IntegrityError):
            Tenant.objects.create(name="Test 2", slug="test-tenant")

    def test_name_uniqueness_failure(self):
        """Failure: duplicate name raises IntegrityError."""
        Tenant.objects.create(name="Test Tenant", slug="test-tenant-1")
        with self.assertRaises(IntegrityError):
            Tenant.objects.create(name="Test Tenant", slug="test-tenant-2")

    def test_tenant_region_optional_edge_case(self):
        """Edge case: region can be null or blank."""
        t1 = Tenant.objects.create(name="T1", slug="t1", region=None)
        t2 = Tenant.objects.create(name="T2", slug="t2", region="us-east-1")
        self.assertIsNone(t1.region)
        self.assertEqual(t2.region, "us-east-1")

    def test_tenant_plan_relationship(self):
        """Test tenant plan relationship"""
        plan = TenantPlan.objects.create(
            name="Free Plan", slug="free", tier=PlanTier.FREE, limits_json={"max_assets": 10}
        )

        tenant = Tenant.objects.create(name="Test", slug="test", plan=plan)
        self.assertEqual(tenant.plan, plan)
        self.assertEqual(tenant.plan.tier, PlanTier.FREE)

    def test_tenant_without_plan(self):
        """Test tenant can exist without plan"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertIsNone(tenant.plan)


class TenantPlanModelTest(TestCase):
    """Test TenantPlan model"""

    def test_create_tenant_plan(self):
        """Test tenant plan creation"""
        plan = TenantPlan.objects.create(
            name="Free Plan",
            slug="free",
            tier=PlanTier.FREE,
            limits_json={"max_assets": 10, "max_api_calls_per_month": 10000},
        )

        self.assertEqual(plan.name, "Free Plan")
        self.assertEqual(plan.slug, "free")
        self.assertEqual(plan.tier, PlanTier.FREE)
        self.assertEqual(plan.limits_json["max_assets"], 10)
        self.assertTrue(plan.is_active)

    def test_plan_get_limit(self):
        """Test get_limit method"""
        plan = TenantPlan.objects.create(
            name="Pro Plan", slug="pro", tier=PlanTier.PRO, limits_json={"max_assets": 100}
        )

        self.assertEqual(plan.get_limit("max_assets"), 100)
        self.assertIsNone(plan.get_limit("nonexistent_limit"))
        self.assertEqual(plan.get_limit("nonexistent_limit", default=0), 0)

    def test_plan_tier_choices(self):
        """Test plan tier enum"""
        plan_free = TenantPlan.objects.create(
            name="Free", slug="free", tier=PlanTier.FREE, limits_json={}
        )
        plan_pro = TenantPlan.objects.create(
            name="Pro", slug="pro", tier=PlanTier.PRO, limits_json={}
        )
        plan_enterprise = TenantPlan.objects.create(
            name="Enterprise", slug="enterprise", tier=PlanTier.ENTERPRISE, limits_json={}
        )

        self.assertEqual(plan_free.tier, PlanTier.FREE)
        self.assertEqual(plan_pro.tier, PlanTier.PRO)
        self.assertEqual(plan_enterprise.tier, PlanTier.ENTERPRISE)

    def test_plan_slug_uniqueness_failure(self):
        """Failure: duplicate plan slug raises IntegrityError."""
        TenantPlan.objects.create(
            name="Plan 1", slug="test-plan", tier=PlanTier.FREE, limits_json={}
        )
        with self.assertRaises(IntegrityError):
            TenantPlan.objects.create(
                name="Plan 2", slug="test-plan", tier=PlanTier.PRO, limits_json={}
            )

    def test_plan_name_uniqueness_failure(self):
        """Failure: duplicate plan name raises IntegrityError."""
        TenantPlan.objects.create(
            name="Test Plan", slug="test-1", tier=PlanTier.FREE, limits_json={}
        )
        with self.assertRaises(IntegrityError):
            TenantPlan.objects.create(
                name="Test Plan", slug="test-2", tier=PlanTier.PRO, limits_json={}
            )

    def test_plan_get_limit_edge_case_default(self):
        """Edge case: get_limit with missing key returns default when provided."""
        plan = TenantPlan.objects.create(
            name="P", slug="p", tier=PlanTier.FREE, limits_json={"max_assets": 5}
        )
        self.assertIsNone(plan.get_limit("unknown"))
        self.assertEqual(plan.get_limit("unknown", default=99), 99)
