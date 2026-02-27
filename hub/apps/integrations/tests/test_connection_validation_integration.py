"""
Integration tests for connection validation rules with GovernanceService and TenantService.

Tests integration with real services (no mocks/stubs), following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.db.utils import InterfaceError as DjangoInterfaceError, OperationalError
from django.test import TransactionTestCase

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.governance.services import GovernanceService
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.tenants.services import TenantService
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _is_connection_closed_error(exc: BaseException) -> bool:
    """True if the exception indicates the DB connection was closed (any backend or wrapper)."""
    msg = str(exc).lower()
    return "connection" in msg and "closed" in msg


def _ensure_db_connection():
    """Ensure default DB connection is open so setUp never sees 'connection already closed'."""
    try:
        connections.close_all()
        connection.ensure_connection()
    except Exception:
        pass


def _ensure_db_connection_for_teardown():
    """Ensure connection for tearDown/flush without closing first (avoid breaking active connection)."""
    try:
        connection.ensure_connection()
    except Exception:
        try:
            connections.close_all()
            connection.ensure_connection()
        except Exception:
            pass


class ConnectionValidationGovernanceIntegrationTest(TransactionTestCase):
    """
    Integration tests for connection validation with GovernanceService.

    Uses TransactionTestCase; tearDown ensures connection is open before super().tearDown()
    to avoid 'connection already closed' during flush in batched runs.
    """

    def setUp(self):
        """Set up test fixtures; retry up to 3 times on connection closed."""
        _ensure_db_connection()
        last_error = None
        for _ in range(3):
            try:
                self._create_fixtures()
                last_error = None
                break
            except (DjangoInterfaceError, OperationalError) as e:
                last_error = e
                if _is_connection_closed_error(e):
                    _ensure_db_connection()
                    continue
                raise
            except Exception as e:
                if _is_connection_closed_error(e):
                    last_error = e
                    _ensure_db_connection()
                    continue
                raise
        if last_error is not None:
            raise last_error

    def _create_fixtures(self):
        """Create tenant, user, rules, and roles. Unique slug per run to avoid collisions."""
        slug_suffix = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
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

    def tearDown(self):
        """Ensure connection then run TransactionTestCase teardown (flush); retry on connection closed."""
        last_err = None
        for _ in range(3):
            try:
                _ensure_db_connection_for_teardown()
                super().tearDown()
                last_err = None
                break
            except (DjangoInterfaceError, OperationalError) as e:
                last_err = e
                if _is_connection_closed_error(e):
                    continue
                raise
            except Exception as e:
                if _is_connection_closed_error(e):
                    last_err = e
                    continue
                raise
        if last_err is not None:
            raise last_err

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

    @pytest.mark.timeout(600)  # TransactionTestCase + GovernanceService can exceed 300s under batch load
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
            email="platform@example.com",
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


class ConnectionValidationTenantServiceIntegrationTest(TransactionTestCase):
    """
    Integration tests for connection validation with TenantService.

    Uses TransactionTestCase; tearDown ensures connection is open before super().tearDown().
    """

    def setUp(self):
        """Set up test fixtures; retry up to 3 times on connection closed."""
        _ensure_db_connection()
        last_error = None
        for _ in range(3):
            try:
                self._create_fixtures()
                last_error = None
                break
            except (DjangoInterfaceError, OperationalError) as e:
                last_error = e
                if _is_connection_closed_error(e):
                    _ensure_db_connection()
                    continue
                raise
            except Exception as e:
                if _is_connection_closed_error(e):
                    last_error = e
                    _ensure_db_connection()
                    continue
                raise
        if last_error is not None:
            raise last_error

    def _create_fixtures(self):
        """Create tenant, user, rules, role, and user-role. Unique slug per run to avoid collisions."""
        slug_suffix = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
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

    def tearDown(self):
        """Ensure connection then run TransactionTestCase teardown; retry on connection closed."""
        last_err = None
        for _ in range(3):
            try:
                _ensure_db_connection_for_teardown()
                super().tearDown()
                last_err = None
                break
            except (DjangoInterfaceError, OperationalError) as e:
                last_err = e
                if _is_connection_closed_error(e):
                    continue
                raise
            except Exception as e:
                if _is_connection_closed_error(e):
                    last_err = e
                    continue
                raise
        if last_err is not None:
            raise last_err

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
            name="Unverified Tenant",
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
            user_id=None, tenant_id=str(self.tenant.id)  # type: ignore[arg-type]
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id), tenant_id=None  # type: ignore[arg-type]
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
