"""
Tests for Asset data_strategy field
"""
import uuid
from django.test import TestCase
from django.core.exceptions import ValidationError

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, AssetSourceType, DataStrategy
from hub.apps.tenants.models import Tenant
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from django.contrib.auth import get_user_model

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

    def test_is_metadata_only(self):
        """Test is_metadata_only() helper method"""
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

        self.assertTrue(asset_metadata.is_metadata_only())
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

    def test_can_download_resource_download_all(self):
        """Test can_download_resource() returns True for DOWNLOAD_ALL"""
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

        # DOWNLOAD_ALL allows downloading any resource
        self.assertTrue(asset.can_download_resource("resource-1"))
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
        from hub.apps.integrations.models import MarketplaceConnection
        from hub.apps.integrations.base import MarketplaceType

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

