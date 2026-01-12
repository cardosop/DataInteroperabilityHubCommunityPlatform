"""
Unit tests for base marketplace connector interface.

Tests the abstract base class structure, enums, and dataclasses
to ensure they cannot be instantiated incorrectly and work as expected.
"""
import pytest
from datetime import datetime
from typing import List

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


class TestMarketplaceType:
    """Test MarketplaceType enum"""

    def test_enum_values(self):
        """Test that all 15 marketplace types are defined"""
        expected_types = [
            "SNOWFLAKE_DATA_MARKETPLACE",
            "AWS_DATA_EXCHANGE",
            "DATABRICKS_MARKETPLACE",
            "GOOGLE_CLOUD_MARKETPLACE",
            "AZURE_MARKETPLACE",
            "DATA_WORLD",
            "KAGGLE",
            "QUANDL",
            "APIS_GURU",
            "RAPIDAPI",
            "PROGRAMMABLE_WEB",
            "DATA_GOV",
            "EUROPEAN_DATA_PORTAL",
            "CKAN_INSTANCE",
            "CUSTOM",
        ]

        actual_types = [mt.value for mt in MarketplaceType]
        assert len(actual_types) == 15, f"Expected 15 marketplace types, got {len(actual_types)}"
        assert set(actual_types) == set(expected_types), "Marketplace types don't match expected values"

    def test_enum_string_representation(self):
        """Test that enum values are strings"""
        for marketplace_type in MarketplaceType:
            assert isinstance(marketplace_type.value, str)
            assert marketplace_type.value == marketplace_type.name


class TestSyncDirection:
    """Test SyncDirection enum"""

    def test_enum_values(self):
        """Test that all sync directions are defined"""
        expected_directions = ["PUSH", "PULL", "BIDIRECTIONAL"]
        actual_directions = [sd.value for sd in SyncDirection]
        assert set(actual_directions) == set(expected_directions)

    def test_enum_string_representation(self):
        """Test that enum values are strings"""
        for sync_direction in SyncDirection:
            assert isinstance(sync_direction.value, str)
            assert sync_direction.value == sync_direction.name


class TestSyncStatus:
    """Test SyncStatus enum"""

    def test_enum_values(self):
        """Test that all sync statuses are defined"""
        expected_statuses = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "PARTIAL"]
        actual_statuses = [ss.value for ss in SyncStatus]
        assert set(actual_statuses) == set(expected_statuses)

    def test_enum_string_representation(self):
        """Test that enum values are strings"""
        for sync_status in SyncStatus:
            assert isinstance(sync_status.value, str)
            assert sync_status.value == sync_status.name


class TestMarketplaceListing:
    """Test MarketplaceListing dataclass"""

    def test_create_minimal_listing(self):
        """Test creating a listing with minimal required fields"""
        listing = MarketplaceListing(
            marketplace_id="test-123",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing"
        )

        assert listing.marketplace_id == "test-123"
        assert listing.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        assert listing.title == "Test Listing"
        assert listing.description is None
        assert listing.tags == []
        assert listing.pricing_plans == []
        assert listing.access_methods == {}
        assert listing.payment_gateways == {}
        assert listing.metadata == {}

    def test_create_full_listing(self):
        """Test creating a listing with all fields"""
        created_at = datetime(2025, 1, 1, 12, 0, 0)
        updated_at = datetime(2025, 1, 2, 12, 0, 0)

        listing = MarketplaceListing(
            marketplace_id="test-456",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Full Test Listing",
            description="A comprehensive test listing",
            product_id="product-123",
            category="Analytics",
            tags=["test", "data"],
            pricing_plans=[{"planID": "basic", "price": 9.99}],
            access_methods={"api": {"type": "REST"}},
            payment_gateways={"stripe": {"enabled": True}},
            metadata={"custom": "value"},
            created_at=created_at,
            updated_at=updated_at,
            url="https://example.com/listing/123"
        )

        assert listing.marketplace_id == "test-456"
        assert listing.marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE
        assert listing.title == "Full Test Listing"
        assert listing.description == "A comprehensive test listing"
        assert listing.product_id == "product-123"
        assert listing.category == "Analytics"
        assert listing.tags == ["test", "data"]
        assert len(listing.pricing_plans) == 1
        assert listing.access_methods == {"api": {"type": "REST"}}
        assert listing.payment_gateways == {"stripe": {"enabled": True}}
        assert listing.metadata == {"custom": "value"}
        assert listing.created_at == created_at
        assert listing.updated_at == updated_at
        assert listing.url == "https://example.com/listing/123"

    def test_listing_serialization(self):
        """Test that listing can be converted to dict-like structure"""
        listing = MarketplaceListing(
            marketplace_id="test-789",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Serialization Test"
        )

        # Test that dataclass fields are accessible
        assert hasattr(listing, '__dataclass_fields__')
        assert 'marketplace_id' in listing.__dict__
        assert 'marketplace_type' in listing.__dict__
        assert 'title' in listing.__dict__


