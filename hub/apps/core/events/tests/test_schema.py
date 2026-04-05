"""
Tests for event schema validation.
"""
import uuid
from django.test import TestCase
from datetime import datetime

from hub.apps.core.events.schema import EventSchema, BASE_EVENT_SCHEMA, get_event_schema


class EventSchemaTest(TestCase):
    """Test event schema validation and building."""

    def test_build_event_success(self):
        """Test building a valid event."""
        contract_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        event = EventSchema.build_event(
            event_type="contract.created",
            data={"contract_id": contract_id},
            tenant_id=tenant_id,
            user_id=user_id
        )

        # event_id must be a valid UUID
        uuid.UUID(event["event_id"])
        self.assertEqual(event["event_type"], "contract.created")
        self.assertEqual(event["event_version"], "1.0.0")
        # timestamp must be a valid ISO 8601 string
        datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        # source must carry the tenant_id and user_id we passed in
        self.assertEqual(event["source"]["tenant_id"], tenant_id)
        self.assertEqual(event["source"]["user_id"], user_id)
        # data must preserve the contract_id we passed in
        self.assertIn("data", event)
        self.assertEqual(event["data"]["contract_id"], contract_id)

    def test_build_event_preserves_all_data(self):
        """Test that ALL data fields passed in are preserved in the output."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "asset_id": str(uuid.uuid4()),
            "status": "active",
            "version": 3,
            "tags": ["finance", "public"],
        }

        event = EventSchema.build_event(
            event_type="contract.created",
            data=data,
        )

        self.assertEqual(event["data"], data)

    def test_validate_event_success(self):
        """Test validating a valid event."""
        event = EventSchema.build_event(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())}
        )

        is_valid, error = EventSchema.validate_event(event)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_event_missing_field(self):
        """Test validating event with missing required field."""
        event = {
            "event_type": "contract.created",
            "data": {}
        }

        is_valid, error = EventSchema.validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

    def test_validate_event_invalid_uuid(self):
        """Test validating event with invalid UUID."""
        event = EventSchema.build_event(
            event_type="contract.created",
            data={}
        )
        event["event_id"] = "invalid-uuid"

        is_valid, error = EventSchema.validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("event_id must be a valid UUID", error)

    def test_validate_event_invalid_event_type(self):
        """Test validating event with invalid event type."""
        event = EventSchema.build_event(
            event_type="InvalidEventType",
            data={}
        )

        is_valid, error = EventSchema.validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("event_type must match pattern", error)

    def test_validate_event_invalid_version(self):
        """Test validating event with invalid version."""
        event = EventSchema.build_event(
            event_type="contract.created",
            data={}
        )
        event["event_version"] = "invalid"

        is_valid, error = EventSchema.validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("event_version must be semantic version", error)

    def test_get_event_schema(self):
        """Test getting event schema for specific type."""
        schema = get_event_schema("contract.created")
        self.assertIn("properties", schema)
        self.assertIn("data", schema["properties"])

    def test_get_odps_event_schema(self):
        """Test getting merged schema for ODPS event types."""
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

        for event_type in odps_event_types:
            schema = get_event_schema(event_type)
            # Should have base schema structure
            self.assertIn("properties", schema)
            self.assertIn("data", schema["properties"])
            # Should have event-specific data schema merged
            data_schema = schema["properties"]["data"]
            self.assertIn("required", data_schema)
            self.assertIn("properties", data_schema)
            # Should have base schema fields
            self.assertIn("event_id", schema["properties"])
            self.assertIn("event_type", schema["properties"])
            self.assertIn("timestamp", schema["properties"])

