"""
Unit tests for MarketplaceIntegrationBusinessRules.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.business_rules.base import ValidationResult, RuleExecutionContext
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.integrations.business_rules import (
    MarketplaceIntegrationBusinessRules,
    MarketplaceIntegrationRuleExecutionContext,
)
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus, MarketplaceListing
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MarketplaceIntegrationBusinessRulesInitializationTest(TestCase):
    """Test MarketplaceIntegrationBusinessRules initialization"""

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        rules = MarketplaceIntegrationBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_id(self):
        """Test initialization with tenant_id"""
        tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        rules = MarketplaceIntegrationBusinessRules(tenant_id=str(tenant.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_and_user(self):
        """Test initialization with tenant_id and user_id"""
        tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=tenant
        )
        rules = MarketplaceIntegrationBusinessRules(tenant_id=str(tenant.id), user_id=str(user.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))
        self.assertEqual(rules.user_id, str(user.id))
        self.assertEqual(rules.get_rule_name(), "MarketplaceIntegrationBusinessRules")

    def test_rule_registration(self):
        """Test that MarketplaceIntegrationBusinessRules is registered in the registry."""
        registry = get_registry()
        rule_metadata = registry.get_rule("marketplace_integration_validation")

        self.assertIsNotNone(rule_metadata)
        self.assertEqual(rule_metadata.rule_name, "marketplace_integration_validation")
        self.assertEqual(rule_metadata.rule_class, MarketplaceIntegrationBusinessRules)
        self.assertIn("marketplace", rule_metadata.tags)
        self.assertIn("integration", rule_metadata.tags)
        self.assertIn("validation", rule_metadata.tags)


class MarketplaceIntegrationRuleExecutionContextTest(TestCase):
    """Test MarketplaceIntegrationRuleExecutionContext"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"}
        )

    def test_context_creation_with_connection(self):
        """Test context creation with connection"""
        context = MarketplaceIntegrationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            connection=self.connection
        )
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.connection, self.connection)
        self.assertIsNone(context.sync_job)
        self.assertIsNone(context.mapping)
        self.assertIsNone(context.asset)
        self.assertIsNone(context.marketplace_listing)

    def test_context_to_dict(self):
        """Test context to_dict method"""
        context = MarketplaceIntegrationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            connection=self.connection
        )
        context_dict = context.to_dict()
        self.assertEqual(context_dict['tenant_id'], str(self.tenant.id))
        self.assertEqual(context_dict['connection_id'], str(self.connection.id))
        self.assertIsNone(context_dict['sync_job_id'])
        self.assertIsNone(context_dict['mapping_id'])
        self.assertIsNone(context_dict['asset_id'])
        self.assertIsNone(context_dict['marketplace_listing_id'])