class TestMarketplaceResource:
    """Test MarketplaceResource dataclass"""

    def test_create_minimal_resource(self):
        """Test creating a resource with minimal required fields"""
        resource = MarketplaceResource(
            resource_id="res-123",
            resource_type="FILE",
            name="test.csv"
        )

        assert resource.resource_id == "res-123"
        assert resource.resource_type == "FILE"
        assert resource.name == "test.csv"
        assert resource.description is None
        assert resource.url is None
        assert resource.format is None
        assert resource.size_bytes is None
        assert resource.metadata == {}

    def test_create_full_resource(self):
        """Test creating a resource with all fields"""
        resource = MarketplaceResource(
            resource_id="res-456",
            resource_type="API",
            name="Test API",
            description="A test API endpoint",
            url="https://api.example.com/v1/data",
            format="JSON",
            size_bytes=1024,
            metadata={"version": "1.0", "rate_limit": 1000}
        )

        assert resource.resource_id == "res-456"
        assert resource.resource_type == "API"
        assert resource.name == "Test API"
        assert resource.description == "A test API endpoint"
        assert resource.url == "https://api.example.com/v1/data"
        assert resource.format == "JSON"
        assert resource.size_bytes == 1024
        assert resource.metadata == {"version": "1.0", "rate_limit": 1000}


class TestSyncResult:
    """Test SyncResult dataclass"""

    def test_create_minimal_result(self):
        """Test creating a result with minimal required fields"""
        result = SyncResult(status=SyncStatus.PENDING)

        assert result.status == SyncStatus.PENDING
        assert result.total_items == 0
        assert result.successful_items == 0
        assert result.failed_items == 0
        assert result.skipped_items == 0
        assert result.errors == []
        assert result.metadata == {}
        assert result.started_at is None
        assert result.completed_at is None

    def test_create_full_result(self):
        """Test creating a result with all fields"""
        started_at = datetime(2025, 1, 1, 10, 0, 0)
        completed_at = datetime(2025, 1, 1, 10, 5, 0)

        result = SyncResult(
            status=SyncStatus.COMPLETED,
            total_items=100,
            successful_items=95,
            failed_items=3,
            skipped_items=2,
            errors=["Error 1", "Error 2"],
            metadata={"duration_seconds": 300},
            started_at=started_at,
            completed_at=completed_at
        )

        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 100
        assert result.successful_items == 95
        assert result.failed_items == 3
        assert result.skipped_items == 2
        assert result.errors == ["Error 1", "Error 2"]
        assert result.metadata == {"duration_seconds": 300}
        assert result.started_at == started_at
        assert result.completed_at == completed_at


class TestMarketplaceAssetMapping:
    """Test MarketplaceAssetMapping dataclass"""

    def test_create_minimal_mapping(self):
        """Test creating a mapping with minimal required fields"""
        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset", "description": "A test asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
                "marketplace_id": "mp-123",
                "listing_id": "list-456"
            },
            odps_metadata={
                "product": {
                    "details": {"en": {"name": "Test Product"}}
                }
            }
        )

        assert mapping.asset_data == {"name": "Test Asset", "description": "A test asset"}
        assert mapping.source_type == AssetSourceType.FEDERATED
        assert mapping.source_metadata["marketplace_type"] == "SNOWFLAKE_DATA_MARKETPLACE"
        assert mapping.odps_metadata["product"]["details"]["en"]["name"] == "Test Product"
        assert mapping.odcs_metadata is None
        assert mapping.resources == []

    def test_create_full_mapping(self):
        """Test creating a mapping with all fields"""
        resource = MarketplaceResource(
            resource_id="res-123",
            resource_type="FILE",
            name="data.csv"
        )

        mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Full Test Asset",
                "description": "A comprehensive test asset",
                "domain": "Analytics",
                "status": "ACTIVE",
                "visibility": "PUBLIC"
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": "AWS_DATA_EXCHANGE",
                "marketplace_id": "mp-789",
                "listing_id": "list-012",
                "listing_url": "https://example.com/listings/012",
                "synced_at": "2025-01-01T12:00:00Z",
                "sync_job_id": "job-345"
            },
            odps_metadata={
                "product": {
                    "details": {"en": {"name": "Test Product", "productID": "prod-123"}},
                    "marketplace": {
                        "pricingPlans": [{"planID": "basic", "price": 9.99}]
                    }
                }
            },
            odcs_metadata={
                "schema": {
                    "fields": [{"name": "field1", "type": "string"}]
                },
                "quality": {
                    "freshness": {"maxAge": "PT1H"}
                }
            },
            resources=[resource]
        )

        assert mapping.asset_data["name"] == "Full Test Asset"
        assert mapping.source_type == AssetSourceType.FEDERATED
        assert mapping.source_metadata["sync_job_id"] == "job-345"
        assert mapping.odps_metadata["product"]["details"]["en"]["productID"] == "prod-123"
        assert mapping.odcs_metadata["schema"]["fields"][0]["name"] == "field1"
        assert len(mapping.resources) == 1
        assert mapping.resources[0].resource_id == "res-123"

    def test_mapping_serialization(self):
        """Test that mapping can be serialized/deserialized"""
        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "TEST"},
            odps_metadata={"product": {}}
        )

        # Test that dataclass fields are accessible
        assert hasattr(mapping, '__dataclass_fields__')
        assert 'asset_data' in mapping.__dict__
        assert 'source_type' in mapping.__dict__
        assert 'source_metadata' in mapping.__dict__
        assert 'odps_metadata' in mapping.__dict__


