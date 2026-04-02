"""
Base test classes for datasets tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.datasets.services import DatasetService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


class DatasetsTestBase(TestCase):
    """Base test class for datasets tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        uid = str(uuid.uuid4())[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create service
        self.service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )


class DatasetsTransactionTestBase(TestCase):
    """Base test class for datasets tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        uid = str(uuid.uuid4())[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create service
        self.service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )


class DatasetsAPITestBase(DatasetsTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Ensure tenant has active subscription so TenantSuspensionMiddleware allows writes (POST/PUT/PATCH/DELETE)
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class DatasetsAPITransactionTestBase(DatasetsTransactionTestBase):
    """Base test class for API tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Ensure tenant has active subscription so TenantSuspensionMiddleware allows writes (POST/PUT/PATCH/DELETE)
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
