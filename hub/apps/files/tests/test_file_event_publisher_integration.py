"""
Integration tests for FileEventPublisher.

Tests event publishing using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.core.events.service_publishers import FileEventPublisher
from hub.apps.core.events.models import Event


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class FileEventPublisherIntegrationTest(TestCase):
    """Integration tests for FileEventPublisher using real EventPublisher."""

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

        # Create a test service with FileEventPublisher
        class TestFileService(FileEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        self.service = TestFileService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create a test file
        self.test_file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test_file.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test-bucket/test_file.csv",
            status=FileStatus.ACTIVE,
            content_sha256="abc123def456"
        )

    def test_publish_file_created_event(self):
        """Test publishing file.created event with real EventPublisher."""
        event_id = self.service.publish_file_created(
            file_id=str(self.test_file.id),
            name=self.test_file.name,
            content_type=self.test_file.content_type,
            size=self.test_file.size,
            status=self.test_file.status,
            content_sha256=self.test_file.content_sha256
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.created")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertEqual(event.data["name"], self.test_file.name)
        self.assertEqual(event.data["content_type"], self.test_file.content_type)
        self.assertEqual(event.data["size"], self.test_file.size)
        self.assertEqual(event.data["status"], self.test_file.status)
        self.assertEqual(event.data["content_sha256"], self.test_file.content_sha256)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        # Note: EventSchema.build_event hardcodes "hub" as service name
        # The EventPublisher's service_name is used for logging/metrics, not event source
        self.assertEqual(event.source_service, "file_service")

    def test_publish_file_updated_event(self):
        """Test publishing file.updated event with real EventPublisher."""
        changes = {
            "status": {"old": FileStatus.PENDING, "new": FileStatus.ACTIVE},
            "size": {"old": 1024, "new": 2048}
        }
        event_id = self.service.publish_file_updated(
            file_id=str(self.test_file.id),
            changes=changes,
            previous_status=FileStatus.PENDING.value,
            new_status=FileStatus.ACTIVE.value
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.updated")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertEqual(event.data["previous_status"], FileStatus.PENDING.value)
        self.assertEqual(event.data["new_status"], FileStatus.ACTIVE.value)

    def test_publish_file_deleted_event(self):
        """Test publishing file.deleted event with real EventPublisher."""
        reason = "User requested deletion"
        event_id = self.service.publish_file_deleted(
            file_id=str(self.test_file.id),
            reason=reason
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.deleted")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertEqual(event.data["reason"], reason)
        self.assertIn("deleted_at", event.data)

    def test_publish_file_uploaded_event(self):
        """Test publishing file.uploaded event with real EventPublisher."""
        event_id = self.service.publish_file_uploaded(
            file_id=str(self.test_file.id),
            file_size=self.test_file.size,
            content_type=self.test_file.content_type,
            upload_duration_ms=500,
            content_sha256=self.test_file.content_sha256
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.uploaded")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertEqual(event.data["file_size"], self.test_file.size)
        self.assertEqual(event.data["content_type"], self.test_file.content_type)
        self.assertEqual(event.data["upload_duration_ms"], 500)
        self.assertEqual(event.data["content_sha256"], self.test_file.content_sha256)

    def test_publish_file_downloaded_event(self):
        """Test publishing file.downloaded event with real EventPublisher."""
        event_id = self.service.publish_file_downloaded(
            file_id=str(self.test_file.id),
            download_duration_ms=300,
            download_size=self.test_file.size
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.downloaded")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertEqual(event.data["download_duration_ms"], 300)
        self.assertEqual(event.data["download_size"], self.test_file.size)

    def test_publish_file_created_with_minimal_data(self):
        """Test publishing file.created event with only required fields."""
        event_id = self.service.publish_file_created(
            file_id=str(self.test_file.id)
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.created")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertIsNone(event.data.get("name"))
        self.assertIsNone(event.data.get("content_type"))
        self.assertIsNone(event.data.get("size"))
        self.assertIsNone(event.data.get("status"))
        self.assertIsNone(event.data.get("content_sha256"))

    def test_publish_file_updated_with_minimal_data(self):
        """Test publishing file.updated event with only required fields."""
        changes = {"status": {"old": "PENDING", "new": "ACTIVE"}}
        event_id = self.service.publish_file_updated(
            file_id=str(self.test_file.id),
            changes=changes
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.updated")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertIsNone(event.data.get("previous_status"))
        self.assertIsNone(event.data.get("new_status"))

    def test_publish_file_deleted_without_reason(self):
        """Test publishing file.deleted event without reason."""
        event_id = self.service.publish_file_deleted(
            file_id=str(self.test_file.id)
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.deleted")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertIsNone(event.data.get("reason"))
        self.assertIn("deleted_at", event.data)

    def test_publish_file_uploaded_with_minimal_data(self):
        """Test publishing file.uploaded event with only required fields."""
        event_id = self.service.publish_file_uploaded(
            file_id=str(self.test_file.id)
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.uploaded")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertIsNone(event.data.get("file_size"))
        self.assertIsNone(event.data.get("content_type"))
        self.assertIsNone(event.data.get("upload_duration_ms"))
        self.assertIsNone(event.data.get("content_sha256"))

    def test_publish_file_downloaded_with_minimal_data(self):
        """Test publishing file.downloaded event with only required fields."""
        event_id = self.service.publish_file_downloaded(
            file_id=str(self.test_file.id)
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "file.downloaded")
        self.assertEqual(event.data["file_id"], str(self.test_file.id))
        self.assertIsNone(event.data.get("download_duration_ms"))
        self.assertIsNone(event.data.get("download_size"))

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include tenant_id and user_id in source."""
        event_id = self.service.publish_file_created(
            file_id=str(self.test_file.id)
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        # Note: EventSchema.build_event hardcodes "hub" as service name
        # The EventPublisher's service_name is used for logging/metrics, not event source
        self.assertEqual(event.source_service, "file_service")

    def test_event_timestamp_is_set(self):
        """Test that events have timestamp set."""
        before_publish = timezone.now()
        event_id = self.service.publish_file_created(
            file_id=str(self.test_file.id)
        )
        after_publish = timezone.now()

        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.timestamp)
        # Verify timestamp is between before and after
        self.assertGreaterEqual(event.timestamp, before_publish)
        self.assertLessEqual(event.timestamp, after_publish)

