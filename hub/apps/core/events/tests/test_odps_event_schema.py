"""
Unit tests for ODPS event schema validation.

Tests comprehensive schema validation for all ODPS event types,
including lifecycle, $ref resolution, and export events.
"""

import uuid
from datetime import UTC, datetime

from django.test import TestCase

from hub.apps.core.events.event_types import (
    CURRENT_EVENT_VERSION,
    get_all_event_types,
    validate_event_data,
)
from hub.apps.core.events.event_types import (
    get_event_schema as get_event_type_schema,
)
from hub.apps.core.events.schema import EventSchema, get_event_schema


class ODPSEventSchemaTest(TestCase):
    """Test ODPS event schema validation."""

    def test_odps_created_schema_exists(self):
        """Test that odps.created schema is defined."""
        schema = get_event_schema("odps.created")
        self.assertIsNotNone(schema)
        self.assertIn("properties", schema)
        self.assertIn("data", schema["properties"])

        # Check required fields
        data_schema = schema["properties"]["data"]
        self.assertIn("required", data_schema)
        self.assertIn("contract_id", data_schema["required"])

    def test_odps_created_schema_validation_valid(self):
        """Test validating valid odps.created event data."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "asset_id": str(uuid.uuid4()),
            "status": "ACTIVE",
            "odps_version": "4.1",
            "original_format": "JSON",
        }
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
        self.assertIsNone(error)

    def test_odps_created_schema_validation_minimal(self):
        """Test validating odps.created with minimal required fields."""
        data = {"contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
        self.assertIsNone(error)

    def test_odps_created_schema_validation_missing_required(self):
        """Test validating odps.created with missing required field."""
        data = {}
        is_valid, error = validate_event_data("odps.created", data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field: contract_id", error)

    def test_odps_created_schema_validation_null_optional_fields(self):
        """Test that optional fields can be None."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "status": None,
            "odps_version": None,
            "original_format": None,
        }
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_updated_schema_validation(self):
        """Test odps.updated event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "changes": {"status": "ACTIVE"},
            "previous_status": "DRAFT",
            "new_status": "ACTIVE",
        }
        is_valid, error = validate_event_data("odps.updated", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_deleted_schema_validation(self):
        """Test odps.deleted event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "deleted_at": datetime.now(UTC).isoformat(),
            "reason": "User requested deletion",
        }
        is_valid, error = validate_event_data("odps.deleted", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_normalized_schema_validation(self):
        """Test odps.normalized event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "normalization_status": "NORMALIZED_OK",
            "normalization_errors": None,
            "odps_version": "4.1",
        }
        is_valid, error = validate_event_data("odps.normalized", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_normalized_schema_validation_with_errors(self):
        """Test odps.normalized with normalization errors."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "normalization_status": "NORMALIZED_WITH_ERRORS",
            "normalization_errors": ["Error 1", "Error 2"],
            "odps_version": None,
        }
        is_valid, error = validate_event_data("odps.normalized", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_linked_schema_validation(self):
        """Test odps.linked event schema validation."""
        data = {
            "odps_contract_id": str(uuid.uuid4()),
            "odcs_contract_id": str(uuid.uuid4()),
            "link_type": "bidirectional",
        }
        is_valid, error = validate_event_data("odps.linked", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_linked_schema_validation_missing_required(self):
        """Test odps.linked with missing required fields."""
        data = {
            "odps_contract_id": str(uuid.uuid4())
            # Missing odcs_contract_id
        }
        is_valid, error = validate_event_data("odps.linked", data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

    def test_odps_unlinked_schema_validation(self):
        """Test odps.unlinked event schema validation."""
        data = {
            "odps_contract_id": str(uuid.uuid4()),
            "odcs_contract_id": str(uuid.uuid4()),
            "reason": "User requested unlink",
        }
        is_valid, error = validate_event_data("odps.unlinked", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_ref_resolved_schema_validation(self):
        """Test odps.ref.resolved event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "ref_path": "#/definitions/quality",
            "ref_type": "internal",
            "resolution_status": "success",
            "ref_count": 5,
            "duration_ms": 100,
        }
        is_valid, error = validate_event_data("odps.ref.resolved", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_ref_resolved_schema_validation_minimal(self):
        """Test odps.ref.resolved with minimal required fields."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "ref_path": "#/test",
            "ref_type": "internal",
            "resolution_status": "success",
        }
        is_valid, error = validate_event_data("odps.ref.resolved", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_ref_failed_schema_validation(self):
        """Test odps.ref.failed event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "ref_path": "https://example.com/schema.json",
            "ref_type": "external",
            "error_message": "Failed to resolve external reference",
            "error_code": "RESOLUTION_FAILED",
            "error_details": {"timeout": True, "retry_count": 3},
        }
        is_valid, error = validate_event_data("odps.ref.failed", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_started_schema_validation(self):
        """Test odps.export.started event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "odps",
            "output_format": "json",
            "odps_version": "4.1",
        }
        is_valid, error = validate_event_data("odps.export.started", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_completed_schema_validation(self):
        """Test odps.export.completed event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "odps",
            "output_format": "json",
            "file_size": 2048,
            "duration_ms": 100,
        }
        is_valid, error = validate_event_data("odps.export.completed", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_failed_schema_validation(self):
        """Test odps.export.failed event schema validation."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "odps",
            "error_message": "Export failed: Invalid format",
            "error_details": {"error_code": "INVALID_FORMAT", "line": 42},
        }
        is_valid, error = validate_event_data("odps.export.failed", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_failed_schema_validation_missing_error_message(self):
        """Test odps.export.failed with missing required error_message."""
        data = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "odps",
            # Missing error_message
        }
        is_valid, error = validate_event_data("odps.export.failed", data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field: error_message", error)

    def test_all_odps_event_types_in_schema_registry(self):
        """Test that all ODPS event types are in the schema registry."""
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

        all_types = get_all_event_types()
        for event_type in odps_event_types:
            self.assertIn(
                event_type, all_types, f"ODPS event type {event_type} not found in registry"
            )

    def test_odps_schemas_merged_with_base_schema(self):
        """Test that ODPS schemas are properly merged with base schema."""
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
            # Should have base schema properties
            self.assertIn("event_id", schema["properties"])
            self.assertIn("event_type", schema["properties"])
            self.assertIn("event_version", schema["properties"])
            self.assertIn("timestamp", schema["properties"])
            self.assertIn("source", schema["properties"])
            self.assertIn("data", schema["properties"])
            # Should have event-specific data schema
            self.assertIn("required", schema["properties"]["data"])
            self.assertIn("properties", schema["properties"]["data"])

    def test_odps_event_build_and_validate_full_event(self):
        """Test building and validating a complete ODPS event."""
        contract_id = str(uuid.uuid4())
        event = EventSchema.build_event(
            event_type="odps.created",
            data={"contract_id": contract_id, "status": "ACTIVE", "odps_version": "4.1"},
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )

        # Validate full event structure
        is_valid, error = EventSchema.validate_event(event)
        self.assertTrue(is_valid, f"Full event validation failed: {error}")

        # Validate event data specifically
        is_data_valid, data_error = validate_event_data("odps.created", event["data"])
        self.assertTrue(is_data_valid, f"Event data validation failed: {data_error}")

        # Verify event structure
        self.assertEqual(event["event_type"], "odps.created")
        self.assertEqual(event["event_version"], CURRENT_EVENT_VERSION)
        self.assertEqual(event["data"]["contract_id"], contract_id)
        self.assertIn("event_id", event)
        self.assertIn("timestamp", event)
        self.assertIn("source", event)

    def test_odps_ref_resolved_event_build_and_validate(self):
        """Test building and validating odps.ref.resolved event."""
        contract_id = str(uuid.uuid4())
        event = EventSchema.build_event(
            event_type="odps.ref.resolved",
            data={
                "contract_id": contract_id,
                "ref_path": "#/definitions/quality",
                "ref_type": "internal",
                "resolution_status": "success",
                "ref_count": 3,
                "duration_ms": 50,
            },
            tenant_id=str(uuid.uuid4()),
        )

        is_valid, error = EventSchema.validate_event(event)
        self.assertTrue(is_valid, f"Full event validation failed: {error}")

        is_data_valid, data_error = validate_event_data("odps.ref.resolved", event["data"])
        self.assertTrue(is_data_valid, f"Event data validation failed: {data_error}")

    def test_odps_export_completed_event_build_and_validate(self):
        """Test building and validating odps.export.completed event."""
        contract_id = str(uuid.uuid4())
        event = EventSchema.build_event(
            event_type="odps.export.completed",
            data={
                "contract_id": contract_id,
                "export_format": "odps",
                "output_format": "json",
                "file_size": 1024,
                "duration_ms": 100,
            },
            tenant_id=str(uuid.uuid4()),
        )

        is_valid, error = EventSchema.validate_event(event)
        self.assertTrue(is_valid, f"Full event validation failed: {error}")

        is_data_valid, data_error = validate_event_data("odps.export.completed", event["data"])
        self.assertTrue(is_data_valid, f"Event data validation failed: {data_error}")

    def test_odps_event_type_schema_retrieval(self):
        """Test retrieving ODPS event type schemas directly."""
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
            schema = get_event_type_schema(event_type)
            self.assertIsNotNone(schema, f"Schema not found for {event_type}")
            self.assertIn("data", schema)
            self.assertIn("type", schema["data"])
            self.assertIn("required", schema["data"])
            self.assertIn("properties", schema["data"])

    def test_odps_schema_required_fields(self):
        """Test that all ODPS schemas have correct required fields."""
        required_fields_map = {
            "odps.created": ["contract_id"],
            "odps.updated": ["contract_id"],
            "odps.deleted": ["contract_id"],
            "odps.normalized": ["contract_id", "normalization_status"],
            "odps.linked": ["odps_contract_id", "odcs_contract_id"],
            "odps.unlinked": ["odps_contract_id", "odcs_contract_id"],
            "odps.ref.resolved": ["contract_id", "ref_path", "ref_type", "resolution_status"],
            "odps.ref.failed": ["contract_id", "ref_path", "ref_type", "error_message"],
            "odps.export.started": ["contract_id", "export_format"],
            "odps.export.completed": ["contract_id", "export_format"],
            "odps.export.failed": ["contract_id", "export_format", "error_message"],
        }

        for event_type, expected_required in required_fields_map.items():
            schema = get_event_type_schema(event_type)
            actual_required = schema["data"].get("required", [])
            for field in expected_required:
                self.assertIn(
                    field, actual_required, f"{event_type} missing required field: {field}"
                )

    def test_odps_schema_optional_fields(self):
        """Test that optional fields are properly defined in ODPS schemas."""
        # Test that optional fields can be omitted
        data = {"contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Should allow optional fields to be omitted: {error}")

        # Test that optional fields can be None
        data_with_nulls = {"contract_id": str(uuid.uuid4()), "status": None, "odps_version": None}
        is_valid, error = validate_event_data("odps.created", data_with_nulls)
        self.assertTrue(is_valid, f"Should allow None for optional fields: {error}")

    def test_odps_schema_type_validation(self):
        """Test that ODPS schemas validate field types correctly."""
        # Valid UUID string
        data = {"contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Valid UUID string should pass: {error}")

        # Invalid type (integer instead of string UUID)
        data_invalid = {"contract_id": 12345}
        is_valid, error = validate_event_data("odps.created", data_invalid)
        self.assertFalse(is_valid, "Invalid type should fail validation")
        self.assertIsNotNone(error, "Error message should be provided")
        self.assertIn("invalid type", error.lower() if error else "")

    def test_odps_linked_schema_both_contract_ids_required(self):
        """Test that odps.linked requires both contract IDs."""
        # Missing odcs_contract_id
        data = {"odps_contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("odps.linked", data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

        # Missing odps_contract_id
        data = {"odcs_contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("odps.linked", data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

        # Both present
        data = {"odps_contract_id": str(uuid.uuid4()), "odcs_contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("odps.linked", data)
        self.assertTrue(is_valid, f"Both contract IDs should be valid: {error}")
