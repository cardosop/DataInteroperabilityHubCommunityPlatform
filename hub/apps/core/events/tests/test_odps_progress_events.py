"""
Tests for ODPS Progress Events (Task 7.3.2)

Comprehensive tests for:
- ODPS creation progress events
- ODPS normalization progress events
- ODPS ref progress events
- ODPS linking status events
- ODPS export progress events
- Event schema validation
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    pytest = None
    pytestmark = None

import uuid
from unittest.mock import patch

from django.test import TestCase

from hub.apps.core.events.event_types import validate_event_data
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.schema import get_event_schema
from hub.apps.core.events.service_publishers import ODPSEventPublisher


class ODPSEventPublisherProgressEventsTest(TestCase):
    """Test ODPS progress event publishing methods (Task 7.3.2)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        self.contract_id = str(uuid.uuid4())
        self.workflow_instance_id = str(uuid.uuid4())

        # Create event publisher with mocked event bus
        self.publisher = ODPSEventPublisher()
        self.publisher._event_publisher = EventPublisher(
            service_name="test_service",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    @patch("hub.apps.core.events.publisher.EventPublisher.publish")
    def test_publish_odps_creation_progress(self, mock_publish):
        """Test publishing odps.creation.progress event"""
        mock_publish.return_value = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_creation_progress(
            contract_id=self.contract_id,
            workflow_instance_id=self.workflow_instance_id,
            progress_percentage=50.0,
            current_step="normalize_odps",
            total_steps=10,
            step_index=5,
            status_message="Normalizing ODPS document",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        self.assertIsNotNone(event_id)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.creation.progress")
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 50.0)
        self.assertEqual(call_args[1]["data"]["contract_id"], self.contract_id)
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], self.workflow_instance_id)
        self.assertEqual(call_args[1]["data"]["current_step"], "normalize_odps")
        self.assertEqual(call_args[1]["data"]["total_steps"], 10)
        self.assertEqual(call_args[1]["data"]["step_index"], 5)

    @patch("hub.apps.core.events.publisher.EventPublisher.publish")
    def test_publish_odps_normalization_progress(self, mock_publish):
        """Test publishing odps.normalization.progress event"""
        mock_publish.return_value = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_normalization_progress(
            contract_id=self.contract_id,
            progress_percentage=75.0,
            current_phase="marketplace_mapping",
            total_phases=6,
            phase_index=4,
            items_processed=15,
            items_total=20,
            status_message="Mapping marketplace fields",
            odps_version="4.1",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        self.assertIsNotNone(event_id)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.normalization.progress")
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 75.0)
        self.assertEqual(call_args[1]["data"]["contract_id"], self.contract_id)
        self.assertEqual(call_args[1]["data"]["current_phase"], "marketplace_mapping")
        self.assertEqual(call_args[1]["data"]["total_phases"], 6)
        self.assertEqual(call_args[1]["data"]["phase_index"], 4)
        self.assertEqual(call_args[1]["data"]["items_processed"], 15)
        self.assertEqual(call_args[1]["data"]["items_total"], 20)
        self.assertEqual(call_args[1]["data"]["odps_version"], "4.1")

    @patch("hub.apps.core.events.publisher.EventPublisher.publish")
    def test_publish_odps_ref_progress(self, mock_publish):
        """Test publishing odps.ref.progress event"""
        mock_publish.return_value = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_ref_progress(
            contract_id=self.contract_id,
            progress_percentage=60.0,
            refs_processed=6,
            refs_total=10,
            current_ref_path="#/definitions/quality",
            ref_type="internal",
            status_message="Resolving internal references",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        self.assertIsNotNone(event_id)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.ref.progress")
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 60.0)
        self.assertEqual(call_args[1]["data"]["contract_id"], self.contract_id)
        self.assertEqual(call_args[1]["data"]["refs_processed"], 6)
        self.assertEqual(call_args[1]["data"]["refs_total"], 10)
        self.assertEqual(call_args[1]["data"]["current_ref_path"], "#/definitions/quality")
        self.assertEqual(call_args[1]["data"]["ref_type"], "internal")

    @patch("hub.apps.core.events.publisher.EventPublisher.publish")
    def test_publish_odps_linking_status(self, mock_publish):
        """Test publishing odps.linking.status event"""
        mock_publish.return_value = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_linking_status(
            odps_contract_id=self.contract_id,
            odcs_contract_id=odcs_contract_id,
            status="completed",
            progress_percentage=100.0,
            current_phase="completed",
            validation_passed=True,
            validation_errors=[],
            link_type="bidirectional",
            status_message="Contracts linked successfully",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        self.assertIsNotNone(event_id)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.linking.status")
        self.assertEqual(call_args[1]["data"]["odps_contract_id"], self.contract_id)
        self.assertEqual(call_args[1]["data"]["odcs_contract_id"], odcs_contract_id)
        self.assertEqual(call_args[1]["data"]["status"], "completed")
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 100.0)
        self.assertEqual(call_args[1]["data"]["validation_passed"], True)
        self.assertEqual(call_args[1]["data"]["link_type"], "bidirectional")

    @patch("hub.apps.core.events.publisher.EventPublisher.publish")
    def test_publish_odps_export_progress(self, mock_publish):
        """Test publishing odps.export.progress event"""
        mock_publish.return_value = str(uuid.uuid4())

        event_id = self.publisher.publish_odps_export_progress(
            contract_id=self.contract_id,
            export_format="json",
            progress_percentage=80.0,
            current_phase="formatting",
            bytes_processed=8000,
            bytes_total=10000,
            status_message="Formatting ODPS as JSON",
            odps_version="4.1",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        self.assertIsNotNone(event_id)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.export.progress")
        self.assertEqual(call_args[1]["data"]["contract_id"], self.contract_id)
        self.assertEqual(call_args[1]["data"]["export_format"], "json")
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 80.0)
        self.assertEqual(call_args[1]["data"]["current_phase"], "formatting")
        self.assertEqual(call_args[1]["data"]["bytes_processed"], 8000)
        self.assertEqual(call_args[1]["data"]["bytes_total"], 10000)
        self.assertEqual(call_args[1]["data"]["odps_version"], "4.1")


