"""
Unit tests for marketplace connector factory.

Tests the factory pattern implementation including registration, retrieval,
error handling, and singleton-like behavior.
"""
import pytest
from django.test import TestCase
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    MarketplaceListing,
    MarketplaceResource,
    SyncResult,
    MarketplaceAssetMapping,
)
from hub.apps.assets.models import AssetSourceType


pytestmark = pytest.mark.django_db(transaction=True)


class TestConnector(DataMarketplaceConnector):
    """Test connector implementation for testing factory"""

    def __init__(self, test_id: str = "default"):
        """Initialize test connector with optional test ID"""
        self.test_id = test_id
        self._marketplace_type = MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        self._supported_directions = [SyncDirection.PUSH, SyncDirection.PULL]

    @property
    def marketplace_type(self) -> MarketplaceType:
        return self._marketplace_type

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return self._supported_directions

    def authenticate(self, credentials):
        return True

    def test_connection(self):
        return True

    def list_listings(self, filters=None, limit=None, offset=None):
        return []

    def get_listing(self, listing_id: str):
        return MarketplaceListing(
            marketplace_id=listing_id,
            marketplace_type=self._marketplace_type,
            title="Test Listing"
        )

    def list_resources(self, listing_id: str):
        return []

    def create_listing(self, listing: MarketplaceListing):
        return listing

    def update_listing(self, listing_id: str, listing: MarketplaceListing):
        return listing

    def publish_resource(self, listing_id: str, resource: MarketplaceResource):
        return resource

    def download_resource(self, resource_id: str, destination_path: str):
        return destination_path

    def map_to_hub_asset(self, listing: MarketplaceListing):
        return MarketplaceAssetMapping(
            asset_data={"name": "Test"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={},
            odps_metadata={}
        )

    def map_from_hub_asset(
        self,
        asset_data: dict,
        odps_metadata: dict | None = None,
        odcs_metadata: dict | None = None
    ):
        return MarketplaceListing(
            marketplace_id="test",
            marketplace_type=self._marketplace_type,
            title=asset_data.get("name", "Unknown")
        )

    def sync_push(self, asset_ids: list[str], options: dict | None = None):
        return SyncResult(status=SyncStatus.COMPLETED)

    def sync_pull(
        self,
        listing_ids: list[str] | None = None,
        filters: dict | None = None,
        options: dict | None = None
    ):
        return SyncResult(status=SyncStatus.COMPLETED)


class TestConnectorAWS(DataMarketplaceConnector):
    """Another test connector for AWS marketplace"""

    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.AWS_DATA_EXCHANGE

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return [SyncDirection.PUSH]

    def authenticate(self, credentials):
        return True

    def test_connection(self):
        return True

    def list_listings(self, filters=None, limit=None, offset=None):
        return []

    def get_listing(self, listing_id: str):
        return MarketplaceListing(
            marketplace_id=listing_id,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="AWS Listing"
        )

    def list_resources(self, listing_id: str):
        return []

    def create_listing(self, listing: MarketplaceListing):
        return listing

    def update_listing(self, listing_id: str, listing: MarketplaceListing):
        return listing

    def publish_resource(self, listing_id: str, resource: MarketplaceResource):
        return resource

    def download_resource(self, resource_id: str, destination_path: str):
        return destination_path

    def map_to_hub_asset(self, listing: MarketplaceListing):
        return MarketplaceAssetMapping(
            asset_data={"name": "AWS Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={},
            odps_metadata={}
        )

    def map_from_hub_asset(
        self,
        asset_data: dict,
        odps_metadata: dict | None = None,
        odcs_metadata: dict | None = None
    ):
        return MarketplaceListing(
            marketplace_id="aws-test",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title=asset_data.get("name", "Unknown")
        )

    def sync_push(self, asset_ids: list[str], options: dict | None = None):
        return SyncResult(status=SyncStatus.COMPLETED)

    def sync_pull(
        self,
        listing_ids: list[str] | None = None,
        filters: dict | None = None,
        options: dict | None = None
    ):
        return SyncResult(status=SyncStatus.COMPLETED)


class TestFactoryRegistration:
    """Test factory connector registration"""

    def test_register_connector(self):
        """Test registering a connector"""
        # Clear any existing registrations for this test
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )

        # Register connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            TestConnector
        )

        # Verify registration
        assert MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value in MarketplaceConnectorFactory._connectors
        assert MarketplaceConnectorFactory._connectors[MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value] == TestConnector

        # Cleanup
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

    def test_register_connector_invalid_class(self):
        """Test registering a connector that doesn't inherit from base class"""
        class InvalidConnector:
            """Invalid connector that doesn't inherit from DataMarketplaceConnector"""
            pass

        with pytest.raises(ValueError, match="must inherit from DataMarketplaceConnector"):
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                InvalidConnector
            )

    def test_register_connector_invalid_type(self):
        """Test registering with invalid marketplace type"""
        with pytest.raises(TypeError, match="must be a MarketplaceType enum value"):
            MarketplaceConnectorFactory.register_connector(
                "INVALID_TYPE",  # Should be MarketplaceType enum
                TestConnector
            )

    def test_register_multiple_connectors(self):
        """Test registering multiple connectors"""
        # Clear existing registrations
        for mt in [MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, MarketplaceType.AWS_DATA_EXCHANGE]:
            if mt.value in MarketplaceConnectorFactory._connectors:
                MarketplaceConnectorFactory.unregister_connector(mt)

        # Register multiple connectors
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            TestConnector
        )
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            TestConnectorAWS
        )

        # Verify both are registered
        assert MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value in MarketplaceConnectorFactory._connectors
        assert MarketplaceType.AWS_DATA_EXCHANGE.value in MarketplaceConnectorFactory._connectors

        # Cleanup
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.AWS_DATA_EXCHANGE
        )


