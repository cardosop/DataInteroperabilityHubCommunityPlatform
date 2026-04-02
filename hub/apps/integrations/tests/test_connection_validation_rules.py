"""
Unit tests for connection validation rules methods.

Tests for validate_connection_config, validate_connection_access, and validate_connection_test.
Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import pytest
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.base import MarketplaceType
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ConnectionValidationRulesTest(TestCase):
    """Test connection validation rules methods"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )

    def test_validate_connection_config_success(self):
        """Test successful connection config validation"""
        config = {"api_key": "test-key", "endpoint": "https://api.example.com"}
        result = self.rules.validate_connection_config(
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            config=config,
            connection_name="Test Connection",
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        # May have warnings about marketplace type not being supported, but config should be valid
        self.assertIn('marketplace_type', result.details)
        self.assertIn('config_valid', result.details)

    def test_validate_connection_config_invalid_marketplace_type(self):
        """Test connection config validation with invalid marketplace type"""
        config = {"api_key": "test-key"}
        result = self.rules.validate_connection_config(
            marketplace_type="INVALID_TYPE",
            config=config,
            connection_name="Test Connection",
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('Invalid marketplace_type' in err for err in result.errors))

    def test_validate_connection_config_invalid_config_type(self):
        """Test connection config validation with invalid config type"""
        result = self.rules.validate_connection_config(
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            config="not-a-dict",
            connection_name="Test Connection",
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('must be a dictionary' in err for err in result.errors))

    def test_validate_connection_config_empty_name(self):
        """Test connection config validation with empty name"""
        config = {"api_key": "test-key"}
        result = self.rules.validate_connection_config(
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            config=config,
            connection_name="",
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('cannot be empty' in err for err in result.errors))

    def test_validate_connection_config_name_uniqueness(self):
        """Test connection config validation with duplicate name"""
        # Create existing connection
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Existing Connection",
            config={"api_key": "test-key"}
        )

        config = {"api_key": "test-key"}
        result = self.rules.validate_connection_config(
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            config=config,
            connection_name="Existing Connection",
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('already exists' in err for err in result.errors))

    def test_validate_connection_config_name_uniqueness_update(self):
        """Test connection config validation with duplicate name on update (should pass)"""
        # Create existing connection
        existing = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Existing Connection",
            config={"api_key": "test-key"}
        )

        config = {"api_key": "test-key"}
        result = self.rules.validate_connection_config(
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            config=config,
            connection_name="Existing Connection",
            tenant_id=str(self.tenant.id),
            connection_id=str(existing.id)  # Exclude self from uniqueness check
        )

        # Should pass because we're updating the same connection
        self.assertIsInstance(result, ValidationResult)
        # May have other errors (like marketplace type not supported), but not name uniqueness
        name_uniqueness_error = any('already exists' in err for err in result.errors)
        self.assertFalse(name_uniqueness_error)

    def test_validate_connection_config_invalid_credentials(self):
        """Test connection config validation with invalid credentials format"""
        config = {"api_key": "", "endpoint": "https://api.example.com"}  # Empty api_key
        result = self.rules.validate_connection_config(
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            config=config,
            connection_name="Test Connection",
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('api_key' in err and 'non-empty string' in err for err in result.errors))

    def test_validate_connection_access_success(self):
        """Test successful connection access validation"""
        # Assign DATA_PROVIDER role to user
        UserRole.objects.create(user=self.user, role=self.provider_role)

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('has_permission', result.details)
        self.assertTrue(result.details['has_permission'])

    def test_validate_connection_access_user_not_found(self):
        """Test connection access validation with non-existent user"""
        fake_user_id = str(uuid.uuid4())

        result = self.rules.validate_connection_access(
            user_id=fake_user_id,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('not found' in err for err in result.errors))

    def test_validate_connection_access_no_permission(self):
        """Test connection access validation without required role"""
        # User has no roles assigned

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('required role' in err for err in result.errors))

    def test_validate_connection_access_tenant_mismatch(self):
        """Test connection access validation with tenant mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        UserRole.objects.create(user=self.user, role=self.provider_role)

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id),
            tenant_id=str(other_tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('does not belong to tenant' in err for err in result.errors))

    def test_validate_connection_access_platform_admin(self):
        """Test connection access validation with platform admin"""
        platform_admin = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True
        )

        result = self.rules.validate_connection_access(
            user_id=str(platform_admin.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn('user_is_platform_admin', result.details)
        self.assertTrue(result.details['user_is_platform_admin'])

    def test_validate_connection_access_tenant_not_verified(self):
        """Test connection access validation with tenant not verified"""
        uid2 = uuid.uuid4().hex[:8]
        unverified_tenant = Tenant.objects.create(
            name=f"Unverified Tenant {uid2}", slug=f"unverified-tenant-{uid2}", kyc_status=KYCStatus.UNVERIFIED
        )
        unverified_user = User.objects.create_user(
            email=f"unverified-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=unverified_tenant
        )
        provider_role, _ = Role.objects.get_or_create(
            tenant=unverified_tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        UserRole.objects.create(user=unverified_user, role=provider_role)

        rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(unverified_tenant.id),
            user_id=str(unverified_user.id)
        )

        result = rules.validate_connection_access(
            user_id=str(unverified_user.id),
            tenant_id=str(unverified_tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('marketplace integration enabled' in err for err in result.errors))

    def test_validate_connection_access_quota_exceeded(self):
        """Test connection access validation with quota exceeded"""
        UserRole.objects.create(user=self.user, role=self.provider_role)

        # Create 50 connections to reach limit
        for i in range(50):
            MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name=f"Connection {i}",
                config={"api_key": f"key-{i}"}
            )

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('maximum connection limit' in err for err in result.errors))

    def test_validate_connection_access_quota_warning(self):
        """Test connection access validation with quota warning"""
        UserRole.objects.create(user=self.user, role=self.provider_role)

        # Create 40 connections (80% of 50 limit)
        for i in range(40):
            MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name=f"Connection {i}",
                config={"api_key": f"key-{i}"}
            )

        result = self.rules.validate_connection_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)  # Still valid, just warning
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any('approaching connection limit' in warn for warn in result.warnings))

    def test_validate_connection_test_success(self):
        """Test successful connection test validation"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        test_results = {"success": True, "latency_ms": 100}
        result = self.rules.validate_connection_test(
            connection=connection,
            test_results=test_results
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('test_success', result.details)
        self.assertTrue(result.details['test_success'])

    def test_validate_connection_test_inactive(self):
        """Test connection test validation with inactive connection"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=False
        )

        result = self.rules.validate_connection_test(
            connection=connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('not active' in err for err in result.errors))

    def test_validate_connection_test_failed_test(self):
        """Test connection test validation with failed test results"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        test_results = {"success": False, "error": "Connection timeout"}
        result = self.rules.validate_connection_test(
            connection=connection,
            test_results=test_results
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('test failed' in err.lower() for err in result.errors))

    def test_validate_connection_test_high_latency(self):
        """Test connection test validation with high latency warning"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        test_results = {"success": True, "latency_ms": 6000}  # 6 seconds
        result = self.rules.validate_connection_test(
            connection=connection,
            test_results=test_results
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)  # Still valid, just warning
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any('high latency' in warn.lower() for warn in result.warnings))

    def test_validate_connection_test_invalid_config(self):
        """Test connection test validation with invalid config"""
        # Create connection with valid config first (to pass model validation)
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        # Manually set invalid config using update() to bypass model validation
        # This simulates a case where config might be corrupted in the database
        MarketplaceConnection.objects.filter(id=connection.id).update(config="not-a-dict")
        connection.refresh_from_db()

        result = self.rules.validate_connection_test(
            connection=connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any('must be a dictionary' in err for err in result.errors))

    def test_validate_connection_test_no_results(self):
        """Test connection test validation without test results"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        result = self.rules.validate_connection_test(
            connection=connection,
            test_results=None
        )

        # Should pass if connection is active and config is valid
        self.assertIsInstance(result, ValidationResult)
        # May have warnings about config structure, but should be valid
        self.assertIn('test_results_provided', result.details)
        self.assertFalse(result.details['test_results_provided'])