class ODPSProgressEventSchemaTest(TestCase):
    """Test ODPS progress event schemas (Task 7.3.2)"""

    def test_odps_creation_progress_schema(self):
        """Test odps.creation.progress event schema"""
        schema = get_event_schema("odps.creation.progress")
        self.assertIsNotNone(schema)
        # get_event_schema returns merged schema with properties wrapper
        self.assertIn("properties", schema)
        self.assertIn("data", schema["properties"])

        # Test valid data
        valid_data = {
            "contract_id": str(uuid.uuid4()),
            "workflow_instance_id": str(uuid.uuid4()),
            "progress_percentage": 50.0,
            "current_step": "normalize_odps",
            "total_steps": 10,
            "step_index": 5,
            "status_message": "Processing step",
        }
        is_valid, error = validate_event_data("odps.creation.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_normalization_progress_schema(self):
        """Test odps.normalization.progress event schema"""
        schema = get_event_schema("odps.normalization.progress")
        self.assertIsNotNone(schema)

        # Test valid data
        valid_data = {
            "contract_id": str(uuid.uuid4()),
            "progress_percentage": 75.0,
            "current_phase": "marketplace_mapping",
            "total_phases": 6,
            "phase_index": 4,
            "items_processed": 15,
            "items_total": 20,
            "status_message": "Mapping fields",
            "odps_version": "4.1",
        }
        is_valid, error = validate_event_data("odps.normalization.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_ref_progress_schema(self):
        """Test odps.ref.progress event schema"""
        schema = get_event_schema("odps.ref.progress")
        self.assertIsNotNone(schema)

        # Test valid data
        valid_data = {
            "contract_id": str(uuid.uuid4()),
            "progress_percentage": 60.0,
            "refs_processed": 6,
            "refs_total": 10,
            "current_ref_path": "#/definitions/quality",
            "ref_type": "internal",
            "status_message": "Resolving references",
        }
        is_valid, error = validate_event_data("odps.ref.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_linking_status_schema(self):
        """Test odps.linking.status event schema"""
        schema = get_event_schema("odps.linking.status")
        self.assertIsNotNone(schema)

        # Test valid data
        valid_data = {
            "odps_contract_id": str(uuid.uuid4()),
            "odcs_contract_id": str(uuid.uuid4()),
            "status": "completed",
            "progress_percentage": 100.0,
            "current_phase": "completed",
            "validation_passed": True,
            "validation_errors": [],
            "link_type": "bidirectional",
            "status_message": "Linking completed",
        }
        is_valid, error = validate_event_data("odps.linking.status", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_export_progress_schema(self):
        """Test odps.export.progress event schema"""
        schema = get_event_schema("odps.export.progress")
        self.assertIsNotNone(schema)

        # Test valid data
        valid_data = {
            "contract_id": str(uuid.uuid4()),
            "export_format": "json",
            "progress_percentage": 80.0,
            "current_phase": "formatting",
            "bytes_processed": 8000,
            "bytes_total": 10000,
            "status_message": "Formatting output",
            "odps_version": "4.1",
        }
        is_valid, error = validate_event_data("odps.export.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

    def test_odps_progress_events_allow_null_contract_id(self):
        """Test that progress events allow null contract_id (for early stages)"""
        # Creation progress
        valid_data = {
            "progress_percentage": 10.0,
            "workflow_instance_id": str(uuid.uuid4()),
        }
        is_valid, error = validate_event_data("odps.creation.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Normalization progress
        valid_data = {
            "progress_percentage": 20.0,
        }
        is_valid, error = validate_event_data("odps.normalization.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")

        # Ref progress
        valid_data = {
            "progress_percentage": 30.0,
        }
        is_valid, error = validate_event_data("odps.ref.progress", valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