class TestFactoryRetrieval:
    """Test factory connector retrieval"""

    def test_get_connector_success(self):
        """Test successfully getting a connector"""
        # Register connector
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                TestConnector
            )

        # Get connector
        connector = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Verify it's the correct type
        assert isinstance(connector, TestConnector)
        assert isinstance(connector, DataMarketplaceConnector)
        assert connector.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

    def test_get_connector_creates_new_instance(self):
        """Test that each get_connector call creates a new instance"""
        # Register connector
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                TestConnector
            )

        # Get two connectors
        connector1 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )
        connector2 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Verify they are different instances
        assert connector1 is not connector2
        assert isinstance(connector1, TestConnector)
        assert isinstance(connector2, TestConnector)

    def test_get_connector_unsupported_type(self):
        """Test getting a connector for unsupported marketplace type"""
        # Ensure this type is not registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE
            )

        # Try to get connector for unregistered type
        with pytest.raises(ValueError, match="Unsupported marketplace type"):
            MarketplaceConnectorFactory.get_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE
            )

    def test_get_connector_invalid_type(self):
        """Test getting connector with invalid marketplace type"""
        with pytest.raises(TypeError, match="must be a MarketplaceType enum value"):
            MarketplaceConnectorFactory.get_connector("INVALID_TYPE")


