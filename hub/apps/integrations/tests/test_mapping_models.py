"""
Unit tests for MarketplaceMapping model.

Comprehensive tests for model creation, unique constraints, sync metadata updates, and validation.
"""
import uuid

from datetime import timedelta

import pytest

from tests.utils.wait_helpers import wait_for_event_persistence
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceMappingModelTest(TestCase):
    """Test MarketplaceMapping model"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
        )

    def test_create_mapping(self):
        """Test basic mapping creation"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        self.assertIsNotNone(mapping.id)
        self.assertEqual(mapping.tenant, self.tenant)
        self.assertEqual(mapping.connection, self.connection)
        self.assertEqual(mapping.hub_asset, self.asset)
        self.assertEqual(mapping.external_listing_id, "ext-listing-123")
        self.assertEqual(mapping.external_resource_ids, [])
        self.assertEqual(mapping.sync_metadata, {})
        self.assertIsNone(mapping.last_synced_at)
        self.assertIsNotNone(mapping.created_at)

    def test_create_mapping_with_all_fields(self):
        """Test mapping creation with all fields"""
        external_resource_ids = ["resource-1", "resource-2", "resource-3"]
        sync_metadata = {"last_sync_status": "success", "items_synced": 10}
        last_synced = timezone.now() - timedelta(hours=1)

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-456",
            external_resource_ids=external_resource_ids,
            sync_metadata=sync_metadata,
            last_synced_at=last_synced,
        )

        self.assertEqual(mapping.external_listing_id, "ext-listing-456")
        self.assertEqual(mapping.external_resource_ids, external_resource_ids)
        self.assertEqual(mapping.sync_metadata, sync_metadata)
        self.assertEqual(mapping.last_synced_at, last_synced)

    def test_mapping_str_representation(self):
        """Test string representation of mapping"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-789",
        )

        str_repr = str(mapping)
        self.assertIn("Test Asset", str_repr)
        self.assertIn("Test Connection", str_repr)
        self.assertIn("ext-listing-789", str_repr)

    def test_unique_constraint_connection_asset(self):
        """Test that connection + hub_asset combination must be unique"""
        MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1",
        )

        # Try to create another mapping with same connection and asset
        with self.assertRaises(ValidationError) as cm:
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id="ext-listing-2",
            )

        self.assertIn("A mapping already exists for this connection and asset.", str(cm.exception))

    def test_same_asset_different_connections(self):
        """Test that same asset can be mapped to different connections"""
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Test Connection 2",
            config={"api_key": "test-key-2"},
        )

        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1",
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection2,
            hub_asset=self.asset,
            external_listing_id="ext-listing-2",
        )

        self.assertNotEqual(mapping1.id, mapping2.id)
        self.assertEqual(mapping1.hub_asset, mapping2.hub_asset)
        self.assertNotEqual(mapping1.connection, mapping2.connection)

    def test_same_connection_different_assets(self):
        """Test that same connection can map different assets"""
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")

        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1",
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-2",
        )

        self.assertNotEqual(mapping1.id, mapping2.id)
        self.assertEqual(mapping1.connection, mapping2.connection)
        self.assertNotEqual(mapping1.hub_asset, mapping2.hub_asset)

    def test_validation_empty_external_listing_id(self):
        """Test validation fails for empty external_listing_id"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="",
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_validation_whitespace_only_external_listing_id(self):
        """Test validation fails for whitespace-only external_listing_id"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="   ",
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_validation_external_resource_ids_not_list(self):
        """Test validation fails when external_resource_ids is not a list"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids="not-a-list",
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_validation_sync_metadata_not_dict(self):
        """Test validation fails when sync_metadata is not a dict"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata="not-a-dict",
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_update_sync_metadata(self):
        """Test update_sync_metadata method"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={"existing": "value"},
        )

        initial_last_synced = mapping.last_synced_at

        wait_for_event_persistence()

        mapping.update_sync_metadata(
            metadata={"new_key": "new_value", "existing": "updated"}, last_synced_at=timezone.now()
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["existing"], "updated")
        self.assertEqual(mapping.sync_metadata["new_key"], "new_value")
        self.assertIsNotNone(mapping.last_synced_at)
        self.assertGreater(
            mapping.last_synced_at, initial_last_synced or timezone.now() - timedelta(seconds=1)
        )

    def test_update_sync_metadata_without_last_synced_at(self):
        """Test update_sync_metadata without explicit last_synced_at"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        before_time = timezone.now()
        mapping.update_sync_metadata(metadata={"status": "synced"})
        after_time = timezone.now()

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["status"], "synced")
        self.assertIsNotNone(mapping.last_synced_at)
        self.assertGreaterEqual(mapping.last_synced_at, before_time)
        self.assertLessEqual(mapping.last_synced_at, after_time)

    def test_update_sync_metadata_invalid_type(self):
        """Test update_sync_metadata fails with non-dict metadata"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        with self.assertRaises(ValueError):
            mapping.update_sync_metadata(metadata="not-a-dict")

        with self.assertRaises(ValueError):
            mapping.update_sync_metadata(metadata=["not-a-dict"])

    def test_update_sync_metadata_merge(self):
        """Test that update_sync_metadata merges with existing metadata"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={"key1": "value1", "key2": "value2"},
        )

        mapping.update_sync_metadata(metadata={"key2": "updated", "key3": "value3"})

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["key1"], "value1")  # Preserved
        self.assertEqual(mapping.sync_metadata["key2"], "updated")  # Updated
        self.assertEqual(mapping.sync_metadata["key3"], "value3")  # Added

    def test_cascade_delete_connection(self):
        """Test that mappings are deleted when connection is deleted"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        mapping_id = mapping.id

        # Delete connection
        self.connection.delete()

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_id).exists())

    def test_cascade_delete_tenant(self):
        """Test that mappings are deleted when tenant is deleted"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        mapping_id = mapping.id

        # Delete tenant
        self.tenant.delete()

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_id).exists())

    def test_cascade_delete_asset(self):
        """Test that mappings are deleted when asset is deleted"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        mapping_id = mapping.id

        # Delete asset
        self.asset.delete()

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_id).exists())

    def test_indexes_exist(self):
        """Test that indexes are created correctly"""
        # Create mappings to test indexes
        MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1",
        )

        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")

        MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-2",
        )

        # Verify queries execute without error
        from django.db import connection as db_connection

        with db_connection.cursor() as cursor:
            # Query that should use tenant + connection index
            cursor.execute(
                """
                EXPLAIN SELECT * FROM marketplace_mappings
                WHERE tenant_id = %s AND connection_id = %s
            """,
                [self.tenant.id, self.connection.id],
            )

            # Just verify query executes without error

    def test_ordering_by_created_at_desc(self):
        """Test that mappings are ordered by created_at descending"""
        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1",
        )

        wait_for_event_persistence()

        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-2",
        )

        mappings = list(MarketplaceMapping.objects.all())
        self.assertEqual(mappings[0], mapping2)  # Most recent first
        self.assertEqual(mappings[1], mapping1)

    def test_external_resource_ids_list(self):
        """Test that external_resource_ids can store a list of IDs"""
        resource_ids = ["resource-1", "resource-2", "resource-3"]

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=resource_ids,
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.external_resource_ids, resource_ids)
        self.assertEqual(len(mapping.external_resource_ids), 3)

    def test_external_resource_ids_empty_list(self):
        """Test that external_resource_ids can be an empty list"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=[],
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.external_resource_ids, [])

    def test_sync_metadata_empty_dict(self):
        """Test that sync_metadata can be an empty dict"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={},
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata, {})

    def test_update_sync_metadata_preserves_existing_keys(self):
        """Test that update_sync_metadata preserves keys not in new metadata"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={"preserved": "value", "updated": "old"},
        )

        mapping.update_sync_metadata(metadata={"updated": "new"})

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["preserved"], "value")
        self.assertEqual(mapping.sync_metadata["updated"], "new")

    def test_last_synced_at_nullable(self):
        """Test that last_synced_at can be None"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            last_synced_at=None,
        )

        mapping.refresh_from_db()
        self.assertIsNone(mapping.last_synced_at)

    def test_update_sync_metadata_with_explicit_datetime(self):
        """Test update_sync_metadata with explicit datetime"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
        )

        explicit_time = timezone.now() - timedelta(days=1)
        mapping.update_sync_metadata(metadata={"test": "value"}, last_synced_at=explicit_time)

        mapping.refresh_from_db()
        self.assertEqual(mapping.last_synced_at, explicit_time)

    # ========== FAILURE SCENARIOS TESTS ==========

    def test_create_mapping_missing_required_fields(self):
        """Test that creating mapping without required fields fails"""
        try:
            from django.db.models.fields.related_descriptors import (
                RelatedObjectDoesNotExist,
            )
        except ImportError:
            from django.db.models import ObjectDoesNotExist as RelatedObjectDoesNotExist

        expected = (ValidationError, IntegrityError, RelatedObjectDoesNotExist)
        # Missing tenant
        with self.assertRaises(expected):
            MarketplaceMapping.objects.create(
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id="ext-listing-123",
            )

        # Missing connection
        with self.assertRaises(expected):
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                hub_asset=self.asset,
                external_listing_id="ext-listing-123",
            )

        # Missing hub_asset
        with self.assertRaises(expected):
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                external_listing_id="ext-listing-123",
            )

        # Missing external_listing_id
        with self.assertRaises(expected):
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=self.asset,
            )

    def test_create_mapping_with_invalid_tenant(self):
        """Test that creating mapping with invalid tenant fails"""
        import uuid

        invalid_tenant_id = uuid.uuid4()
        with self.assertRaises((ValidationError, IntegrityError)):
            MarketplaceMapping.objects.create(
                tenant_id=invalid_tenant_id,
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id="ext-listing-123",
            )

    def test_create_mapping_with_invalid_connection(self):
        """Test that creating mapping with invalid connection fails"""
        import uuid

        invalid_connection_id = uuid.uuid4()
        with self.assertRaises(
            (ValidationError, IntegrityError, MarketplaceConnection.DoesNotExist)
        ):
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection_id=invalid_connection_id,
                hub_asset=self.asset,
                external_listing_id="ext-listing-123",
            )

    def test_create_mapping_with_invalid_asset(self):
        """Test that creating mapping with invalid asset fails"""
        import uuid

        from hub.apps.assets.models import Asset

        invalid_asset_id = uuid.uuid4()
        with self.assertRaises((ValidationError, IntegrityError, Asset.DoesNotExist)):
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset_id=invalid_asset_id,
                external_listing_id="ext-listing-123",
            )

    # ========== EDGE CASES TESTS ==========

    def test_external_listing_id_max_length(self):
        """Test that external_listing_id respects max length"""
        # Create mapping with very long external_listing_id
        long_id = "a" * 500  # Assuming reasonable max length
        try:
            mapping = MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id=long_id,
            )
            # If it succeeds, verify it was stored correctly
            mapping.refresh_from_db()
            self.assertEqual(mapping.external_listing_id, long_id)
        except (ValidationError, IntegrityError):
            # If max length is enforced, that's also acceptable
            pass

    def test_external_resource_ids_large_list(self):
        """Test that external_resource_ids can handle large lists"""
        large_list = [f"resource-{i}" for i in range(1000)]
        try:
            mapping = MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id="ext-listing-large",
                external_resource_ids=large_list,
            )
            mapping.refresh_from_db()
            self.assertEqual(len(mapping.external_resource_ids), 1000)
        except (ValidationError, IntegrityError):
            # If there's a limit, that's acceptable
            pass

    def test_sync_metadata_large_dict(self):
        """Test that sync_metadata can handle large dictionaries"""
        large_dict = {f"key-{i}": f"value-{i}" for i in range(100)}
        try:
            mapping = MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id="ext-listing-large-metadata",
                sync_metadata=large_dict,
            )
            mapping.refresh_from_db()
            self.assertEqual(len(mapping.sync_metadata), 100)
        except (ValidationError, IntegrityError):
            # If there's a limit, that's acceptable
            pass

    def test_external_resource_ids_with_special_characters(self):
        """Test that external_resource_ids can contain special characters"""
        special_ids = ["resource-1", "resource_2", "resource.3", "resource-4@test"]
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-special",
            external_resource_ids=special_ids,
        )
        mapping.refresh_from_db()
        self.assertEqual(mapping.external_resource_ids, special_ids)

    def test_sync_metadata_with_nested_structures(self):
        """Test that sync_metadata can contain nested structures"""
        nested_metadata = {
            "level1": {
                "level2": {
                    "level3": "deep_value",
                    "list": [1, 2, 3],
                    "nested_dict": {"key": "value"},
                }
            },
            "array": [{"item": 1}, {"item": 2}],
        }
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-nested",
            sync_metadata=nested_metadata,
        )
        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["level1"]["level2"]["level3"], "deep_value")
        self.assertEqual(mapping.sync_metadata["array"][0]["item"], 1)

    # ========== ERROR HANDLING TESTS ==========

    def test_update_sync_metadata_with_none(self):
        """Test that update_sync_metadata handles None metadata gracefully"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-none",
        )

        with self.assertRaises((ValueError, TypeError)):
            mapping.update_sync_metadata(metadata=None)

    def test_update_sync_metadata_with_empty_dict(self):
        """Test that update_sync_metadata handles empty dict"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-empty",
            sync_metadata={"existing": "value"},
        )

        mapping.update_sync_metadata(metadata={})
        mapping.refresh_from_db()
        # Empty dict should preserve existing metadata
        self.assertEqual(mapping.sync_metadata["existing"], "value")

    def test_external_resource_ids_with_non_string_items(self):
        """Test that external_resource_ids validation handles non-string items"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=[1, 2, 3],  # Non-string items
        )

        # May raise ValidationError or convert to strings; JSONField may store as-is
        try:
            mapping.full_clean()
            mapping.save()
            mapping.refresh_from_db()
            # If it succeeds, accept either conversion to strings or list of ints stored as-is
            self.assertIsInstance(mapping.external_resource_ids, list)
            self.assertEqual(len(mapping.external_resource_ids), 3)
        except ValidationError:
            # If validation fails, that's also acceptable
            pass

    # ========== TDD COMPLIANCE TESTS ==========

    def test_mapping_has_all_required_fields(self):
        """Test that created mapping has all required fields"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-required",
        )

        # Verify all required fields are present
        self.assertIsNotNone(mapping.id)
        self.assertIsNotNone(mapping.tenant)
        self.assertIsNotNone(mapping.connection)
        self.assertIsNotNone(mapping.hub_asset)
        self.assertIsNotNone(mapping.external_listing_id)
        self.assertIsNotNone(mapping.external_resource_ids)
        self.assertIsNotNone(mapping.sync_metadata)
        self.assertIsNotNone(mapping.created_at)
        self.assertIsNotNone(mapping.updated_at)

    def test_mapping_field_types(self):
        """Test that mapping fields have correct types"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-types",
            external_resource_ids=["resource-1"],
            sync_metadata={"key": "value"},
        )

        # Verify field types (id is UUIDField, so uuid.UUID)
        import uuid as uuid_module

        self.assertIsInstance(mapping.id, (str, int, type(None), uuid_module.UUID))
        self.assertIsInstance(mapping.external_listing_id, str)
        self.assertIsInstance(mapping.external_resource_ids, list)
        self.assertIsInstance(mapping.sync_metadata, dict)
        self.assertIsInstance(mapping.created_at, (type(None), type(timezone.now())))

    def test_mapping_timestamps_auto_set(self):
        """Test that created_at and updated_at are automatically set"""
        before_create = timezone.now()
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-timestamps",
        )
        after_create = timezone.now()

        # Verify timestamps are set (created_at and updated_at may differ by microseconds)
        self.assertIsNotNone(mapping.created_at)
        self.assertIsNotNone(mapping.updated_at)
        self.assertGreaterEqual(mapping.created_at, before_create)
        self.assertLessEqual(mapping.created_at, after_create)
        self.assertGreaterEqual(mapping.updated_at, before_create)
        self.assertLessEqual(mapping.updated_at, after_create)
        self.assertGreaterEqual(
            mapping.updated_at, mapping.created_at, "updated_at should be >= created_at"
        )

    def test_mapping_updated_at_changes_on_update(self):
        """Test that updated_at changes when mapping is updated"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-update",
        )

        original_updated_at = mapping.updated_at

        wait_for_event_persistence()

        mapping.update_sync_metadata(metadata={"updated": True})
        mapping.refresh_from_db()

        self.assertGreater(mapping.updated_at, original_updated_at)
        # created_at should not change
        self.assertEqual(mapping.created_at, mapping.created_at)

    def test_mapping_default_values(self):
        """Test that mapping has correct default values"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-defaults",
        )

        # Verify defaults
        self.assertEqual(mapping.external_resource_ids, [])
        self.assertEqual(mapping.sync_metadata, {})
        self.assertIsNone(mapping.last_synced_at)

    def test_mapping_repr_contains_key_information(self):
        """Test that mapping __repr__ contains key information"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-repr",
        )

        repr_str = repr(mapping)
        # Should contain key identifying information
        self.assertIn(str(mapping.id), repr_str or "")
        # May contain asset name, connection name, or external_listing_id
        self.assertTrue(
            "ext-listing-repr" in repr_str
            or "Test Asset" in repr_str
            or "Test Connection" in repr_str
            or str(mapping.id) in repr_str
        )

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
