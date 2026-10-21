"""
Tests for service event publishers.
"""

import uuid
from unittest.mock import Mock, patch

from django.test import TestCase

from hub.apps.core.events.service_publishers import (
    AssetEventPublisher,
    ContractEventPublisher,
    DatasetEventPublisher,
    FileEventPublisher,
    LineageEventPublisher,
    MarketplaceEventPublisher,
    SearchEventPublisher,
    WorkflowEventPublisher,
)


class ServicePublisherMixin:
    """Base mixin for testing service publishers."""

    def setUp(self):
        """Set up test data."""
        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        self.service = self.create_service()

    def create_service(self):
        """Create service instance - override in subclasses."""
        raise NotImplementedError


class ContractEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test ContractEventPublisher."""

    def create_service(self):
        """Create ContractService with event publisher."""

        class TestService(ContractEventPublisher):
            def __init__(self, tenant_id, user_id):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService(self.tenant_id, self.user_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_contract_created(self, mock_publisher_class):
        """Test publishing contract.created event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        event_id = service.publish_contract_created(
            contract_id=contract_id, asset_id=str(uuid.uuid4()), status="ACTIVE"
        )

        self.assertIsNotNone(event_id)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "contract.created")
        self.assertEqual(call_args[1]["data"]["contract_id"], contract_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_contract_validated(self, mock_publisher_class):
        """Test publishing contract.validated event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        event_id = service.publish_contract_validated(
            contract_id=contract_id, validation_result=True, validation_errors=[]
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "contract.validated")
        self.assertEqual(call_args[1]["data"]["validation_result"], True)


class AssetEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test AssetEventPublisher."""

    def create_service(self):
        """Create AssetService with event publisher."""

        class TestService(AssetEventPublisher):
            def __init__(self, tenant_id, user_id):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService(self.tenant_id, self.user_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_asset_created(self, mock_publisher_class):
        """Test publishing asset.created event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        asset_id = str(uuid.uuid4())
        event_id = service.publish_asset_created(asset_id=asset_id, name="Test Asset")

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "asset.created")
        self.assertEqual(call_args[1]["data"]["asset_id"], asset_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_asset_activated(self, mock_publisher_class):
        """Test publishing asset.activated event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        asset_id = str(uuid.uuid4())
        event_id = service.publish_asset_activated(
            asset_id=asset_id, dq_status="PASSED", compliance_status="COMPLIANT"
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "asset.activated")


class DatasetEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test DatasetEventPublisher."""

    def create_service(self):
        """Create DatasetService with event publisher."""

        class TestService(DatasetEventPublisher):
            def __init__(self, tenant_id, user_id):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService(self.tenant_id, self.user_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_dataset_created(self, mock_publisher_class):
        """Test publishing dataset.created event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        dataset_id = str(uuid.uuid4())
        event_id = service.publish_dataset_created(
            dataset_id=dataset_id, file_id=str(uuid.uuid4()), format="CSV"
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "dataset.created")
        self.assertEqual(call_args[1]["data"]["dataset_id"], dataset_id)


class MarketplaceEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test MarketplaceEventPublisher."""

    def create_service(self):
        """Create MarketplaceService with event publisher."""

        class TestService(MarketplaceEventPublisher):
            def __init__(self, tenant_id, user_id):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService(self.tenant_id, self.user_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_listing_published(self, mock_publisher_class):
        """Test publishing marketplace.listing.published event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        listing_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        event_id = service.publish_listing_published(listing_id=listing_id, asset_id=asset_id)

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "marketplace.listing.published")
        self.assertEqual(call_args[1]["data"]["listing_id"], listing_id)
        self.assertEqual(call_args[1]["data"]["asset_id"], asset_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_order_created(self, mock_publisher_class):
        """Test publishing marketplace.order.created event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        order_id = str(uuid.uuid4())
        listing_id = str(uuid.uuid4())
        buyer_id = str(uuid.uuid4())
        event_id = service.publish_order_created(
            order_id=order_id, listing_id=listing_id, buyer_id=buyer_id, order_amount=100.0
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "marketplace.order.created")
        self.assertEqual(call_args[1]["data"]["order_id"], order_id)


class WorkflowEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test WorkflowEventPublisher."""

    def create_service(self):
        """Create WorkflowEngine with event publisher."""
        tenant_id = self.tenant_id
        user_id = self.user_id

        class TestService(WorkflowEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService()

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_started(self, mock_publisher_class):
        """Test publishing workflow.started event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())
        event_id = service.publish_workflow_started(
            workflow_instance_id=workflow_instance_id, workflow_name="test_workflow"
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.started")
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], workflow_instance_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_completed(self, mock_publisher_class):
        """Test publishing workflow.completed event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())
        event_id = service.publish_workflow_completed(
            workflow_instance_id=workflow_instance_id,
            workflow_name="test_workflow",
            duration_ms=1000,
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.completed")
        self.assertEqual(call_args[1]["data"]["duration_ms"], 1000)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_step_started(self, mock_publisher_class):
        """Test publishing workflow.step.started event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())
        step_index = 0
        step_name = "test_step"
        step_type = "task"

        event_id = service.publish_workflow_step_started(
            workflow_instance_id=workflow_instance_id,
            step_index=step_index,
            step_name=step_name,
            step_type=step_type,
        )

        self.assertIsNotNone(event_id)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.step.started")
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(call_args[1]["data"]["step_index"], step_index)
        self.assertEqual(call_args[1]["data"]["step_name"], step_name)
        self.assertEqual(call_args[1]["data"]["step_type"], step_type)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_step_completed(self, mock_publisher_class):
        """Test publishing workflow.step.completed event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())
        step_index = 1
        step_name = "process_data"
        output_data = {"result": "success", "records_processed": 100}
        duration_ms = 500

        event_id = service.publish_workflow_step_completed(
            workflow_instance_id=workflow_instance_id,
            step_index=step_index,
            step_name=step_name,
            output_data=output_data,
            duration_ms=duration_ms,
        )

        self.assertIsNotNone(event_id)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.step.completed")
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(call_args[1]["data"]["step_index"], step_index)
        self.assertEqual(call_args[1]["data"]["step_name"], step_name)
        self.assertEqual(call_args[1]["data"]["output_data"], output_data)
        self.assertEqual(call_args[1]["data"]["duration_ms"], duration_ms)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_step_failed(self, mock_publisher_class):
        """Test publishing workflow.step.failed event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())
        step_index = 2
        step_name = "validate_input"
        error_message = "Validation failed: missing required field"
        error_details = {"field": "email", "reason": "invalid format"}
        retry_count = 1

        event_id = service.publish_workflow_step_failed(
            workflow_instance_id=workflow_instance_id,
            step_index=step_index,
            step_name=step_name,
            error_message=error_message,
            error_details=error_details,
            retry_count=retry_count,
        )

        self.assertIsNotNone(event_id)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.step.failed")
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(call_args[1]["data"]["step_index"], step_index)
        self.assertEqual(call_args[1]["data"]["step_name"], step_name)
        self.assertEqual(call_args[1]["data"]["error_message"], error_message)
        self.assertEqual(call_args[1]["data"]["error_details"], error_details)
        self.assertEqual(call_args[1]["data"]["retry_count"], retry_count)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_step_started_with_tenant_user(self, mock_publisher_class):
        """Test publishing workflow.step.started event with tenant and user IDs."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        event_id = service.publish_workflow_step_started(
            workflow_instance_id=workflow_instance_id,
            step_index=0,
            step_name="test_step",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["tenant_id"], tenant_id)
        self.assertEqual(call_args[1]["user_id"], user_id)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_step_completed_with_optional_fields(self, mock_publisher_class):
        """Test publishing workflow.step.completed event with optional fields."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())

        # Test with None output_data and duration_ms
        event_id = service.publish_workflow_step_completed(
            workflow_instance_id=workflow_instance_id,
            step_index=0,
            step_name="test_step",
            output_data=None,
            duration_ms=None,
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["data"]["output_data"], {})
        self.assertIsNone(call_args[1]["data"]["duration_ms"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_workflow_step_failed_with_default_retry_count(self, mock_publisher_class):
        """Test publishing workflow.step.failed event with default retry_count."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        workflow_instance_id = str(uuid.uuid4())

        # Test with None retry_count (should default to 0)
        event_id = service.publish_workflow_step_failed(
            workflow_instance_id=workflow_instance_id,
            step_index=0,
            step_name="test_step",
            error_message="Test error",
            error_details=None,
            retry_count=None,
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["data"]["retry_count"], 0)
        self.assertEqual(call_args[1]["data"]["error_details"], {})


class FileEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test FileEventPublisher."""

    def create_service(self):
        """Create FileService with event publisher."""
        tenant_id = self.tenant_id
        user_id = self.user_id

        class TestService(FileEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService()

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_file_created(self, mock_publisher_class):
        """Test publishing file.created event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        file_id = str(uuid.uuid4())
        event_id = service.publish_file_created(
            file_id=file_id,
            name="test_file.csv",
            content_type="text/csv",
            size=1024,
            status="ACTIVE",
            content_sha256="abc123",
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "file.created")
        self.assertEqual(call_args[1]["data"]["file_id"], file_id)
        self.assertEqual(call_args[1]["data"]["name"], "test_file.csv")
        self.assertEqual(call_args[1]["data"]["content_type"], "text/csv")
        self.assertEqual(call_args[1]["data"]["size"], 1024)
        self.assertEqual(call_args[1]["data"]["status"], "ACTIVE")
        self.assertEqual(call_args[1]["data"]["content_sha256"], "abc123")

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_file_updated(self, mock_publisher_class):
        """Test publishing file.updated event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        file_id = str(uuid.uuid4())
        changes = {"status": {"old": "PENDING", "new": "ACTIVE"}}
        event_id = service.publish_file_updated(
            file_id=file_id, changes=changes, previous_status="PENDING", new_status="ACTIVE"
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "file.updated")
        self.assertEqual(call_args[1]["data"]["file_id"], file_id)
        self.assertEqual(call_args[1]["data"]["changes"], changes)
        self.assertEqual(call_args[1]["data"]["previous_status"], "PENDING")
        self.assertEqual(call_args[1]["data"]["new_status"], "ACTIVE")

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_file_deleted(self, mock_publisher_class):
        """Test publishing file.deleted event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        file_id = str(uuid.uuid4())
        event_id = service.publish_file_deleted(file_id=file_id, reason="User requested deletion")

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "file.deleted")
        self.assertEqual(call_args[1]["data"]["file_id"], file_id)
        self.assertEqual(call_args[1]["data"]["reason"], "User requested deletion")
        self.assertIn("deleted_at", call_args[1]["data"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_file_uploaded(self, mock_publisher_class):
        """Test publishing file.uploaded event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        file_id = str(uuid.uuid4())
        event_id = service.publish_file_uploaded(
            file_id=file_id,
            file_size=2048,
            content_type="application/json",
            upload_duration_ms=500,
            content_sha256="def456",
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "file.uploaded")
        self.assertEqual(call_args[1]["data"]["file_id"], file_id)
        self.assertEqual(call_args[1]["data"]["file_size"], 2048)
        self.assertEqual(call_args[1]["data"]["content_type"], "application/json")
        self.assertEqual(call_args[1]["data"]["upload_duration_ms"], 500)
        self.assertEqual(call_args[1]["data"]["content_sha256"], "def456")

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_file_downloaded(self, mock_publisher_class):
        """Test publishing file.downloaded event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        file_id = str(uuid.uuid4())
        event_id = service.publish_file_downloaded(
            file_id=file_id, download_duration_ms=300, download_size=1024
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "file.downloaded")
        self.assertEqual(call_args[1]["data"]["file_id"], file_id)
        self.assertEqual(call_args[1]["data"]["download_duration_ms"], 300)
        self.assertEqual(call_args[1]["data"]["download_size"], 1024)


class LineageEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test LineageEventPublisher."""

    def create_service(self):
        """Create LineageService with event publisher."""
        tenant_id = self.tenant_id
        user_id = self.user_id

        class TestService(LineageEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService()

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_lineage_updated(self, mock_publisher_class):
        """Test publishing lineage.updated event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        event_id = service.publish_lineage_updated(
            contract_id=contract_id,
            model_name="UserModel",
            field_name="email",
            lineage_type="field",
            changes={"relationships_added": 2},
            relationship_count=5,
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "lineage.updated")
        self.assertEqual(call_args[1]["data"]["contract_id"], contract_id)
        self.assertEqual(call_args[1]["data"]["model_name"], "UserModel")
        self.assertEqual(call_args[1]["data"]["field_name"], "email")
        self.assertEqual(call_args[1]["data"]["lineage_type"], "field")
        self.assertEqual(call_args[1]["data"]["relationship_count"], 5)

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_lineage_relationship_added(self, mock_publisher_class):
        """Test publishing lineage.relationship_added event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        source_ref = "namespace1/contract1/model1/field1"
        target_ref = "namespace2/contract2/model2/field2"
        event_id = service.publish_lineage_relationship_added(
            contract_id=contract_id,
            source_reference=source_ref,
            target_reference=target_ref,
            relationship_type="depends_on",
            model_name="UserModel",
            field_name="email",
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "lineage.relationship_added")
        self.assertEqual(call_args[1]["data"]["contract_id"], contract_id)
        self.assertEqual(call_args[1]["data"]["source_reference"], source_ref)
        self.assertEqual(call_args[1]["data"]["target_reference"], target_ref)
        self.assertEqual(call_args[1]["data"]["relationship_type"], "depends_on")
        self.assertEqual(call_args[1]["data"]["model_name"], "UserModel")
        self.assertEqual(call_args[1]["data"]["field_name"], "email")

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_lineage_relationship_removed(self, mock_publisher_class):
        """Test publishing lineage.relationship_removed event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        source_ref = "namespace1/contract1/model1/field1"
        target_ref = "namespace2/contract2/model2/field2"
        event_id = service.publish_lineage_relationship_removed(
            contract_id=contract_id,
            source_reference=source_ref,
            target_reference=target_ref,
            relationship_type="depends_on",
            model_name="UserModel",
            field_name="email",
            reason="Contract deleted",
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "lineage.relationship_removed")
        self.assertEqual(call_args[1]["data"]["contract_id"], contract_id)
        self.assertEqual(call_args[1]["data"]["source_reference"], source_ref)
        self.assertEqual(call_args[1]["data"]["target_reference"], target_ref)
        self.assertEqual(call_args[1]["data"]["relationship_type"], "depends_on")
        self.assertEqual(call_args[1]["data"]["model_name"], "UserModel")
        self.assertEqual(call_args[1]["data"]["field_name"], "email")
        self.assertEqual(call_args[1]["data"]["reason"], "Contract deleted")

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_lineage_updated_with_minimal_data(self, mock_publisher_class):
        """Test publishing lineage.updated event with only required fields."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        event_id = service.publish_lineage_updated(contract_id=contract_id)

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "lineage.updated")
        self.assertEqual(call_args[1]["data"]["contract_id"], contract_id)
        self.assertIsNone(call_args[1]["data"]["model_name"])
        self.assertIsNone(call_args[1]["data"]["field_name"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_lineage_relationship_added_with_minimal_data(self, mock_publisher_class):
        """Test publishing lineage.relationship_added event with only required fields."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        contract_id = str(uuid.uuid4())
        source_ref = "namespace1/contract1"
        target_ref = "namespace2/contract2"
        event_id = service.publish_lineage_relationship_added(
            contract_id=contract_id, source_reference=source_ref, target_reference=target_ref
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "lineage.relationship_added")
        self.assertEqual(call_args[1]["data"]["contract_id"], contract_id)
        self.assertEqual(call_args[1]["data"]["source_reference"], source_ref)
        self.assertEqual(call_args[1]["data"]["target_reference"], target_ref)


class SearchEventPublisherTest(ServicePublisherMixin, TestCase):
    """Test SearchEventPublisher."""

    def create_service(self):
        """Create SearchService with event publisher."""
        tenant_id = self.tenant_id
        user_id = self.user_id

        class TestService(SearchEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__()

        return TestService()

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_search_query(self, mock_publisher_class):
        """Test publishing search.query event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        query = "test query"
        event_id = service.publish_search_query(
            query=query,
            query_type="SEARCH",
            filters={"type": "ASSET", "classification": "PUBLIC"},
            result_count=10,
            no_results=False,
            execution_time_ms=150,
        )

        self.assertIsNotNone(event_id)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "search.query")
        self.assertEqual(call_args[1]["data"]["query"], query)
        self.assertEqual(call_args[1]["data"]["query_type"], "SEARCH")
        self.assertEqual(call_args[1]["data"]["result_count"], 10)
        self.assertEqual(call_args[1]["data"]["no_results"], False)
        self.assertEqual(call_args[1]["data"]["execution_time_ms"], 150)
        self.assertIn("search", call_args[1]["tags"])
        self.assertIn("query", call_args[1]["tags"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_index_updated(self, mock_publisher_class):
        """Test publishing search.index.updated event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        resource_type = "ASSET"
        resource_id = str(uuid.uuid4())
        index_id = str(uuid.uuid4())
        event_id = service.publish_index_updated(
            resource_type=resource_type,
            resource_id=resource_id,
            index_id=index_id,
            title="Test Asset",
            update_type="updated",
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "search.index.updated")
        self.assertEqual(call_args[1]["data"]["resource_type"], resource_type)
        self.assertEqual(call_args[1]["data"]["resource_id"], resource_id)
        self.assertEqual(call_args[1]["data"]["index_id"], index_id)
        self.assertEqual(call_args[1]["data"]["title"], "Test Asset")
        self.assertEqual(call_args[1]["data"]["update_type"], "updated")
        self.assertIn("search", call_args[1]["tags"])
        self.assertIn("index", call_args[1]["tags"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher")
    def test_publish_index_rebuilt(self, mock_publisher_class):
        """Test publishing search.index.rebuilt event."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = str(uuid.uuid4())

        service = self.create_service()
        tenant_id = str(uuid.uuid4())
        event_id = service.publish_index_rebuilt(
            tenant_id=tenant_id,
            resource_count=100,
            duration_ms=5000,
            resource_types=["ASSET", "CONTRACT", "DATASET"],
            success=True,
            errors=[],
        )

        self.assertIsNotNone(event_id)
        call_args = mock_publisher.publish.call_args
        self.assertEqual(call_args[1]["event_type"], "search.index.rebuilt")
        self.assertEqual(call_args[1]["data"]["tenant_id"], tenant_id)
        self.assertEqual(call_args[1]["data"]["resource_count"], 100)
        self.assertEqual(call_args[1]["data"]["duration_ms"], 5000)
        self.assertEqual(len(call_args[1]["data"]["resource_types"]), 3)
        self.assertEqual(call_args[1]["data"]["success"], True)
        self.assertEqual(len(call_args[1]["data"]["errors"]), 0)
        self.assertEqual(call_args[1]["tenant_id"], tenant_id)
        self.assertIn("search", call_args[1]["tags"])
        self.assertIn("index", call_args[1]["tags"])
        self.assertIn("rebuild", call_args[1]["tags"])