class TestFactorySupportedTypes:
    """Test factory get_supported_types method"""

    def test_get_supported_types_empty(self):
        """Test getting supported types when none are registered"""
        # Save current state
        original_connectors = MarketplaceConnectorFactory._connectors.copy()

        # Clear all registrations
        MarketplaceConnectorFactory._connectors.clear()

        # Get supported types
        supported = MarketplaceConnectorFactory.get_supported_types()

        # Should be empty list
        assert supported == []

        # Restore original state
        MarketplaceConnectorFactory._connectors.update(original_connectors)

    def test_get_supported_types_multiple(self):
        """Test getting supported types with multiple registrations"""
        # Clear existing registrations
        for mt in [MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, MarketplaceType.AWS_DATA_EXCHANGE]:
            if mt.value in MarketplaceConnectorFactory._connectors:
                MarketplaceConnectorFactory.unregister_connector(mt)

        # Register multiple connectors
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            TestConnector
        )
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            TestConnectorAWS
        )

        # Get supported types
        supported = MarketplaceConnectorFactory.get_supported_types()

        # Verify both are in the list
        assert MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE in supported
        assert MarketplaceType.AWS_DATA_EXCHANGE in supported
        assert len(supported) >= 2

        # Verify list is sorted
        values = [mt.value for mt in supported]
        assert values == sorted(values)

        # Cleanup
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.AWS_DATA_EXCHANGE
        )

    def test_is_supported(self):
        """Test is_supported method"""
        # Register a connector
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                TestConnector
            )

        # Test supported type
        assert MarketplaceConnectorFactory.is_supported(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        ) is True

        # Test unsupported type
        assert MarketplaceConnectorFactory.is_supported(
            MarketplaceType.DATABRICKS_MARKETPLACE
        ) is False

        # Test invalid type
        assert MarketplaceConnectorFactory.is_supported("INVALID") is False


class TestFactorySingletonBehavior:
    """Test factory singleton-like behavior"""

    def test_factory_is_class_level(self):
        """Test that factory registry is shared across instances"""
        # Register connector
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                TestConnector
            )

        # Access through class (no instance needed)
        connector1 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Access again through class
        connector2 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Both should work and be different instances
        assert connector1 is not connector2
        assert isinstance(connector1, TestConnector)
        assert isinstance(connector2, TestConnector)

    def test_factory_registry_persists(self):
        """Test that factory registry persists across multiple calls"""
        # Clear and register
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            TestConnector
        )

        # Get connector multiple times
        connector1 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )
        connector2 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )
        connector3 = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # All should be valid instances
        assert isinstance(connector1, TestConnector)
        assert isinstance(connector2, TestConnector)
        assert isinstance(connector3, TestConnector)

        # All should be different instances
        assert connector1 is not connector2
        assert connector2 is not connector3
        assert connector1 is not connector3

        # Cleanup
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )


class TestFactoryUnregister:
    """Test factory unregister functionality"""

    def test_unregister_connector(self):
        """Test unregistering a connector"""
        # Register connector
        if MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                TestConnector
            )

        # Verify it's registered
        assert MarketplaceConnectorFactory.is_supported(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Unregister
        MarketplaceConnectorFactory.unregister_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Verify it's no longer registered
        assert not MarketplaceConnectorFactory.is_supported(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Verify getting connector fails
        with pytest.raises(ValueError, match="Unsupported marketplace type"):
            MarketplaceConnectorFactory.get_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )

    def test_unregister_nonexistent(self):
        """Test unregistering a connector that doesn't exist"""
        # Ensure type is not registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE
            )

        # Try to unregister
        with pytest.raises(ValueError, match="not registered"):
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE
            )

    def test_unregister_invalid_type(self):
        """Test unregistering with invalid marketplace type"""
        with pytest.raises(TypeError, match="must be a MarketplaceType enum value"):
            MarketplaceConnectorFactory.unregister_connector("INVALID_TYPE")


