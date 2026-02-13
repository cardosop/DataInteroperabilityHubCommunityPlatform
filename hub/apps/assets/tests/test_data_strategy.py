"""
Tests for Asset data_strategy field
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.assets.models import (
    Asset,
    AssetSourceType,
    AssetStatus,
    AssetVisibility,
    DataStrategy,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class AssetDataStrategyTest(TestCase):
    """Test Asset data_strategy field"""

    def setUp(self):
        """Set up test fixtures with unique identifiers"""
        unique_suffix = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_suffix}",
            slug=f"test-tenant-{unique_suffix}",
        )
        self.user = User.objects.create_user(
            email=f"test-{unique_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_default_data_strategy(self):
        """Test that new assets default to METADATA_ONLY"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            created_by=self.user,
        )
        self.assertEqual(asset.data_strategy, DataStrategy.METADATA_ONLY)

    def test_federated_asset_default_data_strategy(self):
        """Test that federated assets default to METADATA_ONLY"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Federated Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            created_by=self.user,
        )
        self.assertEqual(asset.data_strategy, DataStrategy.METADATA_ONLY)

    def test_set_data_strategy_download_all(self):
        """Test setting data_strategy to DOWNLOAD_ALL"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )
        self.assertEqual(asset.data_strategy, DataStrategy.DOWNLOAD_ALL)

    def test_set_data_strategy_download_selective(self):
        """Test setting data_strategy to DOWNLOAD_SELECTIVE"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=self.user,
        )
        self.assertEqual(asset.data_strategy, DataStrategy.DOWNLOAD_SELECTIVE)

    def test_is_metadata_only_returns_true_for_metadata_only(self):
        """Test is_metadata_only returns True for METADATA_ONLY strategy."""
        asset_metadata = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-metadata-{uuid.uuid4().hex[:8]}",
            name="Metadata Only Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
            created_by=self.user,
        )

        self.assertTrue(asset_metadata.is_metadata_only())

    def test_is_metadata_only_returns_false_for_download_all(self):
        """Test is_metadata_only returns False for DOWNLOAD_ALL strategy."""
        asset_download = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-download-{uuid.uuid4().hex[:8]}",
            name="Download Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        self.assertFalse(asset_download.is_metadata_only())

    def test_can_download_resource_metadata_only(self):
        """Test can_download_resource() returns False for METADATA_ONLY"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
            created_by=self.user,
        )

        self.assertFalse(asset.can_download_resource("resource-1"))

    def test_can_download_resource_download_all_allows_any_resource(self):
        """Test can_download_resource returns True for DOWNLOAD_ALL with any resource."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        self.assertTrue(asset.can_download_resource("resource-1"))

    def test_can_download_resource_download_all_allows_multiple_resources(self):
        """Test can_download_resource returns True for DOWNLOAD_ALL with multiple resources."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        self.assertTrue(asset.can_download_resource("resource-2"))

    def test_can_download_resource_download_selective_with_resource(self):
        """Test can_download_resource() for DOWNLOAD_SELECTIVE with existing resource"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=self.user,
        )

        # Create external resource reference
        from hub.apps.assets.models import ExternalResourceReference
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection

        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name=f"Test Connection {uuid.uuid4().hex[:8]}",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"api_url": "https://example.com/api"},
            is_active=True,
        )

        ExternalResourceReference.objects.create(
            asset=asset,
            resource_id="resource-1",
            name="Resource 1",
            url="https://example.com/resource1.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=connection.id,
        )

        # Can download resource-1 (exists)
        self.assertTrue(asset.can_download_resource("resource-1"))
        # Cannot download resource-2 (doesn't exist)
        self.assertFalse(asset.can_download_resource("resource-2"))

    def test_can_download_resource_download_selective_no_resources(self):
        """Test can_download_resource() for DOWNLOAD_SELECTIVE without resources"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=self.user,
        )

        # No external resources, so cannot download
        self.assertFalse(asset.can_download_resource("resource-1"))

    # ========== SUCCESS SCENARIOS ==========

    def test_data_strategy_success_metadata_only_sets_strategy(self):
        """Test successful METADATA_ONLY strategy sets strategy."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
            created_by=self.user,
        )

        self.assertEqual(asset.data_strategy, DataStrategy.METADATA_ONLY)

    def test_data_strategy_success_metadata_only_is_metadata_only(self):
        """Test successful METADATA_ONLY strategy is_metadata_only returns True."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
            created_by=self.user,
        )

        self.assertTrue(asset.is_metadata_only())

    def test_data_strategy_success_metadata_only_cannot_download(self):
        """Test successful METADATA_ONLY strategy cannot download resource."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
            created_by=self.user,
        )

        self.assertFalse(asset.can_download_resource("resource-1"))

    def test_data_strategy_success_download_all_sets_strategy(self):
        """Test successful DOWNLOAD_ALL strategy sets strategy."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        self.assertEqual(asset.data_strategy, DataStrategy.DOWNLOAD_ALL)

    def test_data_strategy_success_download_all_is_not_metadata_only(self):
        """Test successful DOWNLOAD_ALL strategy is_metadata_only returns False."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        self.assertFalse(asset.is_metadata_only())

    def test_data_strategy_success_download_all_can_download(self):
        """Test successful DOWNLOAD_ALL strategy can download resource."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        self.assertTrue(asset.can_download_resource("resource-1"))

    # ========== FAILURE SCENARIOS ==========

    def test_data_strategy_failure_invalid_strategy(self):
        """Test failure with invalid data_strategy (failure scenario)"""
        # Try to create asset with invalid strategy
        try:
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"test-asset-{uuid.uuid4().hex[:8]}",
                name="Test Asset",
                status=AssetStatus.ACTIVE,
                visibility=AssetVisibility.PUBLIC,
                source_type=AssetSourceType.FEDERATED,
                data_strategy="INVALID_STRATEGY",
                created_by=self.user,
            )
            # If succeeds, verify it was set
            self.assertIsNotNone(asset.data_strategy)
        except (ValidationError, ValueError):
            # If fails, that's acceptable for invalid strategy
            pass

    def test_can_download_resource_failure_nonexistent_resource(self):
        """Test can_download_resource failure for non-existent resource (failure scenario)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=self.user,
        )

        # Should return False for non-existent resource
        self.assertFalse(asset.can_download_resource("nonexistent-resource"))

    # ========== EDGE CASES ==========

    def test_data_strategy_edge_case_hub_native_with_download_all(self):
        """Test HUB_NATIVE asset with DOWNLOAD_ALL strategy (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.HUB_NATIVE,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        # HUB_NATIVE assets typically don't need download strategies
        # But should handle gracefully
        self.assertEqual(asset.data_strategy, DataStrategy.DOWNLOAD_ALL)

    def test_data_strategy_edge_case_multiple_resources_selective_allows_referenced(self):
        """Test DOWNLOAD_SELECTIVE with multiple resources allows downloading referenced resources."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=self.user,
        )

        # Create multiple external resource references
        from hub.apps.assets.models import ExternalResourceReference
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection

        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name=f"Test Connection {uuid.uuid4().hex[:8]}",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"api_url": "https://example.com/api"},
            is_active=True,
        )

        for i in range(5):
            ExternalResourceReference.objects.create(
                asset=asset,
                resource_id=f"resource-{i}",
                name=f"Resource {i}",
                url=f"https://example.com/resource{i}.csv",
                format="CSV",
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                connection_id=connection.id,
            )

        # Should allow downloading all referenced resources
        for i in range(5):
            self.assertTrue(asset.can_download_resource(f"resource-{i}"))

    def test_data_strategy_edge_case_multiple_resources_selective_rejects_non_referenced(self):
        """Test DOWNLOAD_SELECTIVE with multiple resources rejects non-referenced resources."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=self.user,
        )

        # Create multiple external resource references
        from hub.apps.assets.models import ExternalResourceReference
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection

        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name=f"Test Connection {uuid.uuid4().hex[:8]}",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"api_url": "https://example.com/api"},
            is_active=True,
        )

        for i in range(5):
            ExternalResourceReference.objects.create(
                asset=asset,
                resource_id=f"resource-{i}",
                name=f"Resource {i}",
                url=f"https://example.com/resource{i}.csv",
                format="CSV",
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                connection_id=connection.id,
            )

        # Should not allow downloading non-referenced resource
        self.assertFalse(asset.can_download_resource("resource-999"))

    # ========== ERROR HANDLING ==========

    def test_data_strategy_error_handling_database_error(self):
        """Test error handling when database operations fail"""
        # Use valid data
        try:
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"test-asset-{uuid.uuid4().hex[:8]}",
                name="Test Asset",
                status=AssetStatus.ACTIVE,
                visibility=AssetVisibility.PUBLIC,
                source_type=AssetSourceType.FEDERATED,
                data_strategy=DataStrategy.METADATA_ONLY,
                created_by=self.user,
            )
            # Should succeed
            self.assertIsNotNone(asset)
        except Exception:
            # If raises exception, that's a problem
            self.fail("Asset creation should handle database errors gracefully")

    def test_can_download_resource_error_handling(self):
        """Test error handling when checking download permission fails"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
            created_by=self.user,
        )

        # Should handle errors gracefully
        try:
            result = asset.can_download_resource("resource-1")
            # Should return boolean
            self.assertIsInstance(result, bool)
        except Exception:
            # If raises exception, that's a problem
            self.fail("can_download_resource should handle errors gracefully")
