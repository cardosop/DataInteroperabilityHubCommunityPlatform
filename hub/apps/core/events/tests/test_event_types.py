"""
Tests for event type definitions and validation.
"""

import uuid

from django.test import TestCase

from hub.apps.core.events.event_types import (
    CURRENT_EVENT_VERSION,
    get_all_event_types,
    get_event_schema,
    validate_event_data,
)


class EventTypesTest(TestCase):
    """Test event type definitions."""

    def test_all_event_types_defined(self):
        """Test that all required event types are defined."""
        required_event_types = [
            # Contract events
            "contract.created",
            "contract.updated",
            "contract.deleted",
            "contract.validated",
            "contract.normalized",
            # Asset events
            "asset.created",
            "asset.updated",
            "asset.activated",
            "asset.published",
            "asset.retired",
            # Dataset events
            "dataset.created",
            "dataset.updated",
            "dataset.deleted",
            "dataset.uploaded",
            # Ingestion events
            "ingestion.started",
            "ingestion.completed",
            "ingestion.failed",
            "ingestion.file_processed",
            # Quality events
            "quality.check.started",
            "quality.check.completed",
            "quality.check.failed",
            "quality.anomaly.detected",
            # Compliance events
            "compliance.check.started",
            "compliance.check.completed",
            "compliance.check.failed",
            "compliance.report.generated",
            # Version events
            "version.created",
            "version.updated",
            "version.rolled_back",
            # Access events
            "access.requested",
            "access.granted",
            "access.revoked",
            "access.certified",
            # Marketplace events
            "marketplace.listing.published",
            "marketplace.listing.unpublished",
            "marketplace.order.created",
            "marketplace.order.approved",
            "marketplace.order.rejected",
            "marketplace.order.fulfilled",
            "marketplace.entitlement.granted",
            "marketplace.entitlement.revoked",
            # Workflow events
            "workflow.started",
            "workflow.completed",
            "workflow.failed",
            "workflow.cancelled",
            "workflow.step.started",
            "workflow.step.completed",
            "workflow.step.failed",
        ]

        all_types = get_all_event_types()
        for event_type in required_event_types:
            self.assertIn(event_type, all_types, f"Missing event type: {event_type}")

    def test_get_event_schema(self):
        """Test getting event schema."""
        schema = get_event_schema("contract.created")
        self.assertIsNotNone(schema)
        self.assertIn("data", schema)
        self.assertIn("properties", schema["data"])

    def test_get_event_schema_unknown(self):
        """Test getting schema for unknown event type."""
        schema = get_event_schema("unknown.event")
        self.assertIsNone(schema)

    def test_validate_event_data_valid(self):
        """Test validating valid event data."""
        data = {"contract_id": str(uuid.uuid4())}
        is_valid, error = validate_event_data("contract.created", data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
        self.assertIsNone(error)

    def test_validate_event_data_missing_required(self):
        """Test validating event data with missing required field."""
        data = {}
        is_valid, error = validate_event_data("contract.created", data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

    def test_validate_event_data_invalid_type(self):
        """Test validating event data with invalid type."""
        data = {
            "contract_id": 123  # Should be string UUID
        }
        is_valid, error = validate_event_data("contract.created", data)
        self.assertFalse(is_valid)
        self.assertIn("invalid type", error.lower())

    def test_validate_event_data_unknown_event_type(self):
        """Test validating data for unknown event type."""
        data = {"test": "value"}
        is_valid, error = validate_event_data("unknown.event", data)
        self.assertFalse(is_valid)
        self.assertIn("Unknown event type", error)

    def test_contract_created_schema(self):
        """Test contract.created event schema."""
        schema = get_event_schema("contract.created")
        required_fields = schema["data"].get("required", [])
        self.assertIn("contract_id", required_fields)

    def test_asset_created_schema(self):
        """Test asset.created event schema."""
        schema = get_event_schema("asset.created")
        required_fields = schema["data"].get("required", [])
        self.assertIn("asset_id", required_fields)

    def test_workflow_started_schema(self):
        """Test workflow.started event schema."""
        schema = get_event_schema("workflow.started")
        required_fields = schema["data"].get("required", [])
        self.assertIn("workflow_instance_id", required_fields)
        self.assertIn("workflow_name", required_fields)

    def test_marketplace_order_created_schema(self):
        """Test marketplace.order.created event schema."""
        schema = get_event_schema("marketplace.order.created")
        required_fields = schema["data"].get("required", [])
        self.assertIn("order_id", required_fields)
        self.assertIn("listing_id", required_fields)
        self.assertIn("buyer_id", required_fields)

    def test_event_schema_version(self):
        """Test that event schema version is set."""
        self.assertEqual(CURRENT_EVENT_VERSION, "1.0.0")

    def test_all_event_types_have_schemas(self):
        """Test that all event types have schemas defined."""
        all_types = get_all_event_types()
        for event_type in all_types:
            schema = get_event_schema(event_type)
            self.assertIsNotNone(schema, f"No schema for {event_type}")
            self.assertIn("data", schema)
            self.assertIn("properties", schema["data"])