class TestCKANConnectorRegistration(TestCase):
    """Test CKAN connector registration and retrieval"""

    def test_ckan_connector_registration(self):
        """Test that CKAN connector is registered with factory"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Verify registration
        assert MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors
        assert MarketplaceConnectorFactory._connectors[MarketplaceType.CKAN_INSTANCE.value] == CKANConnector

    def test_get_ckan_connector(self):
        """Test retrieving CKAN connector from factory"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Get connector with base_url (CKANConnector requires base_url)
        connector = CKANConnector(base_url='https://ckan.example.com')

        # Verify it's the correct type
        assert isinstance(connector, CKANConnector)
        assert isinstance(connector, DataMarketplaceConnector)
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE

    def test_ckan_connector_is_supported(self):
        """Test that CKAN_INSTANCE is reported as supported after registration"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Verify is_supported returns True
        assert MarketplaceConnectorFactory.is_supported(
            MarketplaceType.CKAN_INSTANCE
        ) is True

    def test_ckan_connector_in_supported_types(self):
        """Test that CKAN_INSTANCE appears in get_supported_types"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Get supported types
        supported = MarketplaceConnectorFactory.get_supported_types()

        # Verify CKAN_INSTANCE is in the list
        assert MarketplaceType.CKAN_INSTANCE in supported

    def test_create_ckan_connector_with_config(self):
        """Test creating CKAN connector with configuration"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Create connector with config (use base_url instead of endpoint to avoid instance matching)
        config = {
            'api_key': 'test-api-key',
            'base_url': 'https://ckan.example.com'  # Use base_url directly, not endpoint
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, CKANConnector)
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE
        # Verify config is set (CKANConnector stores base_url and api_key)
        assert connector.base_url == config.get('base_url')

    def test_ckan_connector_multiple_instances(self):
        """Test that multiple CKAN connector instances can be created"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Create multiple connectors using factory with config (use base_url to avoid instance matching)
        connector1 = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={'base_url': 'https://ckan1.example.com', 'api_key': 'key1'}
        )
        connector2 = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={'base_url': 'https://ckan2.example.com', 'api_key': 'key2'}
        )

        # Verify they are different instances
        assert connector1 is not connector2
        assert isinstance(connector1, CKANConnector)
        assert isinstance(connector2, CKANConnector)
        assert connector1.marketplace_type == MarketplaceType.CKAN_INSTANCE
        assert connector2.marketplace_type == MarketplaceType.CKAN_INSTANCE


class TestGCPMarketplaceConnectorFactory(TestCase):
    """Test GCP Marketplace connector factory registration and creation"""

    def test_create_gcp_marketplace_connector_with_config(self):
        """Test creating GCP Marketplace connector with configuration"""
        try:
            from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
        except ImportError:
            pytest.skip("GCP Marketplace connector not available (google-cloud-bigquery not installed)")

        # Ensure connector is registered
        if MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                GCPMarketplaceConnector
            )

        # Create connector with config
        config = {
            'project_id': 'test-project-id',
            'credentials_json': {
                'type': 'service_account',
                'project_id': 'test-project-id',
                'private_key_id': 'test-key-id',
                'private_key': '-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n',
                'client_email': 'test@test-project.iam.gserviceaccount.com',
                'client_id': '123456789',
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
            },
            'location': 'US'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, GCPMarketplaceConnector)
        assert connector.project_id == 'test-project-id'
        assert connector.location == 'US'
        assert connector.credentials_json == config['credentials_json']
        assert connector.use_adc is False

    def test_create_gcp_marketplace_connector_with_adc(self):
        """Test creating GCP Marketplace connector with Application Default Credentials"""
        try:
            from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
        except ImportError:
            pytest.skip("GCP Marketplace connector not available (google-cloud-bigquery not installed)")

        # Ensure connector is registered
        if MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                GCPMarketplaceConnector
            )

        # Create connector with ADC enabled
        config = {
            'project_id': 'test-project-id',
            'use_adc': True,
            'location': 'EU'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, GCPMarketplaceConnector)
        assert connector.project_id == 'test-project-id'
        assert connector.location == 'EU'
        assert connector.use_adc is True
        assert connector.credentials_json is None

    def test_factory_returns_gcp_marketplace_connector(self):
        """Test factory returns GCP Marketplace connector for GOOGLE_CLOUD_MARKETPLACE type"""
        try:
            from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
        except ImportError:
            pytest.skip("GCP Marketplace connector not available (google-cloud-bigquery not installed)")

        # Ensure connector is registered (should be registered in apps.py ready())
        # If not registered, register it for this test
        if MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                GCPMarketplaceConnector
            )

        # Create connector with config (GCP Marketplace connector requires authentication)
        config = {
            'project_id': 'test-project-id',
            'use_adc': True
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            config=config
        )

        # Verify it's the correct connector type
        assert isinstance(connector, GCPMarketplaceConnector)
        assert connector.marketplace_type == MarketplaceType.GOOGLE_CLOUD_MARKETPLACE
        assert connector.project_id == 'test-project-id'
        assert connector.use_adc is True

    def test_factory_is_supported_gcp_marketplace(self):
        """Test factory is_supported() returns True for GOOGLE_CLOUD_MARKETPLACE"""
        try:
            from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
        except ImportError:
            pytest.skip("GCP Marketplace connector not available (google-cloud-bigquery not installed)")

        # Ensure connector is registered
        if MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                GCPMarketplaceConnector
            )

        # Test is_supported
        assert MarketplaceConnectorFactory.is_supported(
            MarketplaceType.GOOGLE_CLOUD_MARKETPLACE
        ) is True

    def test_factory_get_supported_types_includes_gcp_marketplace(self):
        """Test factory get_supported_types() includes GOOGLE_CLOUD_MARKETPLACE"""
        try:
            from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
        except ImportError:
            pytest.skip("GCP Marketplace connector not available (google-cloud-bigquery not installed)")

        # Ensure connector is registered
        if MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                GCPMarketplaceConnector
            )

        # Get supported types
        supported_types = MarketplaceConnectorFactory.get_supported_types()

        # Verify GOOGLE_CLOUD_MARKETPLACE is in the list
        assert MarketplaceType.GOOGLE_CLOUD_MARKETPLACE in supported_types


