"""
Integration tests for NormalizationEventPublisher.

Tests event publishing using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
import uuid
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.core.events.service_publishers import NormalizationEventPublisher
from hub.apps.core.events.models import Event

uid = uuid.uuid4().hex[:8]


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class NormalizationEventPublisherIntegrationTest(TestCase):
    """Integration tests for NormalizationEventPublisher using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        class TestNormalizationService(NormalizationEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        self.service = TestNormalizationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_publish_normalization_started_event(self):
        """Test publishing normalization.started event with real EventPublisher."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODPS",
            spec_version="4.1",
            source_format="JSON"
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.started")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["normalization_type"], "ODPS")
        self.assertEqual(event.data["spec_version"], "4.1")
        self.assertEqual(event.data["source_format"], "JSON")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "normalization_service")
        self.assertIn("normalization", event.metadata["tags"])
        self.assertIn("started", event.metadata["tags"])

    def test_publish_normalization_started_with_minimal_data(self):
        """Test publishing normalization.started event with minimal required data."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODCS"
        )

        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.started")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["normalization_type"], "ODCS")
        self.assertIsNone(event.data.get("spec_version"))
        self.assertIsNone(event.data.get("source_format"))

    def test_publish_normalization_completed_event(self):
        """Test publishing normalization.completed event with real EventPublisher."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_completed(
            contract_id=contract_id,
            normalization_status="SUCCESS",
            normalization_errors=None,
            normalization_warnings=["Warning: Missing optional field"],
            duration_ms=1500,
            spec_version="4.1"
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.completed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["normalization_status"], "SUCCESS")
        self.assertIsNone(event.data.get("normalization_errors"))
        self.assertEqual(event.data["normalization_warnings"], ["Warning: Missing optional field"])
        self.assertEqual(event.data["duration_ms"], 1500)
        self.assertEqual(event.data["spec_version"], "4.1")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "normalization_service")
        self.assertIn("normalization", event.metadata["tags"])
        self.assertIn("completed", event.metadata["tags"])

    def test_publish_normalization_completed_with_errors(self):
        """Test publishing normalization.completed event with errors."""
        import uuid
        contract_id = str(uuid.uuid4())

        errors = ["Error: Invalid schema", "Error: Missing required field"]
        event_id = self.service.publish_normalization_completed(
            contract_id=contract_id,
            normalization_status="FAILED",
            normalization_errors=errors,
            normalization_warnings=None,
            duration_ms=2000
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.completed")
        self.assertEqual(event.data["normalization_status"], "FAILED")
        self.assertEqual(event.data["normalization_errors"], errors)
        self.assertIsNone(event.data.get("normalization_warnings"))

    def test_publish_normalization_completed_with_minimal_data(self):
        """Test publishing normalization.completed event with minimal required data."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_completed(
            contract_id=contract_id,
            normalization_status="SUCCESS"
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.completed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["normalization_status"], "SUCCESS")
        self.assertIsNone(event.data.get("normalization_errors"))
        self.assertIsNone(event.data.get("normalization_warnings"))
        self.assertIsNone(event.data.get("duration_ms"))
        self.assertIsNone(event.data.get("spec_version"))

    def test_publish_normalization_failed_event(self):
        """Test publishing normalization.failed event with real EventPublisher."""
        import uuid
        contract_id = str(uuid.uuid4())

        error_details = {"code": "SCHEMA_VALIDATION_ERROR", "field": "product.details"}
        errors = ["Schema validation failed", "Missing required field: name"]

        event_id = self.service.publish_normalization_failed(
            contract_id=contract_id,
            error_message="Normalization failed due to schema validation errors",
            error_details=error_details,
            normalization_errors=errors,
            retry_count=2,
            spec_version="4.1"
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.failed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["error_message"], "Normalization failed due to schema validation errors")
        self.assertEqual(event.data["error_details"], error_details)
        self.assertEqual(event.data["normalization_errors"], errors)
        self.assertEqual(event.data["retry_count"], 2)
        self.assertEqual(event.data["spec_version"], "4.1")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "normalization_service")
        self.assertIn("normalization", event.metadata["tags"])
        self.assertIn("failed", event.metadata["tags"])

    def test_publish_normalization_failed_with_minimal_data(self):
        """Test publishing normalization.failed event with minimal required data."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_failed(
            contract_id=contract_id,
            error_message="Normalization failed"
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "normalization.failed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["error_message"], "Normalization failed")
        self.assertIsNone(event.data.get("error_details"))
        self.assertIsNone(event.data.get("normalization_errors"))
        self.assertIsNone(event.data.get("retry_count"))
        self.assertIsNone(event.data.get("spec_version"))

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include correct tenant_id and user_id."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODPS"
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_event_timestamp_is_set(self):
        """Test that events have timestamps."""
        import uuid
        contract_id = str(uuid.uuid4())

        event_id = self.service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODPS"
        )

        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.timestamp)
        self.assertIsInstance(event.timestamp, timezone.datetime)

    def test_event_tags_are_set(self):
        """Test that events have correct tags."""
        import uuid
        contract_id = str(uuid.uuid4())

        # Test started event tags
        started_event_id = self.service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODPS"
        )
        started_event = Event.objects.get(event_id=started_event_id)
        self.assertIn("normalization", started_event.metadata["tags"])
        self.assertIn("started", started_event.metadata["tags"])

        # Test completed event tags
        completed_event_id = self.service.publish_normalization_completed(
            contract_id=contract_id,
            normalization_status="SUCCESS"
        )
        completed_event = Event.objects.get(event_id=completed_event_id)
        self.assertIn("normalization", completed_event.metadata["tags"])
        self.assertIn("completed", completed_event.metadata["tags"])

        # Test failed event tags
        failed_event_id = self.service.publish_normalization_failed(
            contract_id=contract_id,
            error_message="Test error"
        )
        failed_event = Event.objects.get(event_id=failed_event_id)
        self.assertIn("normalization", failed_event.metadata["tags"])
        self.assertIn("failed", failed_event.metadata["tags"])

    def test_publisher_initialization_without_tenant_or_user(self):
        """Test that publisher can be initialized without tenant_id or user_id."""
        class TestService(NormalizationEventPublisher):
            def __init__(self):
                super().__init__()

        service = TestService()
        self.assertIsNotNone(service._event_publisher)

    def test_publisher_uses_service_tenant_and_user(self):
        """Test that publisher uses tenant_id and user_id from service."""
        class TestService(NormalizationEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        service = TestService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        import uuid
        contract_id = str(uuid.uuid4())
        event_id = service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODPS"
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_publisher_allows_override_tenant_and_user(self):
        """Test that publisher allows overriding tenant_id and user_id per event."""
        import uuid
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        contract_id = str(uuid.uuid4())
        event_id = self.service.publish_normalization_started(
            contract_id=contract_id,
            normalization_type="ODPS",
            tenant_id=str(other_tenant.id),
            user_id=str(other_user.id)
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(other_tenant.id))
        self.assertEqual(str(event.user_id), str(other_user.id))

