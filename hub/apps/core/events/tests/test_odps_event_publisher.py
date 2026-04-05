"""
Unit tests for ODPSEventPublisher.

Tests all ODPS event publishing methods with comprehensive coverage.
Follows the same pattern as other service publisher tests.
"""
import uuid
from unittest.mock import Mock, patch
from django.test import TestCase

from hub.apps.core.events.service_publishers import ODPSEventPublisher
from hub.apps.core.events.event_types import validate_event_data


class ODPSEventPublisherTest(TestCase):
    """Test ODPSEventPublisher class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())

    def create_service(self):
        """Create TestService with ODPSEventPublisher - helper method."""
        tenant_id = self.tenant_id
        user_id = self.user_id

        class TestService(ODPSEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService()

    def test_initialization(self):
        """Test ODPSEventPublisher initialization."""
        service = self.create_service()
        self.assertIsNotNone(service._event_publisher)
        self.assertEqual(service._event_publisher.service_name, "contract_service")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_created(self, mock_publisher_class):
        """Test publish_odps_created method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        status = "ACTIVE"
        odps_version = "4.1"
        original_format = "JSON"

        event_id = service.publish_odps_created(
            contract_id=contract_id,
            asset_id=asset_id,
            status=status,
            odps_version=odps_version,
            original_format=original_format,
        )

        self.assertIsNotNone(event_id)
        self.assertEqual(event_id, "event-id-123")
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.created")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["asset_id"], asset_id)
        self.assertEqual(data["status"], status)
        self.assertEqual(data["odps_version"], odps_version)
        self.assertEqual(data["original_format"], original_format)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_created_minimal(self, mock_publisher_class):
        """Test publish_odps_created with minimal required fields."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())

        event_id = service.publish_odps_created(contract_id=contract_id)

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.created", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_updated(self, mock_publisher_class):
        """Test publish_odps_updated method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        changes = {"status": "ACTIVE", "version": "4.2"}
        previous_status = "DRAFT"
        new_status = "ACTIVE"

        event_id = service.publish_odps_updated(
            contract_id=contract_id,
            changes=changes,
            previous_status=previous_status,
            new_status=new_status,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.updated")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["changes"], changes)
        self.assertEqual(data["previous_status"], previous_status)
        self.assertEqual(data["new_status"], new_status)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.updated", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_deleted(self, mock_publisher_class):
        """Test publish_odps_deleted method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        reason = "User requested deletion"

        event_id = service.publish_odps_deleted(
            contract_id=contract_id, reason=reason
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.deleted")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["reason"], reason)
        self.assertIn("deleted_at", data)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.deleted", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_normalized(self, mock_publisher_class):
        """Test publish_odps_normalized method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        normalization_status = "NORMALIZED_OK"
        normalization_errors = []
        odps_version = "4.1"

        event_id = service.publish_odps_normalized(
            contract_id=contract_id,
            normalization_status=normalization_status,
            normalization_errors=normalization_errors,
            odps_version=odps_version,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.normalized")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["normalization_status"], normalization_status)
        self.assertEqual(data["normalization_errors"], normalization_errors)
        self.assertEqual(data["odps_version"], odps_version)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.normalized", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_normalized_with_errors(self, mock_publisher_class):
        """Test publish_odps_normalized with normalization errors."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        normalization_status = "NORMALIZED_WITH_ERRORS"
        normalization_errors = ["Error 1", "Error 2"]

        event_id = service.publish_odps_normalized(
            contract_id=contract_id,
            normalization_status=normalization_status,
            normalization_errors=normalization_errors,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        data = call_args[1]["data"]
        self.assertEqual(data["normalization_errors"], normalization_errors)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.normalized", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_linked(self, mock_publisher_class):
        """Test publish_odps_linked method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())
        link_type = "bidirectional"

        event_id = service.publish_odps_linked(
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            link_type=link_type,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.linked")
        data = call_args[1]["data"]
        self.assertEqual(data["odps_contract_id"], odps_contract_id)
        self.assertEqual(data["odcs_contract_id"], odcs_contract_id)
        self.assertEqual(data["link_type"], link_type)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.linked", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_unlinked(self, mock_publisher_class):
        """Test publish_odps_unlinked method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())
        reason = "User requested unlink"

        event_id = service.publish_odps_unlinked(
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            reason=reason,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.unlinked")
        data = call_args[1]["data"]
        self.assertEqual(data["odps_contract_id"], odps_contract_id)
        self.assertEqual(data["odcs_contract_id"], odcs_contract_id)
        self.assertEqual(data["reason"], reason)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.unlinked", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_ref_resolved(self, mock_publisher_class):
        """Test publish_odps_ref_resolved method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        ref_path = "#/definitions/quality"
        ref_type = "internal"
        resolution_status = "success"
        ref_count = 5
        duration_ms = 100

        event_id = service.publish_odps_ref_resolved(
            contract_id=contract_id,
            ref_path=ref_path,
            ref_type=ref_type,
            resolution_status=resolution_status,
            ref_count=ref_count,
            duration_ms=duration_ms,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.ref.resolved")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["ref_path"], ref_path)
        self.assertEqual(data["ref_type"], ref_type)
        self.assertEqual(data["resolution_status"], resolution_status)
        self.assertEqual(data["ref_count"], ref_count)
        self.assertEqual(data["duration_ms"], duration_ms)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.ref.resolved", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_ref_failed(self, mock_publisher_class):
        """Test publish_odps_ref_failed method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        ref_path = "https://example.com/schema.json"
        ref_type = "external"
        error_message = "Failed to resolve external reference"
        error_code = "RESOLUTION_FAILED"
        error_details = {"timeout": True, "retry_count": 3}

        event_id = service.publish_odps_ref_failed(
            contract_id=contract_id,
            ref_path=ref_path,
            ref_type=ref_type,
            error_message=error_message,
            error_code=error_code,
            error_details=error_details,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.ref.failed")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["ref_path"], ref_path)
        self.assertEqual(data["ref_type"], ref_type)
        self.assertEqual(data["error_message"], error_message)
        self.assertEqual(data["error_code"], error_code)
        self.assertEqual(data["error_details"], error_details)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.ref.failed", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_export_started(self, mock_publisher_class):
        """Test publish_odps_export_started method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        export_format = "odps"
        output_format = "json"
        odps_version = "4.1"

        event_id = service.publish_odps_export_started(
            contract_id=contract_id,
            export_format=export_format,
            output_format=output_format,
            odps_version=odps_version,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.export.started")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["export_format"], export_format)
        self.assertEqual(data["output_format"], output_format)
        self.assertEqual(data["odps_version"], odps_version)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.export.started", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_export_completed(self, mock_publisher_class):
        """Test publish_odps_export_completed method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        export_format = "odps"
        output_format = "json"
        file_size = 1024
        duration_ms = 50

        event_id = service.publish_odps_export_completed(
            contract_id=contract_id,
            export_format=export_format,
            output_format=output_format,
            file_size=file_size,
            duration_ms=duration_ms,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.export.completed")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["export_format"], export_format)
        self.assertEqual(data["output_format"], output_format)
        self.assertEqual(data["file_size"], file_size)
        self.assertEqual(data["duration_ms"], duration_ms)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.export.completed", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    @patch('hub.apps.core.events.service_publishers.EventPublisher')
    def test_publish_odps_export_failed(self, mock_publisher_class):
        """Test publish_odps_export_failed method."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = "event-id-123"

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        export_format = "odps"
        error_message = "Export failed: Invalid format"
        error_details = {"error_code": "INVALID_FORMAT", "line": 42}

        event_id = service.publish_odps_export_failed(
            contract_id=contract_id,
            export_format=export_format,
            error_message=error_message,
            error_details=error_details,
        )

        self.assertEqual(event_id, "event-id-123")
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "odps.export.failed")
        data = call_args[1]["data"]
        self.assertEqual(data["contract_id"], contract_id)
        self.assertEqual(data["export_format"], export_format)
        self.assertEqual(data["error_message"], error_message)
        self.assertEqual(data["error_details"], error_details)

        # Validate event data against schema
        is_valid, error = validate_event_data("odps.export.failed", data)
        self.assertTrue(is_valid, f"Event data validation failed: {error}")

    def create_service(self):
        """Create TestService with ODPSEventPublisher - helper method."""
        tenant_id = self.tenant_id
        user_id = self.user_id

        class TestService(ODPSEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService()