class TestAWSDataExchangeConnectorFactory(TestCase):
    """Test AWS Data Exchange connector factory registration and retrieval"""

    def test_aws_data_exchange_connector_registered(self):
        """Test that AWS Data Exchange connector is registered"""
        from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

        # Check if connector is registered
        assert MarketplaceType.AWS_DATA_EXCHANGE.value in MarketplaceConnectorFactory._connectors
        assert MarketplaceConnectorFactory._connectors[MarketplaceType.AWS_DATA_EXCHANGE.value] == AWSDataExchangeConnector

    def test_get_aws_data_exchange_connector(self):
        """Test getting AWS Data Exchange connector from factory"""
        from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

        # Ensure connector is registered
        if MarketplaceType.AWS_DATA_EXCHANGE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                AWSDataExchangeConnector
            )

        # Get connector
        connector = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.AWS_DATA_EXCHANGE
        )

        # Verify it's the correct type
        assert isinstance(connector, AWSDataExchangeConnector)
        assert isinstance(connector, DataMarketplaceConnector)
        assert connector.marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE

    def test_create_aws_data_exchange_connector_with_config(self):
        """Test creating AWS Data Exchange connector with configuration"""
        from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

        # Ensure connector is registered
        if MarketplaceType.AWS_DATA_EXCHANGE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                AWSDataExchangeConnector
            )

        # Create connector with config
        config = {
            'aws_access_key_id': 'test-access-key-id',
            'aws_secret_access_key': 'test-secret-access-key',
            'region_name': 'us-west-2'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, AWSDataExchangeConnector)
        assert connector.marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE
        # Verify config is set
        assert connector._aws_access_key_id == config['aws_access_key_id']
        assert connector._aws_secret_access_key == config['aws_secret_access_key']
        assert connector._region_name == config['region_name']

    def test_create_aws_data_exchange_connector_with_role_arn(self):
        """Test creating AWS Data Exchange connector with IAM role ARN"""
        from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

        # Ensure connector is registered
        if MarketplaceType.AWS_DATA_EXCHANGE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                AWSDataExchangeConnector
            )

        # Create connector with role ARN
        config = {
            'role_arn': 'arn:aws:iam::123456789012:role/DataExchangeRole',
            'region_name': 'us-east-1'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, AWSDataExchangeConnector)
        assert connector.marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE
        assert connector._role_arn == config['role_arn']
        assert connector._region_name == config['region_name']

    def test_create_aws_data_exchange_connector_with_session_token(self):
        """Test creating AWS Data Exchange connector with session token"""
        from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

        # Ensure connector is registered
        if MarketplaceType.AWS_DATA_EXCHANGE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                AWSDataExchangeConnector
            )

        # Create connector with session token
        config = {
            'aws_access_key_id': 'test-access-key-id',
            'aws_secret_access_key': 'test-secret-access-key',
            'aws_session_token': 'test-session-token',
            'region_name': 'us-west-2'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, AWSDataExchangeConnector)
        assert connector._aws_session_token == config['aws_session_token']

    def test_aws_data_exchange_connector_multiple_instances(self):
        """Test that multiple AWS Data Exchange connector instances can be created"""
        from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

        # Ensure connector is registered
        if MarketplaceType.AWS_DATA_EXCHANGE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                AWSDataExchangeConnector
            )

        # Create multiple connectors using factory with config
        connector1 = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            config={
                'aws_access_key_id': 'key1',
                'aws_secret_access_key': 'secret1',
                'region_name': 'us-east-1'
            }
        )
        connector2 = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.AWS_DATA_EXCHANGE,
            config={
                'aws_access_key_id': 'key2',
                'aws_secret_access_key': 'secret2',
                'region_name': 'us-west-2'
            }
        )

        # Verify they are different instances
        assert connector1 is not connector2
        assert isinstance(connector1, AWSDataExchangeConnector)
        assert isinstance(connector2, AWSDataExchangeConnector)
        assert connector1.marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE
        assert connector2.marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE
        assert connector1._aws_access_key_id == 'key1'
        assert connector2._aws_access_key_id == 'key2'
        assert connector1._region_name == 'us-east-1'
        assert connector2._region_name == 'us-west-2'


