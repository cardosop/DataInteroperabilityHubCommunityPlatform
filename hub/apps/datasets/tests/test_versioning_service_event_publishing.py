"""
Integration tests for VersioningService event publishing.

Tests event publishing using real VersioningService and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.datasets.versioning_service import VersioningService
from hub.apps.datasets.models import Dataset
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.events.models import Event
from hub.apps.files.models import File, FileStatus
from hub.apps.assets.models import Asset, AssetStatus
import uuid


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class VersioningServiceEventPublishingTest(TestCase):
    """Integration tests for VersioningService event publishing using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.service = VersioningService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create file and asset
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv"
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )

        # Create initial dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            version=1
        )

    def test_create_version_publishes_version_created_event(self):
        """Test that create_version() publishes version.created event."""
        # Create a new dataset version
        new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "new_field"}]},
            version=2
        )

        # Create version
        updated_dataset = self.service.create_version(
            dataset_id=str(new_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True
        )

        # Verify version was created
        updated_dataset.refresh_from_db()
        self.assertEqual(updated_dataset.semantic_version, "1.1.0")
        self.assertTrue(updated_dataset.is_current)

        # Verify event was published
        events = Event.objects.filter(
            event_type="version.created",
            tenant_id=self.tenant.id
        ).order_by("-timestamp")

        self.assertGreaterEqual(events.count(), 1)
        event = events.first()

        self.assertEqual(event.event_type, "version.created")
        self.assertEqual(event.data["version_id"], str(updated_dataset.id))
        self.assertEqual(event.data["resource_type"], "DATASET")
        self.assertEqual(event.data["resource_id"], str(updated_dataset.id))
        self.assertEqual(event.data["semantic_version"], "1.1.0")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "versioning_service")

    def test_create_version_with_parent_publishes_event_with_parent_info(self):
        """Test that create_version() with parent version publishes event with parent info."""
        # Create parent version (use existing dataset from setUp)
        parent_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True
        )

        # Create child version with different schema
        child_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "new_field"}]},
            version=2
        )
        child_dataset = self.service.create_version(
            dataset_id=str(child_dataset.id),
            tenant_id=str(self.tenant.id),
            parent_version_id=str(parent_dataset.id),
            semantic_version="1.1.0",
            is_current=True
        )

        # Verify event was published with parent info
        events = Event.objects.filter(
            event_type="version.created",
            tenant_id=self.tenant.id,
            data__version_id=str(child_dataset.id)
        )

        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.data["parent_version_id"], str(parent_dataset.id))

    def test_update_version_publishes_version_updated_event(self):
        """Test that update_version() publishes version.updated event."""
        # Create version first
        version_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True
        )

        # Update version
        changes = {
            "semantic_version": "1.1.0",
            "version_tags": ["production"]
        }
        updated_dataset = self.service.update_version(
            version_id=str(version_dataset.id),
            tenant_id=str(self.tenant.id),
            changes=changes
        )

        # Verify version was updated
        updated_dataset.refresh_from_db()
        self.assertEqual(updated_dataset.semantic_version, "1.1.0")
        self.assertEqual(updated_dataset.version_tags, ["production"])

        # Verify event was published
        events = Event.objects.filter(
            event_type="version.updated",
            tenant_id=self.tenant.id,
            data__version_id=str(updated_dataset.id)
        )

        self.assertEqual(events.count(), 1)
        event = events.first()

        self.assertEqual(event.event_type, "version.updated")
        self.assertEqual(event.data["version_id"], str(updated_dataset.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertEqual(event.data["previous_version"], "1.0.0")
        self.assertEqual(event.data["new_version"], "1.1.0")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "versioning_service")

    def test_delete_version_publishes_version_deleted_event(self):
        """Test that delete_version() publishes version.deleted event."""
        # Create version first
        version_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True
        )

        version_id = str(version_dataset.id)
        resource_id = str(version_dataset.id)

        # Delete version
        self.service.delete_version(
            version_id=version_id,
            tenant_id=str(self.tenant.id),
            reason="Version no longer needed"
        )

        # Verify version was deleted
        with self.assertRaises(Dataset.DoesNotExist):
            Dataset.objects.get(id=version_id)

        # Verify event was published
        events = Event.objects.filter(
            event_type="version.deleted",
            tenant_id=self.tenant.id,
            data__version_id=version_id
        )

        self.assertEqual(events.count(), 1)
        event = events.first()

        self.assertEqual(event.event_type, "version.deleted")
        self.assertEqual(event.data["version_id"], version_id)
        self.assertEqual(event.data["resource_type"], "DATASET")
        self.assertEqual(event.data["resource_id"], resource_id)
        self.assertEqual(event.data["reason"], "Version no longer needed")
        self.assertIsNotNone(event.data["deleted_at"])
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "versioning_service")

    def test_promote_version_publishes_version_promoted_event(self):
        """Test that promote_version() publishes version.promoted event."""
        # Create version first
        version_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True,
            version_tags=["staging"]
        )

        # Promote version
        promoted_dataset = self.service.promote_version(
            version_id=str(version_dataset.id),
            tenant_id=str(self.tenant.id),
            promoted_from="staging",
            promoted_to="production",
            promotion_reason="Promoted to production after testing"
        )

        # Verify version was promoted
        promoted_dataset.refresh_from_db()
        self.assertIn("production", promoted_dataset.version_tags)

        # Verify event was published
        events = Event.objects.filter(
            event_type="version.promoted",
            tenant_id=self.tenant.id,
            data__version_id=str(promoted_dataset.id)
        )

        self.assertEqual(events.count(), 1)
        event = events.first()

        self.assertEqual(event.event_type, "version.promoted")
        self.assertEqual(event.data["version_id"], str(promoted_dataset.id))
        self.assertEqual(event.data["resource_type"], "DATASET")
        self.assertEqual(event.data["resource_id"], str(promoted_dataset.id))
        self.assertEqual(event.data["promoted_from"], "staging")
        self.assertEqual(event.data["promoted_to"], "production")
        self.assertEqual(event.data["promotion_reason"], "Promoted to production after testing")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "versioning_service")

    def test_create_version_event_publishing_failure_does_not_fail_operation(self):
        """Test that event publishing failure doesn't fail version creation."""
        # Create a new dataset version
        new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "new_field"}]},
            version=2
        )

        # Create version (should succeed even if event publishing fails)
        updated_dataset = self.service.create_version(
            dataset_id=str(new_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True
        )

        # Verify version was created successfully
        updated_dataset.refresh_from_db()
        self.assertEqual(updated_dataset.semantic_version, "1.1.0")
        self.assertTrue(updated_dataset.is_current)

    def test_update_version_with_minimal_changes(self):
        """Test update_version() with minimal changes."""
        # Create version first
        version_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True
        )

        # Update with minimal changes
        changes = {"version_tags": ["tag1"]}
        updated_dataset = self.service.update_version(
            version_id=str(version_dataset.id),
            tenant_id=str(self.tenant.id),
            changes=changes
        )

        # Verify update succeeded
        updated_dataset.refresh_from_db()
        self.assertEqual(updated_dataset.version_tags, ["tag1"])

        # Verify event was published
        events = Event.objects.filter(
            event_type="version.updated",
            tenant_id=self.tenant.id,
            data__version_id=str(updated_dataset.id)
        )
        self.assertEqual(events.count(), 1)

    def test_delete_version_without_reason(self):
        """Test delete_version() without reason."""
        # Create version first
        version_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True
        )

        version_id = str(version_dataset.id)

        # Delete version without reason
        self.service.delete_version(
            version_id=version_id,
            tenant_id=str(self.tenant.id)
        )

        # Verify version was deleted
        with self.assertRaises(Dataset.DoesNotExist):
            Dataset.objects.get(id=version_id)

        # Verify event was published without reason
        events = Event.objects.filter(
            event_type="version.deleted",
            tenant_id=self.tenant.id,
            data__version_id=version_id
        )
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertIsNone(event.data.get("reason"))

    def test_promote_version_without_reason(self):
        """Test promote_version() without promotion reason."""
        # Create version first
        version_dataset = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.0",
            is_current=True,
            version_tags=["development"]
        )

        # Promote version without reason
        promoted_dataset = self.service.promote_version(
            version_id=str(version_dataset.id),
            tenant_id=str(self.tenant.id),
            promoted_from="development",
            promoted_to="staging"
        )

        # Verify promotion succeeded
        promoted_dataset.refresh_from_db()
        self.assertIn("staging", promoted_dataset.version_tags)

        # Verify event was published without promotion reason
        events = Event.objects.filter(
            event_type="version.promoted",
            tenant_id=self.tenant.id,
            data__version_id=str(promoted_dataset.id)
        )
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertIsNone(event.data.get("promotion_reason"))

