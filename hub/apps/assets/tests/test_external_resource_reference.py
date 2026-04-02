"""
Tests for ExternalResourceReference model
"""

import os
import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, ExternalResourceReference
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.tenants.models import Tenant

User = get_user_model()


class ExternalResourceReferenceModelTest(TestCase):
    """Test ExternalResourceReference model"""

    def setUp(self):
        """Set up test fixtures with unique identifiers to avoid conflicts"""
        # Use unique identifiers to avoid conflicts between test runs
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
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{unique_suffix}",
            name="Test Asset",
            description="Test Description",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type="FEDERATED",
            created_by=self.user,
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name=f"Test Connection {unique_suffix}",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"api_url": "https://example.com/api"},
            is_active=True,
        )

    def test_create_external_resource_reference(self):
        """Test creating an ExternalResourceReference"""
        external_resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            size_bytes=1024,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
            metadata={"key": "value"},
        )

        self.assertEqual(external_resource.asset, self.asset)
        self.assertEqual(external_resource.resource_id, "resource-1")
        self.assertEqual(external_resource.name, "Test Resource")
        self.assertEqual(external_resource.url, "https://example.com/resource.csv")
        self.assertEqual(external_resource.format, "CSV")
        self.assertEqual(external_resource.size_bytes, 1024)
        self.assertEqual(external_resource.marketplace_type, MarketplaceType.CKAN_INSTANCE.value)
        self.assertEqual(external_resource.connection_id, self.connection.id)
        self.assertEqual(external_resource.metadata, {"key": "value"})
        self.assertIsNotNone(external_resource.created_at)
        self.assertIsNotNone(external_resource.updated_at)

    def test_unique_constraint_asset_resource_id(self):
        """Test unique constraint on asset and resource_id"""
        ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            ExternalResourceReference.objects.create(
                asset=self.asset,
                resource_id="resource-1",
                name="Another Resource",
                url="https://example.com/another.csv",
                format="CSV",
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                connection_id=self.connection.id,
            )

    def test_clean_validates_format(self):
        """Test clean() method validates format"""
        external_resource = ExternalResourceReference(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="INVALID_FORMAT",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        with self.assertRaises(ValidationError) as cm:
            external_resource.clean()
        self.assertIn("Invalid format", str(cm.exception))

    def test_clean_validates_size_bytes(self):
        """Test clean() method validates size_bytes"""
        external_resource = ExternalResourceReference(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            size_bytes=-1,  # Invalid negative size
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        with self.assertRaises(ValidationError) as cm:
            external_resource.clean()
        self.assertIn("size_bytes must be non-negative", str(cm.exception))

    def test_str_representation(self):
        """Test __str__ method"""
        external_resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        expected_str = f"Test Resource (resource-1) - {self.asset.name}"
        self.assertEqual(str(external_resource), expected_str)

    def test_cascade_delete(self):
        """Test that ExternalResourceReference is deleted when Asset is deleted"""
        external_resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        resource_id = external_resource.id
        self.asset.delete()

        # Verify ExternalResourceReference was deleted
        self.assertFalse(ExternalResourceReference.objects.filter(id=resource_id).exists())

    def test_asset_get_external_resources(self):
        """Test Asset.get_external_resources() method"""
        external_resource1 = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Resource 1",
            url="https://example.com/resource1.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )
        external_resource2 = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-2",
            name="Resource 2",
            url="https://example.com/resource2.json",
            format="JSON",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        # Get external resources
        resources = self.asset.get_external_resources()
        self.assertEqual(resources.count(), 2)
        self.assertIn(external_resource1, resources)
        self.assertIn(external_resource2, resources)

    def test_asset_has_external_resources(self):
        """Test Asset.has_external_resources() method"""
        # Initially no external resources
        self.assertFalse(self.asset.has_external_resources())

        # Create external resource
        ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        # Now has external resources
        self.assertTrue(self.asset.has_external_resources())

    # ========== FAILURE SCENARIOS ==========

    def test_create_external_resource_reference_failure_duplicate(self):
        """Test creating duplicate external resource reference fails (failure scenario)"""
        ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            ExternalResourceReference.objects.create(
                asset=self.asset,
                resource_id="resource-1",
                name="Duplicate Resource",
                url="https://example.com/duplicate.csv",
                format="CSV",
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                connection_id=self.connection.id,
            )

    def test_create_external_resource_reference_with_arbitrary_connection_id(self):
        """Test creating external resource reference with arbitrary connection_id succeeds.

        The connection_id field is a UUIDField with no FK constraint, so the model
        accepts any UUID value.  Validation of the connection happens at the
        service/view layer, not the model layer.
        """
        fake_connection_id = uuid.uuid4()

        resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=fake_connection_id,
        )
        self.assertIsNotNone(resource.id)
        self.assertEqual(resource.connection_id, fake_connection_id)

    # ========== EDGE CASES ==========

    def test_external_resource_reference_edge_case_empty_url(self):
        """Test external resource reference with empty URL (edge case)"""
        resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-empty-url",
            name="Empty URL Resource",
            url="",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        self.assertEqual(resource.url, "")

    def test_external_resource_reference_edge_case_very_long_url(self):
        """Test external resource reference with very long URL (edge case)"""
        # Django URLField has max_length of 200 by default
        # Test with a URL that's at the limit but not exceeding it
        long_url = "https://example.com/" + "a" * (200 - len("https://example.com/"))
        resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-long-url",
            name="Long URL Resource",
            url=long_url,
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        self.assertEqual(resource.url, long_url)

    def test_external_resource_reference_edge_case_zero_size(self):
        """Test external resource reference with zero size (edge case)"""
        resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-zero-size",
            name="Zero Size Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            size_bytes=0,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        self.assertEqual(resource.size_bytes, 0)

    def test_external_resource_reference_edge_case_multiple_resources_same_asset_count(self):
        """Test multiple external resources for same asset has correct count."""
        for i in range(5):
            ExternalResourceReference.objects.create(
                asset=self.asset,
                resource_id=f"resource-{i}",
                name=f"Resource {i}",
                url=f"https://example.com/resource{i}.csv",
                format="CSV",
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                connection_id=self.connection.id,
            )

        # Use the correct related_name from the model
        self.assertEqual(self.asset.external_resource_references.count(), 5)

    def test_external_resource_reference_edge_case_multiple_resources_same_asset_has_resources(
        self,
    ):
        """Test multiple external resources for same asset has_external_resources returns True."""
        for i in range(5):
            ExternalResourceReference.objects.create(
                asset=self.asset,
                resource_id=f"resource-{i}",
                name=f"Resource {i}",
                url=f"https://example.com/resource{i}.csv",
                format="CSV",
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                connection_id=self.connection.id,
            )

        self.assertTrue(self.asset.has_external_resources())

    def test_asset_download_external_resource_not_found(self):
        """Test Asset.download_external_resource() when resource not found"""
        with self.assertRaises(ValidationError) as cm:
            self.asset.download_external_resource("non-existent-resource")
        self.assertIn("not found", str(cm.exception).lower())

    def test_asset_download_external_resource_connection_not_found(self):
        """Test Asset.download_external_resource() when connection not found"""
        # Create external resource with invalid connection_id
        invalid_connection_id = "00000000-0000-0000-0000-000000000000"
        external_resource = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=invalid_connection_id,
        )

        with self.assertRaises(ValidationError) as cm:
            self.asset.download_external_resource("resource-1")
        self.assertIn("connection", str(cm.exception).lower())

    def test_multiple_resources_same_asset(self):
        """Test creating multiple ExternalResourceReference for same asset"""
        resource1 = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Resource 1",
            url="https://example.com/resource1.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )
        resource2 = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-2",
            name="Resource 2",
            url="https://example.com/resource2.json",
            format="JSON",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        self.assertEqual(self.asset.external_resource_references.count(), 2)
        self.assertIn(resource1, self.asset.external_resource_references.all())
        self.assertIn(resource2, self.asset.external_resource_references.all())

    def test_different_assets_same_resource_id(self):
        """Test creating ExternalResourceReference with same resource_id for different assets"""
        unique_suffix = uuid.uuid4().hex[:8]
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-2-{unique_suffix}",
            name="Test Asset 2",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
            source_type="FEDERATED",
            created_by=self.user,
        )

        resource1 = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id="resource-1",
            name="Resource 1",
            url="https://example.com/resource1.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )
        resource2 = ExternalResourceReference.objects.create(
            asset=asset2,
            resource_id="resource-1",  # Same resource_id, different asset
            name="Resource 1",
            url="https://example.com/resource1.csv",
            format="CSV",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.connection.id,
        )

        # Both should exist
        self.assertEqual(self.asset.external_resource_references.count(), 1)
        self.assertEqual(asset2.external_resource_references.count(), 1)
        self.assertNotEqual(resource1.id, resource2.id)