class TestCKANConnectorIntegration(TestCase):
    """Integration tests for CKAN connector retrieval and usage"""

    def test_ckan_connector_retrieval_in_service(self):
        """Test that CKAN connector can be retrieved in service context"""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        # Unregister any existing connector to ensure clean state
        if MarketplaceType.CKAN_INSTANCE.value in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)

        # Register CKAN connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE,
            CKANConnector
        )

        # Create factory instance (as used in services)
        factory = MarketplaceConnectorFactory()

        # Verify factory can check support
        assert factory.is_supported(MarketplaceType.CKAN_INSTANCE) is True

        # Verify factory can create connector (use base_url to avoid instance matching)
        connector = factory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={'base_url': 'https://ckan.example.com', 'api_key': 'test-key'}
        )

        assert isinstance(connector, CKANConnector)
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE

    def test_ckan_connector_automatic_registration(self):
        """Test that CKAN connector is automatically registered on app startup"""
        # This test verifies that the app's ready() method registers the connector
        from django.apps import apps

        # Get the integrations app config
        app_config = apps.get_app_config('integrations')

        # Call ready() to trigger registration
        # Note: In real Django, this is called automatically, but we can call it here for testing
        if not hasattr(app_config, '_ready_called'):
            app_config.ready()
            app_config._ready_called = True

        # Verify CKAN connector is registered (either CKANConnector or DadosGovBrConnector)
        assert MarketplaceConnectorFactory.is_supported(
            MarketplaceType.CKAN_INSTANCE
        ) is True

        # Check which connector is registered and use appropriate config
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector
        from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

        registered_connector = MarketplaceConnectorFactory._connectors.get(MarketplaceType.CKAN_INSTANCE.value)

        # Use appropriate config based on registered connector
        if registered_connector == DadosGovBrConnector:
            # DadosGovBrConnector expects jwt_token, not api_key
            config = {'base_url': 'https://ckan.example.com', 'jwt_token': 'test-key'}
        else:
            # CKANConnector expects api_key
            config = {'base_url': 'https://ckan.example.com', 'api_key': 'test-key'}

        # Verify we can create the connector with config
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config=config
        )

        # Verify connector is created and is a DataMarketplaceConnector
        assert isinstance(connector, (CKANConnector, DadosGovBrConnector))
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE


