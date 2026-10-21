"""
Comprehensive unit and integration tests for ODPS event payloads.

Tests all ODPS event payload structures, validation, and end-to-end delivery
without mocks or stubs. Verifies payloads match schemas and are correctly
structured for event bus delivery.
"""

import uuid
from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hub.apps.core.events.event_types import (
    CURRENT_EVENT_VERSION,
    get_event_schema,
    validate_event_data,
)
from hub.apps.core.events.schema import EventSchema
from hub.apps.core.events.service_publishers import ODPSEventPublisher

User = get_user_model()


class ODPSEventPayloadsUnitTest(TestCase):
    """Unit tests for ODPS event payload structures and validation."""

    def test_odps_created_payload_structure(self):
        """Test odps.created event payload structure matches schema."""
        # Valid payload with all fields
        payload = {
            "contract_id": str(uuid.uuid4()),
            "asset_id": str(uuid.uuid4()),
            "status": "ACTIVE",
            "odps_version": "4.1",
            "original_format": "JSON",
        }

        is_valid, error = validate_event_data("odps.created", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema structure
        schema = get_event_schema("odps.created")
        self.assertIsNotNone(schema)
        self.assertIn("data", schema)
        self.assertIn("contract_id", schema["data"]["properties"])
        self.assertIn("odps_version", schema["data"]["properties"])
        self.assertIn("original_format", schema["data"]["properties"])

        # Verify required fields
        self.assertIn("contract_id", schema["data"]["required"])

    def test_odps_created_payload_minimal(self):
        """Test odps.created with minimal required fields only."""
        payload = {
            "contract_id": str(uuid.uuid4()),
        }

        is_valid, error = validate_event_data("odps.created", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_created_payload_null_optional_fields(self):
        """Test odps.created allows None for optional fields."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "asset_id": None,
            "status": None,
            "odps_version": None,
            "original_format": None,
        }

        is_valid, error = validate_event_data("odps.created", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_updated_payload_structure(self):
        """Test odps.updated event payload structure."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "changes": {"status": "ACTIVE", "version": "4.2"},
            "previous_status": "DRAFT",
            "new_status": "ACTIVE",
        }

        is_valid, error = validate_event_data("odps.updated", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.updated")
        self.assertIn("contract_id", schema["data"]["required"])
        self.assertIn("changes", schema["data"]["properties"])

    def test_odps_updated_payload_minimal(self):
        """Test odps.updated with minimal required fields."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "changes": {},
        }

        is_valid, error = validate_event_data("odps.updated", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_deleted_payload_structure(self):
        """Test odps.deleted event payload structure."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "deleted_at": datetime.now(UTC).isoformat(),
            "reason": "User requested deletion",
        }

        is_valid, error = validate_event_data("odps.deleted", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.deleted")
        self.assertIn("contract_id", schema["data"]["required"])
        self.assertIn("deleted_at", schema["data"]["properties"])

    def test_odps_deleted_payload_minimal(self):
        """Test odps.deleted with minimal required fields."""
        payload = {
            "contract_id": str(uuid.uuid4()),
        }

        is_valid, error = validate_event_data("odps.deleted", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_normalized_payload_structure(self):
        """Test odps.normalized event payload structure."""
        # Success case
        payload = {
            "contract_id": str(uuid.uuid4()),
            "normalization_status": "NORMALIZED_OK",
            "normalization_errors": None,
            "odps_version": "4.1",
        }

        is_valid, error = validate_event_data("odps.normalized", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # With errors case
        payload_with_errors = {
            "contract_id": str(uuid.uuid4()),
            "normalization_status": "NORMALIZATION_FAILED",
            "normalization_errors": ["Error 1", "Error 2"],
            "odps_version": "4.1",
        }

        is_valid, error = validate_event_data("odps.normalized", payload_with_errors)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.normalized")
        self.assertIn("contract_id", schema["data"]["required"])
        self.assertIn("normalization_status", schema["data"]["required"])
        self.assertIn("normalization_errors", schema["data"]["properties"])

    def test_odps_linked_payload_structure(self):
        """Test odps.linked event payload structure."""
        payload = {
            "odps_contract_id": str(uuid.uuid4()),
            "odcs_contract_id": str(uuid.uuid4()),
            "link_type": "bidirectional",
        }

        is_valid, error = validate_event_data("odps.linked", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.linked")
        self.assertIn("odps_contract_id", schema["data"]["required"])
        self.assertIn("odcs_contract_id", schema["data"]["required"])

    def test_odps_linked_payload_requires_both_contract_ids(self):
        """Test odps.linked requires both contract IDs."""
        # Missing odcs_contract_id
        payload = {
            "odps_contract_id": str(uuid.uuid4()),
        }

        is_valid, error = validate_event_data("odps.linked", payload)
        self.assertFalse(is_valid)
        self.assertIn("odcs_contract_id", error)

        # Missing odps_contract_id
        payload = {
            "odcs_contract_id": str(uuid.uuid4()),
        }

        is_valid, error = validate_event_data("odps.linked", payload)
        self.assertFalse(is_valid)
        self.assertIn("odps_contract_id", error)

    def test_odps_unlinked_payload_structure(self):
        """Test odps.unlinked event payload structure."""
        payload = {
            "odps_contract_id": str(uuid.uuid4()),
            "odcs_contract_id": str(uuid.uuid4()),
            "reason": "User requested unlink",
        }

        is_valid, error = validate_event_data("odps.unlinked", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.unlinked")
        self.assertIn("odps_contract_id", schema["data"]["required"])
        self.assertIn("odcs_contract_id", schema["data"]["required"])

    def test_odps_export_started_payload_structure(self):
        """Test odps.export.started event payload structure."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "JSON",
            "output_format": "JSON",
            "odps_version": "4.1",
        }

        is_valid, error = validate_event_data("odps.export.started", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.export.started")
        self.assertIn("contract_id", schema["data"]["required"])
        self.assertIn("export_format", schema["data"]["required"])

    def test_odps_export_started_payload_minimal(self):
        """Test odps.export.started with minimal required fields."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "JSON",
        }

        is_valid, error = validate_event_data("odps.export.started", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_completed_payload_structure(self):
        """Test odps.export.completed event payload structure."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "JSON",
            "output_format": "JSON",
            "file_size": 1024,
            "duration_ms": 500,
        }

        is_valid, error = validate_event_data("odps.export.completed", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.export.completed")
        self.assertIn("contract_id", schema["data"]["required"])
        self.assertIn("export_format", schema["data"]["required"])
        self.assertIn("file_size", schema["data"]["properties"])
        self.assertIn("duration_ms", schema["data"]["properties"])

    def test_odps_export_completed_payload_minimal(self):
        """Test odps.export.completed with minimal required fields."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "JSON",
        }

        is_valid, error = validate_event_data("odps.export.completed", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_failed_payload_structure(self):
        """Test odps.export.failed event payload structure."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "JSON",
            "error_message": "Export failed: Invalid format",
            "error_details": {"code": "EXPORT_ERROR", "line": 42},
        }

        is_valid, error = validate_event_data("odps.export.failed", payload)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Verify schema
        schema = get_event_schema("odps.export.failed")
        self.assertIn("contract_id", schema["data"]["required"])
        self.assertIn("export_format", schema["data"]["required"])
        self.assertIn("error_message", schema["data"]["required"])

    def test_odps_export_failed_payload_requires_error_message(self):
        """Test odps.export.failed requires error_message."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "JSON",
        }

        is_valid, error = validate_event_data("odps.export.failed", payload)
        self.assertFalse(is_valid)
        self.assertIn("error_message", error)

    def test_all_odps_event_payloads_have_schemas(self):
        """Test that all ODPS event types have defined schemas."""
        odps_event_types = [
            "odps.created",
            "odps.updated",
            "odps.deleted",
            "odps.normalized",
            "odps.linked",
            "odps.unlinked",
            "odps.export.started",
            "odps.export.completed",
            "odps.export.failed",
        ]

        for event_type in odps_event_types:
            schema = get_event_schema(event_type)
            self.assertIsNotNone(schema, f"Schema not found for {event_type}")
            self.assertIn("data", schema)
            self.assertIn("type", schema["data"])
            self.assertIn("required", schema["data"])
            self.assertIn("properties", schema["data"])

    def test_odps_payload_type_validation(self):
        """Test that payload types are correctly validated."""
        # Valid UUID string
        payload = {
            "contract_id": str(uuid.uuid4()),
        }
        is_valid, error = validate_event_data("odps.created", payload)
        self.assertTrue(is_valid, f"Valid UUID should pass: {error}")

        # Invalid type (integer instead of string UUID)
        invalid_payload = {
            "contract_id": 12345,
        }
        is_valid, error = validate_event_data("odps.created", invalid_payload)
        self.assertFalse(is_valid, "Invalid type should fail validation")
        self.assertIsNotNone(error)


@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False, EVENT_BUS_WRITE_BEHIND_ENABLED=False)
class ODPSEventPayloadsIntegrationTest(TestCase):
    """Integration tests for ODPS event payload delivery without mocks."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        # Create publisher and set attributes dynamically
        self.publisher = ODPSEventPublisher()
        self.publisher.tenant_id = self.tenant_id
        self.publisher.user_id = self.user_id
        # Update event publisher with tenant/user context
        self.publisher._event_publisher.tenant_id = self.tenant_id
        self.publisher._event_publisher.user_id = self.user_id

    def test_odps_created_payload_delivery(self):
        """Test odps.created event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_created(
            contract_id=contract_id,
            asset_id=asset_id,
            status="ACTIVE",
            odps_version="4.1",
            original_format="JSON",
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        # Verify event structure
        self.assertEqual(event.event_type, "odps.created")
        self.assertEqual(event.event_version, CURRENT_EVENT_VERSION)
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["asset_id"], asset_id)
        self.assertEqual(event.data["status"], "ACTIVE")
        self.assertEqual(event.data["odps_version"], "4.1")
        self.assertEqual(event.data["original_format"], "JSON")

        # Verify payload validation
        is_valid, error = validate_event_data("odps.created", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_updated_payload_delivery(self):
        """Test odps.updated event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        changes = {"status": "ACTIVE", "version": "4.2"}

        event_id = self.publisher.publish_odps_updated(
            contract_id=contract_id,
            changes=changes,
            previous_status="DRAFT",
            new_status="ACTIVE",
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.updated")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["changes"], changes)
        self.assertEqual(event.data["previous_status"], "DRAFT")
        self.assertEqual(event.data["new_status"], "ACTIVE")

        # Verify payload validation
        is_valid, error = validate_event_data("odps.updated", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_deleted_payload_delivery(self):
        """Test odps.deleted event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        reason = "User requested deletion"

        event_id = self.publisher.publish_odps_deleted(
            contract_id=contract_id,
            reason=reason,
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.deleted")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["reason"], reason)
        self.assertIn("deleted_at", event.data)

        # Verify payload validation
        is_valid, error = validate_event_data("odps.deleted", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_normalized_payload_delivery(self):
        """Test odps.normalized event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        normalization_errors = ["Error 1", "Error 2"]

        event_id = self.publisher.publish_odps_normalized(
            contract_id=contract_id,
            normalization_status="NORMALIZATION_FAILED",
            normalization_errors=normalization_errors,
            odps_version="4.1",
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.normalized")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["normalization_status"], "NORMALIZATION_FAILED")
        self.assertEqual(event.data["normalization_errors"], normalization_errors)
        self.assertEqual(event.data["odps_version"], "4.1")

        # Verify payload validation
        is_valid, error = validate_event_data("odps.normalized", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_linked_payload_delivery(self):
        """Test odps.linked event payload is correctly delivered."""
        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())
        link_type = "bidirectional"

        event_id = self.publisher.publish_odps_linked(
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            link_type=link_type,
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.linked")
        self.assertEqual(event.data["odps_contract_id"], odps_contract_id)
        self.assertEqual(event.data["odcs_contract_id"], odcs_contract_id)
        self.assertEqual(event.data["link_type"], link_type)

        # Verify payload validation
        is_valid, error = validate_event_data("odps.linked", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_unlinked_payload_delivery(self):
        """Test odps.unlinked event payload is correctly delivered."""
        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())
        reason = "User requested unlink"

        event_id = self.publisher.publish_odps_unlinked(
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            reason=reason,
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.unlinked")
        self.assertEqual(event.data["odps_contract_id"], odps_contract_id)
        self.assertEqual(event.data["odcs_contract_id"], odcs_contract_id)
        self.assertEqual(event.data["reason"], reason)

        # Verify payload validation
        is_valid, error = validate_event_data("odps.unlinked", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_export_started_payload_delivery(self):
        """Test odps.export.started event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        export_format = "JSON"
        output_format = "JSON"
        odps_version = "4.1"

        event_id = self.publisher.publish_odps_export_started(
            contract_id=contract_id,
            export_format=export_format,
            output_format=output_format,
            odps_version=odps_version,
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.export.started")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["export_format"], export_format)
        self.assertEqual(event.data["output_format"], output_format)
        self.assertEqual(event.data["odps_version"], odps_version)

        # Verify payload validation
        is_valid, error = validate_event_data("odps.export.started", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_export_completed_payload_delivery(self):
        """Test odps.export.completed event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        export_format = "JSON"
        output_format = "JSON"
        file_size = 2048
        duration_ms = 500

        event_id = self.publisher.publish_odps_export_completed(
            contract_id=contract_id,
            export_format=export_format,
            output_format=output_format,
            file_size=file_size,
            duration_ms=duration_ms,
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.export.completed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["export_format"], export_format)
        self.assertEqual(event.data["output_format"], output_format)
        self.assertEqual(event.data["file_size"], file_size)
        self.assertEqual(event.data["duration_ms"], duration_ms)

        # Verify payload validation
        is_valid, error = validate_event_data("odps.export.completed", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_odps_export_failed_payload_delivery(self):
        """Test odps.export.failed event payload is correctly delivered."""
        contract_id = str(uuid.uuid4())
        export_format = "JSON"
        error_message = "Export failed: Invalid format"
        error_details = {"code": "EXPORT_ERROR", "line": 42}

        event_id = self.publisher.publish_odps_export_failed(
            contract_id=contract_id,
            export_format=export_format,
            error_message=error_message,
            error_details=error_details,
        )

        # Verify event was published
        from hub.apps.core.events.models import Event

        event = Event.objects.get(event_id=event_id)

        self.assertEqual(event.event_type, "odps.export.failed")
        self.assertEqual(event.data["contract_id"], contract_id)
        self.assertEqual(event.data["export_format"], export_format)
        self.assertEqual(event.data["error_message"], error_message)
        self.assertEqual(event.data["error_details"], error_details)

        # Verify payload validation
        is_valid, error = validate_event_data("odps.export.failed", event.data)
        self.assertTrue(is_valid, f"Published payload validation failed: {error}")

    def test_all_odps_events_build_valid_full_events(self):
        """Test that all ODPS events can be built as complete valid events."""
        contract_id = str(uuid.uuid4())

        test_cases = [
            {
                "event_type": "odps.created",
                "data": {
                    "contract_id": contract_id,
                    "status": "ACTIVE",
                    "odps_version": "4.1",
                },
            },
            {
                "event_type": "odps.updated",
                "data": {
                    "contract_id": contract_id,
                    "changes": {"status": "ACTIVE"},
                },
            },
            {
                "event_type": "odps.deleted",
                "data": {
                    "contract_id": contract_id,
                    "reason": "Test deletion",
                },
            },
            {
                "event_type": "odps.normalized",
                "data": {
                    "contract_id": contract_id,
                    "normalization_status": "NORMALIZED_OK",
                },
            },
            {
                "event_type": "odps.linked",
                "data": {
                    "odps_contract_id": contract_id,
                    "odcs_contract_id": str(uuid.uuid4()),
                },
            },
            {
                "event_type": "odps.unlinked",
                "data": {
                    "odps_contract_id": contract_id,
                    "odcs_contract_id": str(uuid.uuid4()),
                },
            },
            {
                "event_type": "odps.export.started",
                "data": {
                    "contract_id": contract_id,
                    "export_format": "JSON",
                },
            },
            {
                "event_type": "odps.export.completed",
                "data": {
                    "contract_id": contract_id,
                    "export_format": "JSON",
                },
            },
            {
                "event_type": "odps.export.failed",
                "data": {
                    "contract_id": contract_id,
                    "export_format": "JSON",
                    "error_message": "Test error",
                },
            },
        ]

        for test_case in test_cases:
            event = EventSchema.build_event(
                event_type=test_case["event_type"],
                data=test_case["data"],
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

            # Validate full event structure
            is_valid, error = EventSchema.validate_event(event)
            self.assertTrue(
                is_valid,
                f"Full event validation failed for {test_case['event_type']}: {error}",
            )

            # Validate event data specifically
            is_data_valid, data_error = validate_event_data(test_case["event_type"], event["data"])
            self.assertTrue(
                is_data_valid,
                f"Event data validation failed for {test_case['event_type']}: {data_error}",
            )

            # Verify event structure
            self.assertEqual(event["event_type"], test_case["event_type"])
            self.assertEqual(event["event_version"], CURRENT_EVENT_VERSION)
            self.assertIn("event_id", event)
            self.assertIn("timestamp", event)
            self.assertIn("source", event)
            self.assertIn("data", event)
