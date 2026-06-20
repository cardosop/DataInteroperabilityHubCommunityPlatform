"""
Unit tests for ODPS event types in webhook service.

Tests that ODPS event types are properly defined and can be used in webhook subscriptions.
"""

import pytest
from django.test import TestCase

from hub.apps.core.events.event_types import (
    get_all_event_types,
    get_event_schema,
    validate_event_data,
)
from hub.apps.webhooks.models import WebhookEventType

pytestmark = pytest.mark.django_db(transaction=True)


class ODPSEventTypesUnitTest(TestCase):
    """Unit tests for ODPS event types"""

    def test_odps_event_types_exist_in_enum(self):
        """Test that all ODPS event types exist in WebhookEventType enum"""
        odps_event_types = [
            WebhookEventType.ODPS_CREATED,
            WebhookEventType.ODPS_UPDATED,
            WebhookEventType.ODPS_DELETED,
            WebhookEventType.ODPS_NORMALIZED,
            WebhookEventType.ODPS_LINKED,
            WebhookEventType.ODPS_UNLINKED,
            WebhookEventType.ODPS_EXPORT_STARTED,
            WebhookEventType.ODPS_EXPORT_COMPLETED,
            WebhookEventType.ODPS_EXPORT_FAILED,
        ]

        # Verify all event types are non-None and have the ODPS_ prefix
        for event_type in odps_event_types:
            self.assertIsNotNone(event_type)
            self.assertTrue(
                event_type.startswith("odps."),
                f"ODPS event type '{event_type}' should have 'odps.' prefix",
            )

    def test_odps_event_schemas_exist(self):
        """Test that all ODPS event schemas are defined"""
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
            if schema is not None:
                self.assertIn("data", schema)
                self.assertIn("type", schema["data"])
                self.assertEqual(schema["data"]["type"], "object")

    def test_odps_created_schema_validation(self):
        """Test odps.created event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "asset_id": "550e8400-e29b-41d4-a716-446655440001",
            "status": "ACTIVE",
            "odps_version": "4.1",
            "original_format": "JSON",
        }
        is_valid, error = validate_event_data("odps.created", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Missing required field
        invalid_data = {
            "asset_id": "550e8400-e29b-41d4-a716-446655440001",
        }
        is_valid, error = validate_event_data("odps.created", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("contract_id", error)

    def test_odps_updated_schema_validation(self):
        """Test odps.updated event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "changes": {"status": "ACTIVE"},
            "previous_status": "DRAFT",
            "new_status": "ACTIVE",
        }
        is_valid, error = validate_event_data("odps.updated", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Missing required field
        invalid_data = {
            "changes": {"status": "ACTIVE"},
        }
        is_valid, error = validate_event_data("odps.updated", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("contract_id", error)

    def test_odps_deleted_schema_validation(self):
        """Test odps.deleted event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "deleted_at": "2025-01-15T10:00:00Z",
            "reason": "User request",
        }
        is_valid, error = validate_event_data("odps.deleted", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_normalized_schema_validation(self):
        """Test odps.normalized event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "normalization_status": "NORMALIZED_OK",
            "normalization_errors": None,
            "odps_version": "4.1",
        }
        is_valid, error = validate_event_data("odps.normalized", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # With errors
        valid_data_with_errors = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "normalization_status": "NORMALIZATION_FAILED",
            "normalization_errors": ["Error 1", "Error 2"],
        }
        is_valid, error = validate_event_data("odps.normalized", valid_data_with_errors)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_linked_schema_validation(self):
        """Test odps.linked event schema validation"""
        # Valid data
        valid_data = {
            "odps_contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "odcs_contract_id": "550e8400-e29b-41d4-a716-446655440001",
            "link_type": "bidirectional",
        }
        is_valid, error = validate_event_data("odps.linked", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Missing required field
        invalid_data = {
            "odps_contract_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        is_valid, error = validate_event_data("odps.linked", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("odcs_contract_id", error)

    def test_odps_unlinked_schema_validation(self):
        """Test odps.unlinked event schema validation"""
        # Valid data
        valid_data = {
            "odps_contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "odcs_contract_id": "550e8400-e29b-41d4-a716-446655440001",
            "reason": "User request",
        }
        is_valid, error = validate_event_data("odps.unlinked", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_started_schema_validation(self):
        """Test odps.export.started event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "export_format": "JSON",
            "output_format": "JSON",
            "odps_version": "4.1",
        }
        is_valid, error = validate_event_data("odps.export.started", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_completed_schema_validation(self):
        """Test odps.export.completed event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "export_format": "JSON",
            "output_format": "JSON",
            "file_size": 1024,
            "duration_ms": 500,
        }
        is_valid, error = validate_event_data("odps.export.completed", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_failed_schema_validation(self):
        """Test odps.export.failed event schema validation"""
        # Valid data
        valid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
            "export_format": "JSON",
            "error_message": "Export failed",
            "error_details": {"code": "EXPORT_ERROR"},
        }
        is_valid, error = validate_event_data("odps.export.failed", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Missing required field
        invalid_data = {
            "contract_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        is_valid, error = validate_event_data("odps.export.failed", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("export_format", error)

    def test_odps_event_types_in_all_event_types(self):
        """Test that all ODPS event types are in get_all_event_types()"""
        all_event_types = get_all_event_types()
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
            self.assertIn(event_type, all_event_types, f"{event_type} not in all event types")

    def test_get_odps_event_types(self):
        """Test get_odps_event_types() returns at least 9 ODPS event types."""
        odps_event_types = WebhookEventType.get_odps_event_types()

        self.assertGreaterEqual(len(odps_event_types), 9)
        # All returned types should have the odps. prefix
        for event_type in odps_event_types:
            self.assertTrue(
                event_type.startswith("odps."),
                f"All ODPS event types should start with 'odps.', got '{event_type}'",
            )

    def test_is_odps_event_type(self):
        """Test is_odps_event_type() correctly identifies ODPS events"""
        # ODPS events should return True (using string values or enum members)
        self.assertTrue(WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_CREATED)))
        self.assertTrue(WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_UPDATED)))
        self.assertTrue(WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_DELETED)))
        self.assertTrue(WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_NORMALIZED)))
        self.assertTrue(WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_LINKED)))
        self.assertTrue(WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_UNLINKED)))
        self.assertTrue(
            WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_EXPORT_STARTED))
        )
        self.assertTrue(
            WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_EXPORT_COMPLETED))
        )
        self.assertTrue(
            WebhookEventType.is_odps_event_type(str(WebhookEventType.ODPS_EXPORT_FAILED))
        )

        # Also test with enum members directly
        self.assertTrue(WebhookEventType.is_odps_event_type(WebhookEventType.ODPS_CREATED))

        # Non-ODPS events should return False
        self.assertFalse(
            WebhookEventType.is_odps_event_type(str(WebhookEventType.CONTRACT_CREATED))
        )
        self.assertFalse(WebhookEventType.is_odps_event_type(str(WebhookEventType.ASSET_CREATED)))
        self.assertFalse(
            WebhookEventType.is_odps_event_type(str(WebhookEventType.INGESTION_COMPLETED))
        )

        # Invalid event types should return False
        self.assertFalse(WebhookEventType.is_odps_event_type("invalid.event.type"))
