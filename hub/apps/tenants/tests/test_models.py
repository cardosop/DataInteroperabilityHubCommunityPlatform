"""
Unit tests for Tenant model.

Covers success, failure, and edge cases with real DB. TDD-style assertions.
All names/slugs use uuid suffixes to avoid UniqueViolation under --keepdb.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant(**overrides):
    """Create a Tenant with a unique name/slug. Avoids collision under --keepdb."""
    from django.db import connection
    # Recover from InFailedSqlTransaction left by a previous test's teardown
    if connection.needs_rollback:
        connection.rollback()
    uid = uuid.uuid4().hex[:8]
    defaults = {
        "name": f"Tenant {uid}",
        "slug": f"tenant-{uid}",
    }
    defaults.update(overrides)
    return Tenant.objects.create(**defaults)


class TenantModelTest(TestCase):
    """Test Tenant model"""

    def test_create_tenant_success(self):
        """Success: tenant creation sets default status and kyc_status."""
        tenant = _make_tenant()
        self.assertTrue(tenant.name.startswith("Tenant "))
        self.assertTrue(tenant.slug.startswith("tenant-"))
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        self.assertIsNone(tenant.deleted_at)
        self.assertIsNotNone(tenant.id)

    def test_tenant_status_choices(self):
        """Test tenant status enum"""
        tenant = _make_tenant()

        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)

        tenant.status = TenantStatus.DELETED
        tenant.save()
        self.assertEqual(tenant.status, TenantStatus.DELETED)

    def test_kyc_status_choices(self):
        """Test KYC status enum"""
        tenant = _make_tenant()

        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save()
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)

    def test_tenant_is_active(self):
        """Test is_active method"""
        tenant = _make_tenant()
        self.assertTrue(tenant.is_active())

        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertFalse(tenant.is_active())

    def test_tenant_is_suspended(self):
        """Test is_suspended method"""
        tenant = _make_tenant()
        self.assertFalse(tenant.is_suspended())

        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertTrue(tenant.is_suspended())

    def test_tenant_is_deleted(self):
        """Test is_deleted method"""
        tenant = _make_tenant()
        self.assertFalse(tenant.is_deleted())

        tenant.status = TenantStatus.DELETED
        tenant.save()
        self.assertTrue(tenant.is_deleted())

    def test_can_publish_to_marketplace(self):
        """Test can_publish_to_marketplace method"""
        tenant = _make_tenant()

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
        tenant = _make_tenant()

        tenant.suspend()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)

        # Cannot suspend deleted tenant
        tenant.status = TenantStatus.DELETED
        tenant.save()
        with self.assertRaises(ValueError):
            tenant.suspend()

    def test_reactivate_tenant(self):
        """Test reactivate method"""
        tenant = _make_tenant()
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
        tenant = _make_tenant()

        tenant.soft_delete()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)

    def test_slug_uniqueness_failure(self):
        """Failure: duplicate slug raises IntegrityError."""
        uid = uuid.uuid4().hex[:8]
        Tenant(name=f"Slug Test 1 {uid}", slug=f"slug-uniq-{uid}").save()
        with self.assertRaises(IntegrityError):
            Tenant(name=f"Slug Test 2 {uid}", slug=f"slug-uniq-{uid}").save()

    def test_name_uniqueness_failure(self):
        """Failure: duplicate name raises IntegrityError."""
        uid = uuid.uuid4().hex[:8]
        Tenant(name=f"Name Uniq {uid}", slug=f"name-uniq-1-{uid}").save()
        with self.assertRaises(IntegrityError):
            Tenant(name=f"Name Uniq {uid}", slug=f"name-uniq-2-{uid}").save()

    def test_tenant_region_optional_edge_case(self):
        """Edge case: region can be null or blank."""
        uid = uuid.uuid4().hex[:8]
        t1 = Tenant.objects.create(name=f"T1 {uid}", slug=f"t1-{uid}", region=None)
        t2 = Tenant.objects.create(name=f"T2 {uid}", slug=f"t2-{uid}", region="us-east-1")
        self.assertIsNone(t1.region)
        self.assertEqual(t2.region, "us-east-1")

    def test_tenant_plan_relationship(self):
        """Test tenant plan relationship"""
        plan, _ = TenantPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free Plan",
                "tier": PlanTier.FREE,
                "limits_json": {"max_assets": 10},
            },
        )

        tenant = _make_tenant(plan=plan)
        self.assertEqual(tenant.plan, plan)
        self.assertEqual(tenant.plan.tier, PlanTier.FREE)

    def test_tenant_without_plan(self):
        """Test tenant can exist without plan"""
        tenant = _make_tenant()
        self.assertIsNone(tenant.plan)

    # ── H11: restore() method ────────────────────────────────────
    def test_restore_tenant(self):
        """Test restore() clears deleted_at and sets status to ACTIVE."""
        tenant = _make_tenant()
        tenant.soft_delete()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)

        tenant.restore()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertIsNone(tenant.deleted_at)

        # Verify persistence
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertIsNone(tenant.deleted_at)

    # ── H10: ActiveTenantManager excludes soft-deleted ───────────
    def test_active_tenant_manager_excludes_deleted(self):
        """Tenant.objects (ActiveTenantManager) excludes soft-deleted;
        Tenant.all_objects includes them."""
        tenant = _make_tenant()
        tid = tenant.id
        tenant.soft_delete()

        # Default manager should NOT find it
        self.assertFalse(Tenant.objects.filter(id=tid).exists())
        # all_objects should still find it
        self.assertTrue(Tenant.all_objects.filter(id=tid).exists())

    # ── H13: KYC expiry blocks marketplace publishing ────────────
    def test_can_publish_to_marketplace_kyc_expired(self):
        """Tenant with expired KYC cannot publish to marketplace."""
        from datetime import timedelta
        tenant = _make_tenant()
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.status = TenantStatus.ACTIVE
        # Set KYC expiry in the past
        tenant.kyc_expires_at = timezone.now() - timedelta(days=1)
        tenant.save()
        self.assertFalse(tenant.can_publish_to_marketplace())

    def test_can_publish_to_marketplace_kyc_not_expired(self):
        """Tenant with non-expired KYC can publish to marketplace."""
        from datetime import timedelta
        tenant = _make_tenant()
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.status = TenantStatus.ACTIVE
        tenant.kyc_expires_at = timezone.now() + timedelta(days=30)
        tenant.save()
        self.assertTrue(tenant.can_publish_to_marketplace())


class TenantPlanModelTest(TestCase):
    """Test TenantPlan model"""

    def test_create_tenant_plan(self):
        """Test tenant plan creation"""
        uid = uuid.uuid4().hex[:8]
        plan = TenantPlan.objects.create(
            name=f"Create Test Plan {uid}",
            slug=f"create-test-{uid}",
            tier=PlanTier.FREE,
            limits_json={"max_assets": 10, "max_api_calls_per_month": 10000},
        )

        self.assertIn("Create Test Plan", plan.name)
        self.assertIn("create-test-", plan.slug)
        self.assertEqual(plan.tier, PlanTier.FREE)
        self.assertEqual(plan.limits_json["max_assets"], 10)
        self.assertTrue(plan.is_active)

    def test_plan_get_limit(self):
        """Test get_limit method"""
        uid = uuid.uuid4().hex[:8]
        plan, _ = TenantPlan.objects.get_or_create(
            slug="pro",
            defaults={
                "name": "Pro Plan",
                "tier": PlanTier.PRO,
                "limits_json": {"max_assets": 100},
            },
        )

        self.assertEqual(plan.get_limit("max_assets"), 100)
        self.assertIsNone(plan.get_limit("nonexistent_limit"))
        self.assertEqual(plan.get_limit("nonexistent_limit", default=0), 0)

    def test_plan_tier_choices(self):
        """Test plan tier enum"""
        uid = uuid.uuid4().hex[:8]
        plan_free = TenantPlan.objects.create(
            name=f"Tier Free {uid}", slug=f"tier-free-{uid}", tier=PlanTier.FREE, limits_json={}
        )
        plan_pro = TenantPlan.objects.create(
            name=f"Tier Pro {uid}", slug=f"tier-pro-{uid}", tier=PlanTier.PRO, limits_json={}
        )
        plan_enterprise = TenantPlan.objects.create(
            name=f"Tier Ent {uid}", slug=f"tier-ent-{uid}", tier=PlanTier.ENTERPRISE, limits_json={}
        )

        self.assertEqual(plan_free.tier, PlanTier.FREE)
        self.assertEqual(plan_pro.tier, PlanTier.PRO)
        self.assertEqual(plan_enterprise.tier, PlanTier.ENTERPRISE)

    def test_plan_slug_uniqueness_failure(self):
        """Failure: duplicate plan slug raises IntegrityError."""
        uid = uuid.uuid4().hex[:8]
        TenantPlan(
            name=f"Plan 1 {uid}", slug=f"test-plan-{uid}",
            tier=PlanTier.FREE, limits_json={}
        ).save()
        with self.assertRaises(IntegrityError):
            TenantPlan(
                name=f"Plan 2 {uid}", slug=f"test-plan-{uid}",
                tier=PlanTier.PRO, limits_json={}
            ).save()

    def test_plan_name_uniqueness_failure(self):
        """Failure: duplicate plan name raises IntegrityError."""
        uid = uuid.uuid4().hex[:8]
        TenantPlan(
            name=f"Test Plan {uid}", slug=f"test-1-{uid}",
            tier=PlanTier.FREE, limits_json={}
        ).save()
        with self.assertRaises(IntegrityError):
            TenantPlan(
                name=f"Test Plan {uid}", slug=f"test-2-{uid}",
                tier=PlanTier.PRO, limits_json={}
            ).save()

    def test_plan_get_limit_edge_case_default(self):
        """Edge case: get_limit with missing key returns default when provided."""
        uid = uuid.uuid4().hex[:8]
        plan = TenantPlan.objects.create(
            name=f"Edge {uid}", slug=f"edge-{uid}", tier=PlanTier.FREE, limits_json={"max_assets": 5}
        )
        self.assertIsNone(plan.get_limit("unknown"))
        self.assertEqual(plan.get_limit("unknown", default=99), 99)
