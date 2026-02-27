"""
Base test classes for contracts tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


class ContractsTestBase(TestCase):
    """Base test class for contracts tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create services
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))


class ContractsTransactionTestBase(TransactionTestCase):
    """Base test class for contracts tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create services
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))


class ContractsAPITestBase(ContractsTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Active subscription required so TenantSuspensionMiddleware allows writes (POST/PATCH/DELETE).
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class ContractsAPITransactionTestBase(ContractsTransactionTestBase):
    """Base test class for API tests requiring TransactionTestCase with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Active subscription required so TenantSuspensionMiddleware allows writes (POST/PATCH/DELETE).
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
