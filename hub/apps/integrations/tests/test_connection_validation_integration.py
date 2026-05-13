"""
Integration tests for connection validation rules with GovernanceService and TenantService.

Tests integration with real services (no mocks/stubs), following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.governance.services import GovernanceService
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.tenants.services import TenantService
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db
User = get_user_model()


class ConnectionValidationGovernanceIntegrationTest(TestCase):
    """Integration tests for connection validation with GovernanceService."""

    def setUp(self):
        """Create tenant, user, rules, and roles. Unique slug per run to avoid collisions."""
        slug_suffix = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{slug_suffix}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{slug_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        self.rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )

    def test_validate_connection_access_with_governance_service_pattern(self):
        """
        Test that validate_connection_access follows the same permission pattern
        as GovernanceService.check_user_permissions_for_domain_creation
        """
        # Assign TENANT_ADMIN role (similar to domain creation requirement)
        UserRole.objects.create(user=self.user, role=self.admin_role)

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("has_permission", result.details)
        self.assertTrue(result.details["has_permission"])

        # Verify GovernanceService would also allow this
        governance_service = GovernanceService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        # Should not raise PermissionError
        try:
            governance_service.check_user_permissions_for_domain_creation(
                user_id=str(self.user.id), tenant_id=str(self.tenant.id)
            )
            permission_allowed = True
        except Exception:
            permission_allowed = False

        # Our validation should match GovernanceService behavior
        self.assertTrue(permission_allowed)

    def test_validate_connection_access_without_permission_governance_pattern(self):
        """
        Test that validate_connection_access correctly identifies missing permissions
        following GovernanceService pattern
        """
        # User has no roles assigned

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("required role" in err for err in result.errors))

        # Verify GovernanceService would also reject this
        governance_service = GovernanceService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        # Should raise PermissionError
        try:
            governance_service.check_user_permissions_for_domain_creation(
                user_id=str(self.user.id), tenant_id=str(self.tenant.id)
            )
            permission_allowed = True
        except Exception:
            permission_allowed = False

        # Our validation should match GovernanceService behavior
        self.assertFalse(permission_allowed)

    def test_validate_connection_access_platform_admin_governance_pattern(self):
        """
        Test that validate_connection_access correctly handles platform admins
        following GovernanceService pattern
        """
        platform_admin = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
        )

        result = self.rules.validate_connection_access(
            user_id=str(platform_admin.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("user_is_platform_admin", result.details)
        self.assertTrue(result.details["user_is_platform_admin"])

        # Verify GovernanceService also allows platform admins
        governance_service = GovernanceService(
            tenant_id=str(self.tenant.id), user_id=str(platform_admin.id)
        )
        # Should not raise PermissionError for platform admin
        try:
            governance_service.check_user_permissions_for_domain_creation(
                user_id=str(platform_admin.id), tenant_id=str(self.tenant.id)
            )
            permission_allowed = True
        except Exception:
            permission_allowed = False

        self.assertTrue(permission_allowed)


class ConnectionValidationTenantServiceIntegrationTest(TestCase):
    """Integration tests for connection validation with TenantService."""

    def setUp(self):
        """Create tenant, user, rules, role, and user-role."""
        slug_suffix = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-svc-{slug_suffix}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-svc-{slug_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        self.rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.create(user=self.user, role=self.provider_role)

    def test_validate_connection_access_tenant_service_integration(self):
        """
        Test that validate_connection_access integrates correctly with TenantService
        for tenant verification checks
        """
        # Verify tenant exists via TenantService
        tenant_service = TenantService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        tenant = tenant_service.get_tenant(str(self.tenant.id))

        # Our validation should check tenant.can_publish_to_marketplace()
        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("marketplace_integration_enabled", result.details)
        self.assertTrue(result.details["marketplace_integration_enabled"])

        # Verify tenant.can_publish_to_marketplace() matches our validation
        can_publish = tenant.can_publish_to_marketplace()
        self.assertTrue(can_publish)
        self.assertEqual(can_publish, result.details["marketplace_integration_enabled"])

    def test_validate_connection_access_unverified_tenant_tenant_service(self):
        """
        Test that validate_connection_access correctly identifies unverified tenants
        using TenantService pattern
        """
        uv_suffix = uuid.uuid4().hex[:8]
        unverified_tenant = Tenant.objects.create(
            name=f"Unverified Tenant {uv_suffix}",
            slug=f"unverified-tenant-{uv_suffix}",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        unverified_user = User.objects.create_user(
            email=f"unverified-{uv_suffix}@example.com",
            password="testpass123",
            tenant=unverified_tenant,
        )
        provider_role, _ = Role.objects.get_or_create(
            tenant=unverified_tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.create(user=unverified_user, role=provider_role)

        rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(unverified_tenant.id), user_id=str(unverified_user.id)
        )

        result = rules.validate_connection_access(
            user_id=str(unverified_user.id), tenant_id=str(unverified_tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("marketplace integration enabled" in err for err in result.errors))

        # Verify tenant.can_publish_to_marketplace() matches our validation
        tenant_service = TenantService(
            tenant_id=str(unverified_tenant.id), user_id=str(unverified_user.id)
        )
        tenant = tenant_service.get_tenant(str(unverified_tenant.id))
        can_publish = tenant.can_publish_to_marketplace()
        self.assertFalse(can_publish)
        self.assertEqual(can_publish, result.details["marketplace_integration_enabled"])

    def test_validate_connection_access_quota_with_tenant_service(self):
        """
        Test that validate_connection_access quota checking works correctly
        and can be extended to use TenantService for tenant-specific limits
        """
        # Create connections up to limit
        for i in range(50):
            MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name=f"Connection {i}",
                config={"api_key": f"key-{i}"},
            )

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("maximum connection limit" in err for err in result.errors))
        self.assertIn("current_connection_count", result.details)
        self.assertEqual(result.details["current_connection_count"], 50)

        # Verify TenantService can retrieve tenant (for future quota configuration)
        tenant_service = TenantService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        tenant = tenant_service.get_tenant(str(self.tenant.id))
        self.assertIsNotNone(tenant)
        # In future, tenant config could store max_connections_per_tenant

    def test_validate_connection_access_with_invalid_user_id(self):
        """Test error handling when user_id is invalid"""
        result = self.rules.validate_connection_access(
            user_id="invalid-user-id", tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_connection_access_with_invalid_tenant_id(self):
        """Test error handling when tenant_id is invalid"""
        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id="invalid-tenant-id"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_connection_access_with_none_values(self):
        """Test error handling when user_id or tenant_id is None"""
        result = self.rules.validate_connection_access(
            user_id=None, tenant_id=str(self.tenant.id)  # type: ignore[arg-type]  # test: edge-case type exercise
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=None  # type: ignore[arg-type]  # test: edge-case type exercise
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_connection_access_with_multiple_roles(self):
        """Test that multiple roles are handled correctly"""
        # Create additional role
        viewer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_VIEWER", defaults={"description": "Data Viewer"}
        )

        # Assign both roles (get_or_create to avoid duplicate key if already assigned)
        UserRole.objects.get_or_create(user=self.user, role=self.provider_role)
        UserRole.objects.get_or_create(user=self.user, role=viewer_role)

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
