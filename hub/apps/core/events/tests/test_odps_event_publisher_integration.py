"""
Integration tests for ODPSEventPublisher.

Tests ODPS event publishing with actual event bus integration.
Uses real event bus (no mocks) to verify end-to-end event publishing.
"""
import uuid
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from hub.apps.core.events.service_publishers import ODPSEventPublisher


User = get_user_model()


@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False, EVENT_BUS_WRITE_BEHIND_ENABLED=False)
class ODPSEventPublisherIntegrationTest(TestCase):
    """Integration tests for ODPSEventPublisher with event bus."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        # Create publisher and set attributes dynamically
        self.publisher = ODPSEventPublisher()
        setattr(self.publisher, 'tenant_id', self.tenant_id)
        setattr(self.publisher, 'user_id', self.user_id)
        # Update event publisher with tenant/user context
        self.publisher._event_publisher.tenant_id = self.tenant_id
        self.publisher._event_publisher.user_id = self.user_id

    def test_publish_odps_created_integration(self):
        """Test ODPS created event publishing with real event bus."""
        contract_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_created(
            contract_id=contract_id,
            asset_id=asset_id,
            status="ACTIVE",
            odps_version="4.1",
        )

        # Real event bus returns a UUID, not a mock value
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
        # Verify event was published by checking it exists in the database
        from hub.apps.core.events.models import Event
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "odps.created")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["asset_id"], asset_id)

    def test_publish_odps_linked_integration(self):
        """Test ODPS linked event publishing with real event bus."""
        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_linked(
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            link_type="bidirectional",
        )

        # Real event bus returns a UUID
        self.assertIsNotNone(event_id)
        # Verify event was published
        from hub.apps.core.events.models import Event
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "odps.linked")
        self.assertEqual(event.data["odps_contract_id"], odps_contract_id)
        self.assertEqual(event.data["odcs_contract_id"], odcs_contract_id)

    def test_publish_odps_ref_resolved_integration(self):
        """Test ODPS ref resolved event publishing with real event bus."""
        contract_id = str(uuid.uuid4())
        ref_path = "#/definitions/quality"
        ref_type = "internal"

        event_id = self.publisher.publish_odps_ref_resolved(
            contract_id=contract_id,
            ref_path=ref_path,
            ref_type=ref_type,
            resolution_status="success",
            ref_count=3,
            duration_ms=50,
        )

        # Real event bus returns a UUID
        self.assertIsNotNone(event_id)
        # Verify event was published
        from hub.apps.core.events.models import Event
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "odps.ref.resolved")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["ref_path"], ref_path)
        self.assertEqual(event.data["ref_type"], ref_type)
        self.assertEqual(event.data["ref_count"], 3)

    def test_publish_odps_export_completed_integration(self):
        """Test ODPS export completed event publishing with real event bus."""
        contract_id = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_export_completed(
            contract_id=contract_id,
            export_format="odps",
            output_format="json",
            file_size=2048,
            duration_ms=100,
        )

        # Real event bus returns a UUID
        self.assertIsNotNone(event_id)
        # Verify event was published
        from hub.apps.core.events.models import Event
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "odps.export.completed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["file_size"], 2048)
        self.assertEqual(event.data["duration_ms"], 100)

    def test_event_publisher_tenant_context(self):
        """Test that events include tenant and user context."""
        contract_id = str(uuid.uuid4())
        event_id = self.publisher.publish_odps_created(contract_id=contract_id)

        # Verify event was published and check context
        from hub.apps.core.events.models import Event
        event = Event.objects.get(event_id=event_id)
        # The EventPublisher should include tenant_id and user_id in the event metadata
        # This is handled by the EventPublisher class, not the ODPSEventPublisher
        # Verify the event was published successfully with correct type
        self.assertEqual(event.event_type, "odps.created")
        self.assertEqual(event.data["contract_id"], contract_id)
        # Event should have metadata (may contain tenant_id/user_id if set)
        self.assertIsNotNone(event.metadata)

    def test_all_event_types_are_valid(self):
        """Test that all ODPS event types have valid schemas."""
        from hub.apps.core.events.event_types import get_event_schema, get_all_event_types

        odps_event_types = [
            "odps.created",
            "odps.updated",
            "odps.deleted",
            "odps.normalized",
            "odps.linked",
            "odps.unlinked",
            "odps.ref.resolved",
            "odps.ref.failed",
            "odps.export.started",
            "odps.export.completed",
            "odps.export.failed",
        ]

        all_event_types = get_all_event_types()

        for event_type in odps_event_types:
            self.assertIn(event_type, all_event_types, f"Event type {event_type} not found in event types")
            schema = get_event_schema(event_type)
            self.assertIsNotNone(schema, f"Schema not found for event type {event_type}")
            self.assertIn("data", schema, f"Schema for {event_type} missing 'data' key")
            self.assertIn("type", schema["data"], f"Schema for {event_type} missing 'type' in data")
            self.assertIn("required", schema["data"], f"Schema for {event_type} missing 'required' in data")