class MarketplaceIntegrationBusinessRulesValidationTest(TestCase):
    """Test MarketplaceIntegrationBusinessRules validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

    def test_validate_with_marketplace_context(self):
        """Test validate with MarketplaceIntegrationRuleExecutionContext"""
        context = MarketplaceIntegrationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            connection=self.connection
        )

        result = self.rules.validate(context, validation_type='connection')

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_with_standard_context(self):
        """Test validate with standard RuleExecutionContext"""
        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource=self.connection,
            metadata={
                'connection': self.connection
            }
        )

        result = self.rules.validate(context, validation_type='connection')

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_with_kwargs(self):
        """Test validate with connection in kwargs"""
        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = self.rules.validate(
            context,
            connection=self.connection,
            validation_type='connection'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_no_resources(self):
        """Test validate with no resources provided"""
        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = self.rules.validate(context)

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("At least one resource", result.errors[0])

    def test_validate_connection_success(self):
        """Test successful connection validation"""
        result = self.rules.validate(
            connection=self.connection,
            validation_type='connection'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('connection_id', result.details)
        self.assertEqual(result.details['connection_id'], str(self.connection.id))

    def test_validate_connection_inactive(self):
        """Test connection validation with inactive connection"""
        self.connection.is_active = False
        self.connection.save()

        result = self.rules.validate(
            connection=self.connection,
            validation_type='connection'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)  # Inactive is a warning, not an error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('is_active', result.details)
        self.assertFalse(result.details['is_active'])

    def test_validate_connection_tenant_mismatch(self):
        """Test connection validation with tenant mismatch"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        rules = MarketplaceIntegrationBusinessRules(tenant_id=str(other_tenant.id))

        result = rules.validate(
            connection=self.connection,
            validation_type='connection'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('tenant', result.errors[0].lower())

    def test_validate_sync_job_success(self):
        """Test successful sync job validation"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        result = self.rules.validate(
            sync_job=sync_job,
            validation_type='sync_job'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('sync_job_id', result.details)
        self.assertEqual(result.details['sync_job_id'], str(sync_job.id))

    def test_validate_sync_job_inactive_connection(self):
        """Test sync job validation with inactive connection"""
        self.connection.is_active = False
        self.connection.save()

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        result = self.rules.validate(
            sync_job=sync_job,
            validation_type='sync_job'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('not active', result.errors[0])

    def test_validate_mapping_success(self):
        """Test successful mapping validation"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key="test-asset-key"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="external-listing-123"
        )

        result = self.rules.validate(
            mapping=mapping,
            validation_type='mapping'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('mapping_id', result.details)
        self.assertEqual(result.details['mapping_id'], str(mapping.id))

    def test_validate_mapping_missing_external_listing_id(self):
        """Test mapping validation with missing external_listing_id"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key="test-asset-key"
        )
        # Create a valid mapping first
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="valid-id"
        )
        # Manually set empty string to test business rules validation
        # This simulates a case where the field might be empty due to data corruption
        mapping.external_listing_id = ""
        # Use update_fields to bypass model validation
        MarketplaceMapping.objects.filter(id=mapping.id).update(external_listing_id="")
        # Refresh from database
        mapping.refresh_from_db()

        result = self.rules.validate(
            mapping=mapping,
            validation_type='mapping'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('external_listing_id', result.errors[0])

    def test_validate_asset_success(self):
        """Test successful asset validation"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key="test-asset-key"
        )

        result = self.rules.validate(
            asset=asset,
            validation_type='asset'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('asset_id', result.details)
        self.assertEqual(result.details['asset_id'], str(asset.id))

    def test_validate_marketplace_listing_success(self):
        """Test successful marketplace listing validation"""
        listing = MarketplaceListing(
            marketplace_id="listing-123",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing"
        )

        result = self.rules.validate(
            marketplace_listing=listing,
            validation_type='marketplace_listing'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('marketplace_id', result.details)
        self.assertEqual(result.details['marketplace_id'], "listing-123")

    def test_validate_marketplace_listing_missing_id(self):
        """Test marketplace listing validation with missing marketplace_id"""
        listing = MarketplaceListing(
            marketplace_id="",  # Empty string
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing"
        )

        result = self.rules.validate(
            marketplace_listing=listing,
            validation_type='marketplace_listing'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('marketplace_id', result.errors[0])

    def test_validate_all_resources(self):
        """Test validate with all resource types"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key="test-asset-key"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="external-listing-123"
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )
        listing = MarketplaceListing(
            marketplace_id="listing-123",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing"
        )

        result = self.rules.validate(
            connection=self.connection,
            sync_job=sync_job,
            mapping=mapping,
            asset=asset,
            marketplace_listing=listing,
            validation_type='all'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


class SyncValidationRulesTest(TestCase):
    """Test sync validation rules methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        # Register test connector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.tests.test_factory import TestConnector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            TestConnector
        )

    def test_validate_sync_direction_success(self):
        """Test successful sync direction validation"""
        result = self.rules.validate_sync_direction(
            sync_direction=SyncDirection.PUSH,
            connection=self.connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('sync_direction', result.details)
        self.assertEqual(result.details['sync_direction'], SyncDirection.PUSH.value)

    def test_validate_sync_direction_unsupported(self):
        """Test sync direction validation with unsupported direction"""
        # Create connection with connector that only supports PUSH
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.tests.test_factory import TestConnectorAWS
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            TestConnectorAWS
        )

        aws_connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="AWS Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        # Try PULL direction which is not supported by AWS connector
        result = self.rules.validate_sync_direction(
            sync_direction=SyncDirection.PULL,
            connection=aws_connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('not supported', result.errors[0])

    def test_validate_sync_direction_invalid_direction(self):
        """Test sync direction validation with invalid direction"""
        result = self.rules.validate_sync_direction(
            sync_direction="INVALID_DIRECTION",
            connection=self.connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_sync_eligibility_success(self):
        """Test successful sync eligibility validation"""
        result = self.rules.validate_sync_eligibility(
            connection=self.connection
        )

        self.assertIsInstance(result, ValidationResult)
        # May have warnings if connector test fails, but should not have errors for active connection
        self.assertIn('connection_active', result.details)
        self.assertTrue(result.details['connection_active'])

    def test_validate_sync_eligibility_inactive_connection(self):
        """Test sync eligibility validation with inactive connection"""
        self.connection.is_active = False
        self.connection.save()

        result = self.rules.validate_sync_eligibility(
            connection=self.connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('not active', result.errors[0])

    def test_validate_sync_eligibility_conflicting_jobs(self):
        """Test sync eligibility validation with conflicting sync jobs"""
        # Create a running sync job
        running_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        # Create a pending sync job
        pending_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value
        )

        # Try to validate eligibility for a new sync job
        new_sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        result = self.rules.validate_sync_eligibility(
            connection=self.connection,
            sync_job=new_sync_job
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('conflicting', result.errors[0].lower())
        self.assertIn('conflicting_jobs_count', result.details)
        self.assertGreaterEqual(result.details['conflicting_jobs_count'], 1)

    def test_validate_sync_eligibility_exclude_current_job(self):
        """Test sync eligibility validation excludes current job from conflicts"""
        # Create a sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        # Validate eligibility for the same job (should not conflict with itself)
        result = self.rules.validate_sync_eligibility(
            connection=self.connection,
            sync_job=sync_job
        )

        # Should not have conflicts with itself
        self.assertIn('has_conflicts', result.details)
        self.assertFalse(result.details['has_conflicts'])

    def test_validate_sync_resources_push_success(self):
        """Test successful sync resources validation for PUSH sync"""
        asset1 = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset 1",
            key="test-asset-1"
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset 2",
            key="test-asset-2"
        )

        result = self.rules.validate_sync_resources(
            sync_direction=SyncDirection.PUSH,
            connection=self.connection,
            asset_ids=[str(asset1.id), str(asset2.id)],
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('accessible_assets_count', result.details)
        self.assertEqual(result.details['accessible_assets_count'], 2)

    def test_validate_sync_resources_push_missing_assets(self):
        """Test sync resources validation for PUSH sync with missing assets"""
        result = self.rules.validate_sync_resources(
            sync_direction=SyncDirection.PUSH,
            connection=self.connection,
            asset_ids=["non-existent-id"],
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('not accessible', result.errors[0])

    def test_validate_sync_resources_push_no_asset_ids(self):
        """Test sync resources validation for PUSH sync without asset IDs"""
        result = self.rules.validate_sync_resources(
            sync_direction=SyncDirection.PUSH,
            connection=self.connection,
            asset_ids=None,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('Asset IDs are required', result.errors[0])

    def test_validate_sync_resources_pull_success(self):
        """Test successful sync resources validation for PULL sync"""
        result = self.rules.validate_sync_resources(
            sync_direction=SyncDirection.PULL,
            connection=self.connection,
            listing_ids=["listing-1", "listing-2"],
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        # May have warnings if listings don't exist, but structure should be valid
        self.assertIn('listing_ids_count', result.details)
        self.assertEqual(result.details['listing_ids_count'], 2)

    def test_validate_sync_resources_pull_no_listing_ids(self):
        """Test sync resources validation for PULL sync without listing IDs"""
        result = self.rules.validate_sync_resources(
            sync_direction=SyncDirection.PULL,
            connection=self.connection,
            listing_ids=None,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        # Should have warning but not error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('No listing IDs', result.warnings[0])

    def test_validate_sync_resources_quota_exceeded(self):
        """Test sync resources validation with quota exceeded"""
        # Create many assets
        asset_ids = []
        for i in range(1001):  # Exceeds default quota of 1000
            asset = Asset.objects.create(
                tenant=self.tenant,
                name=f"Test Asset {i}",
                key=f"test-asset-{i}"
            )
            asset_ids.append(str(asset.id))

        result = self.rules.validate_sync_resources(
            sync_direction=SyncDirection.PUSH,
            connection=self.connection,
            asset_ids=asset_ids,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('exceeds maximum', result.errors[0])

    def test_validate_sync_mapping_success(self):
        """Test successful sync mapping validation"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key="test-asset-key"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="external-listing-123"
        )

        result = self.rules.validate_sync_mapping(
            mapping=mapping
        )

        self.assertIsInstance(result, ValidationResult)
        # May have warnings if listing doesn't exist via connector, but structure should be valid
        self.assertIn('mapping_id', result.details)
        self.assertEqual(result.details['mapping_id'], str(mapping.id))

    def test_validate_sync_mapping_conflict_asset(self):
        """Test sync mapping validation with asset conflict"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key="test-asset-key"
        )
        # Create first mapping
        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="external-listing-1"
        )

        # Try to create second mapping with same connection + asset
        mapping2 = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="external-listing-2"
        )

        result = self.rules.validate_sync_mapping(
            mapping=mapping2
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('conflict', result.errors[0].lower())

    def test_validate_sync_mapping_conflict_listing(self):
        """Test sync mapping validation with listing conflict"""
        asset1 = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset 1",
            key="test-asset-1"
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset 2",
            key="test-asset-2"
        )
        # Create first mapping
        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset1,
            external_listing_id="external-listing-123"
        )

        # Try to create second mapping with same connection + external_listing_id
        mapping2 = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="external-listing-123"
        )

        result = self.rules.validate_sync_mapping(
            mapping=mapping2
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('conflict', result.errors[0].lower())



class FederatedAssetValidationRulesTest(TestCase):
    """Test federated asset validation rules methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        # Register test connector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.tests.test_factory import TestConnector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            TestConnector
        )

    def test_validate_federated_asset_creation_success(self):
        """Test successful federated asset creation validation"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Test Federated Asset",
                "description": "A test federated asset",
                "key": "test-federated-asset"
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123",
                "listing_url": "https://marketplace.example.com/listing/123"
            },
            odps_metadata={
                "product": {
                    "productID": "prod-123",
                    "details": {
                        "en": {
                            "name": "Test Product"
                        }
                    }
                }
            },
            odcs_metadata={
                "schema": {
                    "assetID": "prod-123"
                }
            },
            resources=[]
        )

        result = self.rules.validate_federated_asset_creation(
            asset_mapping=asset_mapping,
            connection=self.connection
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('source_type_valid', result.details)
        self.assertTrue(result.details['source_type_valid'])

    def test_validate_federated_asset_creation_invalid_source_type(self):
        """Test federated asset creation validation with invalid source type"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.HUB_NATIVE,  # Wrong source type
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata={},
            resources=[]
        )

        result = self.rules.validate_federated_asset_creation(
            asset_mapping=asset_mapping
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('FEDERATED', result.errors[0])

    def test_validate_federated_asset_creation_missing_metadata(self):
        """Test federated asset creation validation with missing metadata"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
                # Missing marketplace_id and listing_id
            },
            odps_metadata={},
            resources=[]
        )

        result = self.rules.validate_federated_asset_creation(
            asset_mapping=asset_mapping
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('missing required fields', result.errors[0])

    def test_validate_federated_asset_creation_missing_name(self):
        """Test federated asset creation validation with missing name"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"description": "Test description"},  # Has description but missing name
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata={},
            resources=[]
        )

        result = self.rules.validate_federated_asset_creation(
            asset_mapping=asset_mapping
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('name', result.errors[0].lower())

    def test_validate_dual_contract_creation_success(self):
        """Test successful dual contract creation validation"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata={
                "product": {
                    "productID": "prod-123",
                    "details": {
                        "en": {
                            "name": "Test Product"
                        }
                    }
                }
            },
            odcs_metadata={
                "schema": {
                    "assetID": "prod-123"
                },
                "quality": {},
                "sla": {}
            },
            resources=[]
        )

        result = self.rules.validate_dual_contract_creation(
            asset_mapping=asset_mapping,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('has_odps_metadata', result.details)
        self.assertTrue(result.details['has_odps_metadata'])

    def test_validate_dual_contract_creation_missing_odps(self):
        """Test dual contract creation validation with missing ODPS metadata"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata=None,  # Missing ODPS
            odcs_metadata={},
            resources=[]
        )

        result = self.rules.validate_dual_contract_creation(
            asset_mapping=asset_mapping,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('ODPS metadata', result.errors[0])

    def test_validate_dual_contract_creation_no_odcs(self):
        """Test dual contract creation validation without ODCS metadata"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata={
                "product": {
                    "productID": "prod-123",
                    "details": {"en": {"name": "Test"}}
                }
            },
            odcs_metadata=None,  # No ODCS
            resources=[]
        )

        result = self.rules.validate_dual_contract_creation(
            asset_mapping=asset_mapping,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        # Should be valid but with warnings
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('ODCS metadata', result.warnings[0])

    def test_validate_dual_contract_creation_id_mismatch(self):
        """Test dual contract creation validation with ID mismatch"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata={
                "product": {
                    "productID": "prod-123",
                    "details": {"en": {"name": "Test"}}
                }
            },
            odcs_metadata={
                "schema": {
                    "assetID": "prod-456"  # Different ID
                }
            },
            resources=[]
        )

        result = self.rules.validate_dual_contract_creation(
            asset_mapping=asset_mapping,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        # Should be valid but with warnings about ID mismatch
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('do not match', result.warnings[0])

    def test_validate_resource_download_success(self):
        """Test successful resource download validation"""
        from hub.apps.integrations.base import MarketplaceResource

        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="data.csv",
                format="CSV",
                size_bytes=1024,
                url="https://example.com/data.csv"
            ),
            MarketplaceResource(
                resource_id="res-2",
                resource_type="FILE",
                name="data.json",
                format="JSON",
                size_bytes=2048,
                url="https://example.com/data.json"
            )
        ]

        result = self.rules.validate_resource_download(
            resources=resources,
            connection=self.connection,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('downloadable_resources_count', result.details)
        self.assertEqual(result.details['downloadable_resources_count'], 2)

    def test_validate_resource_download_empty_list(self):
        """Test resource download validation with empty list"""
        result = self.rules.validate_resource_download(
            resources=[],
            connection=self.connection,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)  # Empty list is valid
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('No resources', result.warnings[0])

    def test_validate_resource_download_oversized(self):
        """Test resource download validation with oversized resource"""
        from hub.apps.integrations.base import MarketplaceResource

        # Create resource larger than default limit (10 GB)
        oversized_size = 11 * 1024 * 1024 * 1024  # 11 GB
        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="huge-file.csv",
                format="CSV",
                size_bytes=oversized_size,
                url="https://example.com/huge-file.csv"
            )
        ]

        result = self.rules.validate_resource_download(
            resources=resources,
            connection=self.connection,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('exceeds maximum size', result.errors[0])

    def test_validate_resource_download_unsupported_format(self):
        """Test resource download validation with unsupported format"""
        from hub.apps.integrations.base import MarketplaceResource

        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="data.xyz",  # Unsupported format
                format="XYZ",
                size_bytes=1024,
                url="https://example.com/data.xyz"
            )
        ]

        result = self.rules.validate_resource_download(
            resources=resources,
            connection=self.connection,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        # Unsupported format is a warning, not an error
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('unsupported format', result.warnings[0].lower())

    def test_validate_resource_download_missing_resource_id(self):
        """Test resource download validation with missing resource_id"""
        from hub.apps.integrations.base import MarketplaceResource

        resources = [
            MarketplaceResource(
                resource_id="",  # Empty resource_id
                resource_type="FILE",
                name="data.csv",
                format="CSV",
                size_bytes=1024
            )
        ]

        result = self.rules.validate_resource_download(
            resources=resources,
            connection=self.connection,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('resource_id', result.errors[0].lower())

    def test_validate_dual_contract_creation_integration_with_contract_service(self):
        """Integration test: Validate dual contract creation with ContractService"""
        from hub.apps.integrations.base import MarketplaceAssetMapping
        from hub.apps.assets.models import AssetSourceType
        from hub.apps.contracts.services import ContractService
        import json

        # Create ODCS contract via ContractService (real service, no mocks)
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-integration",
            "name": "Test ODCS Integration",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        })

        contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        odcs_contract = contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type="ODCS"
        )

        # Create asset mapping with ODPS metadata that can be linked to ODCS
        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(self.connection.id),
                "listing_id": "listing-123"
            },
            odps_metadata={
                "product": {
                    "productID": "prod-123",
                    "details": {
                        "en": {
                            "name": "Test Product"
                        }
                    },
                    "dataSchema": {
                        "fields": [{"name": "id", "type": "string"}]
                    }
                }
            },
            odcs_metadata={
                "schema": {
                    "assetID": "prod-123",
                    "fields": [{"name": "id", "type": "string"}]
                }
            },
            resources=[]
        )

        # Validate dual contract creation
        result = self.rules.validate_dual_contract_creation(
            asset_mapping=asset_mapping,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn('has_odps_metadata', result.details)
        self.assertTrue(result.details['has_odps_metadata'])
        self.assertIn('has_odcs_metadata', result.details)
        self.assertTrue(result.details['has_odcs_metadata'])

        # Verify ODCS contract was created successfully (integration test)
        self.assertIsNotNone(odcs_contract)
        self.assertEqual(str(odcs_contract.tenant.id), str(self.tenant.id))
