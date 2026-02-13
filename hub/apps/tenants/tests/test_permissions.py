"""
Unit tests for tenant permissions.

Uses real User model (no mocks/stubs).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.tenants.permissions import CanPublishToMarketplace, IsPlatformAdmin
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantPermissionsTest(TestCase):
    """Test tenant permission classes with real User."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="test",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="test",
            tenant=self.tenant,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_is_platform_admin_permission(self):
        """IsPlatformAdmin: platform admin has permission, regular user does not."""
        permission = IsPlatformAdmin()
        request = self.factory.get("/api/v1/tenants/")
        request.user = self.admin_user
        self.assertTrue(permission.has_permission(request, None))
        request.user = self.regular_user
        self.assertFalse(permission.has_permission(request, None))

    def test_can_publish_to_marketplace_permission(self):
        """Test CanPublishToMarketplace permission"""
        permission = CanPublishToMarketplace()

        # Unverified tenant
        request = self.factory.get("/api/v1/marketplace/listings/")
        request.tenant = self.tenant

        self.assertFalse(permission.has_permission(request, None))

        # Verified tenant
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save()
        request.tenant = self.tenant

        self.assertTrue(permission.has_permission(request, None))

        # Suspended verified tenant
        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save()
        request.tenant = self.tenant

        self.assertFalse(permission.has_permission(request, None))