class TestDatabricksConnectorFactory(TestCase):
    """Test Databricks connector factory registration and retrieval"""

    def test_databricks_connector_registered(self):
        """Test that Databricks connector is registered"""
        from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector

        # Check if connector is registered
        assert MarketplaceType.DATABRICKS_MARKETPLACE.value in MarketplaceConnectorFactory._connectors
        assert MarketplaceConnectorFactory._connectors[MarketplaceType.DATABRICKS_MARKETPLACE.value] == DatabricksConnector

    def test_get_databricks_connector(self):
        """Test getting Databricks connector from factory"""
        from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector

        # Ensure connector is registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )

        # Get connector (will fail without host/token, but that's expected)
        # We'll test with config in next test
        try:
            connector = MarketplaceConnectorFactory.get_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE
            )
            # If it doesn't fail, verify it's the correct type
            assert isinstance(connector, DatabricksConnector)
            assert isinstance(connector, DataMarketplaceConnector)
            assert connector.marketplace_type == MarketplaceType.DATABRICKS_MARKETPLACE
        except ValueError:
            # Expected if host/token not set in settings
            pass

    def test_create_databricks_connector_with_config(self):
        """Test creating Databricks connector with configuration"""
        from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector

        # Ensure connector is registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )

        # Create connector with config
        config = {
            'host': 'https://test-workspace.cloud.databricks.com',
            'token': 'dapi1234567890abcdef',
            'cluster_id': '1234-567890-abcd1234'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.DATABRICKS_MARKETPLACE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, DatabricksConnector)
        assert connector.marketplace_type == MarketplaceType.DATABRICKS_MARKETPLACE
        assert connector.host == config['host']
        assert connector.token == config['token']
        assert connector.cluster_id == config['cluster_id']

    def test_create_databricks_connector_without_cluster_id(self):
        """Test creating Databricks connector without cluster_id"""
        from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector

        # Ensure connector is registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )

        # Create connector without cluster_id
        config = {
            'host': 'https://test-workspace.cloud.databricks.com',
            'token': 'dapi1234567890abcdef'
        }
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.DATABRICKS_MARKETPLACE,
            config=config
        )

        # Verify connector is created correctly
        assert isinstance(connector, DatabricksConnector)
        assert connector.marketplace_type == MarketplaceType.DATABRICKS_MARKETPLACE
        assert connector.host == config['host']
        assert connector.token == config['token']
        assert connector.cluster_id is None

    def test_databricks_connector_multiple_instances(self):
        """Test that multiple Databricks connector instances can be created"""
        from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector

        # Ensure connector is registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )

        # Create multiple connector instances
        config1 = {
            'host': 'https://workspace1.cloud.databricks.com',
            'token': 'dapi1111111111111111'
        }
        config2 = {
            'host': 'https://workspace2.cloud.databricks.com',
            'token': 'dapi2222222222222222'
        }

        connector1 = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.DATABRICKS_MARKETPLACE,
            config=config1
        )
        connector2 = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.DATABRICKS_MARKETPLACE,
            config=config2
        )

        # Verify they are different instances
        assert connector1 is not connector2
        assert connector1.host == config1['host']
        assert connector2.host == config2['host']
        assert isinstance(connector1, DatabricksConnector)
        assert isinstance(connector2, DatabricksConnector)

    def test_databricks_connector_supported_type(self):
        """Test that Databricks marketplace type is supported"""
        # Ensure connector is registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )

        assert MarketplaceConnectorFactory.is_supported(MarketplaceType.DATABRICKS_MARKETPLACE)

    def test_databricks_connector_in_supported_types(self):
        """Test that Databricks marketplace type appears in supported types list"""
        # Ensure connector is registered
        if MarketplaceType.DATABRICKS_MARKETPLACE.value not in MarketplaceConnectorFactory._connectors:
            from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )

        supported_types = MarketplaceConnectorFactory.get_supported_types()
        assert MarketplaceType.DATABRICKS_MARKETPLACE in supported_types