class TestDataMarketplaceConnector:
    """Test DataMarketplaceConnector abstract base class"""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract base class cannot be instantiated directly"""
        with pytest.raises(TypeError):
            DataMarketplaceConnector()

    def test_abstract_methods_exist(self):
        """Test that all abstract methods are defined"""
        abstract_methods = {
            'marketplace_type',
            'supported_sync_directions',
            'authenticate',
            'test_connection',
            'list_listings',
            'get_listing',
            'list_resources',
            'create_listing',
            'update_listing',
            'publish_resource',
            'download_resource',
            'map_to_hub_asset',
            'map_from_hub_asset',
            'sync_push',
            'sync_pull',
        }

        # Get all abstract methods from the class
        actual_methods = set()
        for name in dir(DataMarketplaceConnector):
            attr = getattr(DataMarketplaceConnector, name)
            if hasattr(attr, '__isabstractmethod__') and attr.__isabstractmethod__:
                actual_methods.add(name)

        # Check properties separately
        if hasattr(DataMarketplaceConnector, 'marketplace_type'):
            prop = DataMarketplaceConnector.marketplace_type
            if hasattr(prop, 'fget') and hasattr(prop.fget, '__isabstractmethod__'):
                if prop.fget.__isabstractmethod__:
                    actual_methods.add('marketplace_type')

        if hasattr(DataMarketplaceConnector, 'supported_sync_directions'):
            prop = DataMarketplaceConnector.supported_sync_directions
            if hasattr(prop, 'fget') and hasattr(prop.fget, '__isabstractmethod__'):
                if prop.fget.__isabstractmethod__:
                    actual_methods.add('supported_sync_directions')

        # Verify all expected abstract methods exist
        assert abstract_methods.issubset(actual_methods), \
            f"Missing abstract methods: {abstract_methods - actual_methods}"

    def test_concrete_implementation_required(self):
        """Test that a concrete implementation must implement all abstract methods"""

        class IncompleteConnector(DataMarketplaceConnector):
            """Incomplete connector implementation"""
            pass

        # Should raise TypeError when trying to instantiate
        with pytest.raises(TypeError):
            IncompleteConnector()

        # Complete implementation should work
        class CompleteConnector(DataMarketplaceConnector):
            """Complete connector implementation"""

            @property
            def marketplace_type(self):
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

            @property
            def supported_sync_directions(self):
                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id):
                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="Test"
                )

            def list_resources(self, listing_id):
                return []

            def create_listing(self, listing):
                return listing

            def update_listing(self, listing_id, listing):
                return listing

            def publish_resource(self, listing_id, resource):
                return resource

            def download_resource(self, resource_id, destination_path):
                return destination_path

            def map_to_hub_asset(self, listing):
                return MarketplaceAssetMapping(
                    asset_data={"name": "Test"},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                    odps_metadata={}
                )

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                return MarketplaceListing(
                    marketplace_id="test",
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title=asset_data.get("name", "Unknown")
                )

            def sync_push(self, asset_ids, options=None):
                return SyncResult(status=SyncStatus.COMPLETED)

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                return SyncResult(status=SyncStatus.COMPLETED)

        # Complete implementation should be instantiable
        connector = CompleteConnector()
        assert connector.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        assert SyncDirection.PUSH in connector.supported_sync_directions
        assert connector.authenticate({}) is True

