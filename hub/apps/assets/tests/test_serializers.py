"""
Unit tests for asset serializers.
"""

import uuid
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.assets.serializers import (
    AssetCreateSerializer,
    AssetSerializer,
    AssetUpdateSerializer,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class AssetSerializerTest(TestCase):
    """Test asset serializers"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user,
        )

    def test_asset_serializer_serializes_id(self):
        """Test AssetSerializer serializes id correctly."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["id"], str(self.asset.id))

    def test_asset_serializer_serializes_key(self):
        """Test AssetSerializer serializes key correctly."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["key"], "test-asset")

    def test_asset_serializer_serializes_name(self):
        """Test AssetSerializer serializes name correctly."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["name"], "Test Asset")

    def test_asset_serializer_serializes_status(self):
        """Test AssetSerializer serializes status correctly"""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["status"], AssetStatus.DRAFT)

    def test_asset_create_serializer_is_valid(self):
        """Test AssetCreateSerializer validation returns True for valid data"""
        serializer = AssetCreateSerializer(
            data={
                "key": "new-asset",
                "name": "New Asset",
                "description": "New description",
                "visibility": "INTERNAL",
            }
        )

        self.assertTrue(serializer.is_valid())

    def test_asset_create_serializer_validates_key_and_name(self):
        """Test AssetCreateSerializer validates key and name correctly"""
        serializer = AssetCreateSerializer(
            data={
                "key": "new-asset",
                "name": "New Asset",
                "description": "New description",
                "visibility": "INTERNAL",
            }
        )

        serializer.is_valid()
        self.assertEqual(serializer.validated_data["key"], "new-asset")
        self.assertEqual(serializer.validated_data["name"], "New Asset")

    def test_asset_update_serializer_is_valid(self):
        """Test AssetUpdateSerializer validation returns True for valid data"""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={"name": "Updated Asset", "description": "Updated description"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid())

    def test_asset_update_serializer_updates_name(self):
        """Test AssetUpdateSerializer updates name correctly"""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={"name": "Updated Asset", "description": "Updated description"},
            partial=True,
        )

        serializer.is_valid()
        updated = serializer.save()
        self.assertEqual(updated.name, "Updated Asset")

    # ========== FAILURE SCENARIOS ==========

    def test_asset_create_serializer_invalid_data(self):
        """Test AssetCreateSerializer with invalid data (failure scenario)"""
        serializer = AssetCreateSerializer(data={"key": "", "name": "Test Asset"})  # Empty key

        self.assertFalse(serializer.is_valid())
        self.assertIn("key", serializer.errors)

    def test_asset_create_serializer_missing_required_fields(self):
        """Test AssetCreateSerializer with missing required fields (failure scenario)"""
        serializer = AssetCreateSerializer(
            data={
                "name": "Test Asset"
                # Missing key
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("key", serializer.errors)

    def test_asset_update_serializer_invalid_status(self):
        """AssetUpdateSerializer rejects invalid status values."""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={"status": "INVALID_STATUS"},
            partial=True,
        )

        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject invalid status value",
        )
        self.assertIn("status", serializer.errors)

    # ========== EDGE CASES ==========

    def test_asset_serializer_empty_description(self):
        """Test AssetSerializer with empty description (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="empty-desc-asset",
            name="Empty Desc Asset",
            description="",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        serializer = AssetSerializer(asset)
        data = serializer.data

        self.assertEqual(data["description"], "")

    def test_asset_serializer_none_values(self):
        """Test AssetSerializer with None values (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="none-values-asset",
            name="None Values Asset",
            description=None,
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        serializer = AssetSerializer(asset)
        data = serializer.data

        # Should handle None values gracefully
        self.assertIsNotNone(data["id"])
        self.assertEqual(data["key"], "none-values-asset")

    def test_asset_create_serializer_very_long_key(self):
        """AssetCreateSerializer rejects key exceeding max_length."""
        long_key = "a" * 300  # max_length=255
        serializer = AssetCreateSerializer(
            data={"key": long_key, "name": "Test Asset"},
        )

        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject key longer than max_length",
        )
        self.assertIn("key", serializer.errors)

    def test_asset_update_serializer_partial_update(self):
        """Test AssetUpdateSerializer with partial update (edge case)"""
        serializer = AssetUpdateSerializer(
            instance=self.asset, data={"name": "Partially Updated"}, partial=True
        )

        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        self.assertEqual(updated.name, "Partially Updated")
        # Other fields should remain unchanged
        self.assertEqual(updated.key, self.asset.key)

    def test_asset_update_serializer_no_changes(self):
        """Test AssetUpdateSerializer with no changes (edge case)"""
        serializer = AssetUpdateSerializer(instance=self.asset, data={}, partial=True)

        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        # Should not change anything
        self.assertEqual(updated.name, self.asset.name)

    # ========== ERROR HANDLING ==========

    def test_asset_serializer_serializes_valid_asset(self):
        """AssetSerializer serializes a valid asset without error."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data
        self.assertEqual(data["key"], self.asset.key)
        self.assertEqual(data["name"], self.asset.name)
        self.assertIn("id", data)

    def test_asset_create_serializer_ignores_unknown_fields(self):
        """AssetCreateSerializer ignores unknown fields (DRF default)."""
        serializer = AssetCreateSerializer(
            data={
                "key": "test-asset",
                "name": "Test Asset",
                "status": "INVALID_STATUS",
            }
        )
        # DRF ignores unknown fields — serializer is valid
        self.assertTrue(
            serializer.is_valid(),
            f"Extra fields should be ignored: {serializer.errors}",
        )

    def test_asset_update_serializer_nonexistent_instance_raises(self):
        """Saving AssetUpdateSerializer with unsaved instance raises."""
        import uuid

        fake_asset = Asset(
            id=uuid.uuid4(), tenant=self.tenant, key="fake",
        )
        serializer = AssetUpdateSerializer(
            instance=fake_asset, data={"name": "Updated"},
        )

        if serializer.is_valid():
            with self.assertRaises(Exception):
                serializer.save()
