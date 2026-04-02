"""
Base test classes for files tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.services import FileService
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


def _ensure_tenant_has_active_subscription(tenant):
    """
    Ensure the tenant has an active subscription so write operations
    (POST/PUT/PATCH/DELETE) are allowed by TenantSuspensionMiddleware
    (hub.apps.tenants.middleware; Phase 25.2.4 subscription check).
    Used by API test bases that hit the full request stack. No mocks.
    """
    from hub.apps.billing.models import Subscription, SubscriptionStatus

    plan, _ = TenantPlan.objects.get_or_create(
        slug="files-test-plan",
        defaults={
            "name": "Files Test Plan",
            "tier": PlanTier.PRO,
            "limits_json": {"max_assets": 100, "max_storage_gb": 1000},
            "is_active": True,
        },
    )
    # Ensure the plan has max_storage_gb (handles pre-existing rows
    # created before this limit was added to the test plan).
    if "max_storage_gb" not in (plan.limits_json or {}):
        plan.limits_json = {**(plan.limits_json or {}), "max_storage_gb": 1000}
        plan.save(update_fields=["limits_json"])

    # Assign the plan directly on the tenant FK so that
    # PlanLimitService.check_limit() finds it via tenant.plan
    if tenant.plan_id != plan.id:
        tenant.plan = plan
        tenant.save(update_fields=["plan"])

    subscription = (
        Subscription.objects.filter(tenant_id=tenant.id).order_by("-created_at").first()
    )
    if not subscription or subscription.status not in (
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.TRIAL,
    ):
        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now(),
        )


class FilesTestBase(TestCase):
    """Base test class for files tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Ensure tenant has active subscription with storage limits
        # (required because FileService.create_file enforces plan limits)
        _ensure_tenant_has_active_subscription(self.tenant)

        # Create service
        self.service = FileService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )


class FilesTransactionTestBase(TestCase):
    """Base test class for files tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Ensure tenant has active subscription with storage limits
        _ensure_tenant_has_active_subscription(self.tenant)

        # Create service
        self.service = FileService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )


class FilesAPITestBase(FilesTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        _ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class FilesAPITransactionTestBase(FilesTransactionTestBase):
    """Base test class for API tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        _ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
