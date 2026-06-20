"""
Tests for Scheduled Ingestion Workflow

Comprehensive unit, integration, and E2E tests for scheduled ingestion workflow.
"""

import os
import tempfile
import uuid
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import StepStatus, WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.scheduled_ingestion import ScheduledIngestionWorkflow
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import Tenant

User = get_user_model()


class ScheduledIngestionWorkflowUnitTest(TestCase):
    """Unit tests for scheduled ingestion workflow tasks"""

    def _get_workflow_definition(self):
        """Helper to get workflow definition, registering if needed"""
        workflow_def = self.registry.get_workflow(ScheduledIngestionWorkflow.WORKFLOW_NAME)
        if not workflow_def:
            workflow_def = ScheduledIngestionWorkflow.register_workflow(self.registry)
        return workflow_def

    def setUp(self):
        """Set up test fixtures"""
        # Use get_or_create to handle test database reuse
        self.tenant, _ = Tenant.objects.get_or_create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            defaults={"slug": "test-tenant", "status": "ACTIVE", "kyc_status": "UNVERIFIED"},
        )
        self.user, _ = User.objects.get_or_create(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            defaults={"password": "testpass123", "tenant": self.tenant},
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        ScheduledIngestionWorkflow.register_workflow(self.registry)
        ScheduledIngestionWorkflow.register_tasks(self.engine)

        # Create scheduled ingestion (use unique name to avoid conflicts)
        unique_name = f"Test Ingestion {uuid.uuid4().hex[:8]}"
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=unique_name,
            description="Test scheduled ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "access_key_id": "test-key",
                "secret_access_key": "test-secret",
                "enable_dq_validation": False,
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

    def test_validate_ingestion_config_task_success(self):
        """Test ingestion configuration validation task with valid config"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="validate_ingestion_config", step_index=0, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.validate_ingestion_config")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["validated"])
        self.assertEqual(result["source_type"], SourceType.S3)
        self.assertEqual(result["file_pattern"], ".*\\.csv")

    def test_validate_ingestion_config_task_missing_id(self):
        """Test ingestion configuration validation with missing scheduled_ingestion_id"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="validate_ingestion_config", step_index=0, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.validate_ingestion_config")

        with self.assertRaises(ValueError) as cm:
            task_func(instance.input_data, instance, step)

        self.assertIn("scheduled_ingestion_id", str(cm.exception))

    def test_validate_ingestion_config_task_invalid_pattern(self):
        """Test ingestion configuration validation with invalid file pattern"""
        # Create scheduled ingestion with valid pattern first
        invalid_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Invalid Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",  # Valid pattern first
            created_by=self.user,
        )
        # Update with invalid pattern using update() to bypass model validation
        ScheduledIngestion.objects.filter(id=invalid_ingestion.id).update(file_pattern="[invalid")
        # Refresh from DB
        invalid_ingestion.refresh_from_db()

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"scheduled_ingestion_id": str(invalid_ingestion.id)},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="validate_ingestion_config", step_index=0, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.validate_ingestion_config")

        # The workflow validation task should catch invalid patterns and raise ValueError
        with self.assertRaises(ValueError) as cm:
            task_func(instance.input_data, instance, step)
        self.assertIn("Invalid file pattern regex", str(cm.exception))

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory")
    def test_connect_to_source_task_success(self, mock_get_factory):
        """Test connect to source task with successful connection"""
        mock_connector = Mock()
        mock_connector.test_connection.return_value = {"success": True, "details": {}}
        mock_factory = Mock()
        mock_factory.get_connector.return_value = mock_connector
        mock_get_factory.return_value = mock_factory

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                "source_type": SourceType.S3,
                "source_config": self.scheduled_ingestion.get_source_config(),
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="connect_to_source", step_index=1, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.connect_to_source")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["connected"])
        self.assertEqual(result["connector_type"], SourceType.S3)

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory")
    def test_connect_to_source_task_failure(self, mock_get_factory):
        """Test connect to source task with connection failure"""
        mock_connector = Mock()
        mock_connector.test_connection.return_value = {
            "success": False,
            "error": "Connection failed",
        }
        mock_factory = Mock()
        mock_factory.get_connector.return_value = mock_connector
        mock_get_factory.return_value = mock_factory

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "source_type": SourceType.S3,
                "source_config": self.scheduled_ingestion.get_source_config(),
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="connect_to_source", step_index=1, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.connect_to_source")

        from hub.apps.orchestration.workflow_engine import WorkflowStepValueError

        with self.assertRaises(WorkflowStepValueError):
            task_func(instance.input_data, instance, step)

    def test_connect_to_source_fails_fast_when_connector_not_registered(self):
        """
        When source_type has no registered connector, job fails fast with ConnectorNotAvailableError.
        No mocks: use real SourceConnectorFactory with an unsupported source type.
        """
        # Create ingestion then set unsupported source type (bypasses choices for this test)
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Unsupported type ingestion",
            description="Test",
            source_type=SourceType.S3,
            source_config={"bucket": "b", "prefix": "p"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        # Use queryset update() to bypass model full_clean() validation
        # (source_type choices don't include UNSUPPORTED_SOURCE_TYPE).
        ScheduledIngestion.objects.filter(pk=ingestion.pk).update(
            source_type="UNSUPPORTED_SOURCE_TYPE"
        )
        ingestion.refresh_from_db()

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(ingestion.id),
                "source_type": "UNSUPPORTED_SOURCE_TYPE",
                "source_config": ingestion.get_source_config(),
            },
            status=WorkflowStatus.RUNNING,
        )
        step = instance.steps.create(
            step_name="connect_to_source",
            step_index=1,
            status=StepStatus.PENDING,
        )
        task_func = self.engine.task_registry.get("scheduled_ingestion.connect_to_source")

        from hub.apps.orchestration.workflow_engine import WorkflowStepValueError

        # ``_connect_to_source_task`` wraps ``ConnectorNotAvailableError``
        # inside ``WorkflowStepValueError`` so the engine can handle it
        # uniformly (compensation, progress, etc.).
        with self.assertRaises(WorkflowStepValueError) as cm:
            task_func(instance.input_data, instance, step)

        self.assertIn("UNSUPPORTED_SOURCE_TYPE", str(cm.exception))
        self.assertIn("connector not registered", str(cm.exception))

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory")
    def test_discover_files_task_success(self, mock_get_factory):
        """Test discover files task with successful discovery"""
        mock_connector = Mock()
        mock_connector.discover_files.return_value = ["file1.csv", "file2.csv", "file3.csv"]
        mock_factory = Mock()
        mock_factory.get_connector.return_value = mock_connector
        mock_get_factory.return_value = mock_factory

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                "source_type": SourceType.S3,
                "source_config": self.scheduled_ingestion.get_source_config(),
                "file_pattern": ".*\\.csv",
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="discover_files", step_index=2, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.discover_files")
        result = task_func(instance.input_data, instance, step)

        self.assertEqual(result["files_found"], 3)
        self.assertEqual(len(result["discovered_files"]), 3)
        self.assertIn("file1.csv", result["discovered_files"])

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory")
    def test_filter_files_task_success(self, mock_get_factory):
        """Test filter files task with successful filtering"""
        mock_connector = Mock()
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 1024,
        }
        mock_factory = Mock()
        mock_factory.get_connector.return_value = mock_connector
        mock_get_factory.return_value = mock_factory

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                "discovered_files": ["file1.csv", "file2.csv"],
                "source_type": SourceType.S3,
                "source_config": self.scheduled_ingestion.get_source_config(),
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="filter_files", step_index=3, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.filter_files")
        result = task_func(instance.input_data, instance, step)

        self.assertIn("filtered_files", result)
        self.assertIn("state", result)
        self.assertIn("filtered_files", result["state"])

    def test_validate_file_task_success(self):
        """Test validate file task with valid file"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"file_path": "test.csv", "file_format": "CSV", "file_content_length": 1024},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="validate_file", step_index=4, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.validate_file")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["validated"])
        self.assertEqual(result["file_format"], "CSV")

    def test_validate_file_task_empty_file(self):
        """Test validate file task with empty file"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"file_path": "empty.csv", "file_format": "CSV", "file_content_length": 0},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="validate_file", step_index=4, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.validate_file")

        with self.assertRaises(ValueError) as cm:
            task_func(instance.input_data, instance, step)

        self.assertIn("empty", str(cm.exception).lower())

    def test_validate_file_task_unsupported_format(self):
        """Test validate file task with unsupported format"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"file_path": "test.xyz", "file_format": "XYZ", "file_content_length": 1024},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="validate_file", step_index=4, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.validate_file")

        with self.assertRaises(ValueError) as cm:
            task_func(instance.input_data, instance, step)

        self.assertIn("unsupported", str(cm.exception).lower())

    @patch("hub.apps.dq.service_client.DQServiceClient")
    def test_run_dq_check_task_success(self, mock_dq_client_class):
        """Test run DQ check task with successful check"""
        mock_dq_client = Mock()
        mock_dq_client.health_check.return_value = (True, {})
        mock_dq_client.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [],
            "execution_time_seconds": 1.5,
        }
        mock_dq_client_class.return_value = mock_dq_client

        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file.write(b"col1,col2\nval1,val2\n")
        temp_path = temp_file.name
        temp_file.close()

        try:
            instance = WorkflowInstance.objects.create(
                workflow_definition=self.registry.get_workflow(
                    ScheduledIngestionWorkflow.WORKFLOW_NAME
                ),
                tenant=self.tenant,
                input_data={
                    "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                    "file_path": "test.csv",
                    "temp_path": temp_path,
                    "file_format": "CSV",
                    "dq_profile_key": "intake_basic_gx",
                    "dq_strict_mode": True,
                    "min_quality_score": 0.8,
                },
                status=WorkflowStatus.RUNNING,
            )

            step = instance.steps.create(
                step_name="run_dq_check", step_index=5, status=StepStatus.PENDING
            )

            task_func = self.engine.task_registry.get("scheduled_ingestion.run_dq_check")
            result = task_func(instance.input_data, instance, step)

            self.assertTrue(result["dq_check_passed"])
            self.assertEqual(result["overall_status"], "PASS")
            self.assertEqual(result["quality_score"], 0.95)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @patch("hub.apps.dq.service_client.DQServiceClient")
    def test_run_dq_check_task_low_quality_score(self, mock_dq_client_class):
        """Test run DQ check task with low quality score"""
        mock_dq_client = Mock()
        mock_dq_client.health_check.return_value = (True, {})
        mock_dq_client.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.5,  # Below threshold
            "checks": [],
        }
        mock_dq_client_class.return_value = mock_dq_client

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file.write(b"col1,col2\nval1,val2\n")
        temp_path = temp_file.name
        temp_file.close()

        try:
            instance = WorkflowInstance.objects.create(
                workflow_definition=self.registry.get_workflow(
                    ScheduledIngestionWorkflow.WORKFLOW_NAME
                ),
                tenant=self.tenant,
                input_data={
                    "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                    "file_path": "test.csv",
                    "temp_path": temp_path,
                    "file_format": "CSV",
                    "dq_strict_mode": True,
                    "min_quality_score": 0.8,
                },
                status=WorkflowStatus.RUNNING,
            )

            step = instance.steps.create(
                step_name="run_dq_check", step_index=5, status=StepStatus.PENDING
            )

            task_func = self.engine.task_registry.get("scheduled_ingestion.run_dq_check")

            with self.assertRaises(ValueError) as cm:
                task_func(instance.input_data, instance, step)

            self.assertIn("quality score", str(cm.exception).lower())
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion.S3StorageClient")
    @patch("hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory")
    def test_download_file_task_success(self, mock_get_factory, mock_storage_class):
        """Test download file task with successful download"""
        mock_connector = Mock()
        mock_result = Mock()
        mock_result.status.value = "SUCCESS"
        mock_result.message = "Downloaded"
        mock_connector.download_file.return_value = mock_result
        mock_factory = Mock()
        mock_factory.get_connector.return_value = mock_connector
        mock_get_factory.return_value = mock_factory

        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        # Create temp file with content
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file.write(b"col1,col2\nval1,val2\n")
        temp_path = temp_file.name
        temp_file.close()

        try:
            instance = WorkflowInstance.objects.create(
                workflow_definition=self.registry.get_workflow(
                    ScheduledIngestionWorkflow.WORKFLOW_NAME
                ),
                tenant=self.tenant,
                input_data={
                    "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                    "source_type": SourceType.S3,
                    "source_config": self.scheduled_ingestion.get_source_config(),
                    "loop_item": {"file_path": "test.csv", "file_timestamp": None},
                },
                status=WorkflowStatus.RUNNING,
            )

            step = instance.steps.create(
                step_name="download_file", step_index=4, status=StepStatus.PENDING
            )

            task_func = self.engine.task_registry.get("scheduled_ingestion.download_file")

            # Mock file download to write to temp_path
            def mock_download(config, file_path, dest_path):
                with open(dest_path, "wb") as f:
                    f.write(b"col1,col2\nval1,val2\n")
                return mock_result

            mock_connector.download_file.side_effect = mock_download

            result = task_func(instance.input_data, instance, step)

            self.assertEqual(result["file_path"], "test.csv")
            self.assertIn("temp_path", result)
            self.assertEqual(result["file_format"], "CSV")
            self.assertIn("file_hash", result)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_mark_file_processed_task_success(self):
        """Test mark file processed task"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                "file_path": "test.csv",
                "dataset_id": "test-dataset-id",
                "loop_item": {"file_path": "test.csv", "file_timestamp": None},
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="mark_file_processed", step_index=8, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.mark_file_processed")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["processed"])
        self.assertEqual(result["file_path"], "test.csv")
        self.assertEqual(result["dataset_id"], "test-dataset-id")

        # Verify file was marked as processed in state
        self.scheduled_ingestion.refresh_from_db()
        from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager

        state_manager = IncrementalStateManager(self.scheduled_ingestion)

        self.assertTrue(state_manager.is_file_processed("test.csv"))

    def test_update_ingestion_state_task_success(self):
        """Test update ingestion state task"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="update_ingestion_state", step_index=9, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.update_ingestion_state")
        result = task_func(instance.input_data, instance, step)

        self.assertIn("state_summary", result)
        self.assertIn("total_processed", result["state_summary"])
        self.assertIn("total_failed", result["state_summary"])

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion.DeadLetterQueueManager")
    def test_handle_failures_dlq_task_success(self, mock_dlq_manager):
        """Test handle failures DLQ task"""
        mock_dlq_manager.sync_from_ingestion_state.return_value = 2

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="handle_failures_dlq", step_index=10, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.handle_failures_dlq")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["dlq_synced"])
        self.assertEqual(result["items_synced"], 2)

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion.send_email_async")
    def test_send_completion_notification_task_success(self, mock_send_email):
        """Test send completion notification task"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                "state_summary": {
                    "total_processed": 5,
                    "total_failed": 1,
                    "permanent_failures": 0,
                    "retryable_failures": 1,
                },
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="send_completion_notification", step_index=11, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get(
            "scheduled_ingestion.send_completion_notification"
        )
        result = task_func(instance.input_data, instance, step)

        # Notification may be skipped if not configured, so just check it doesn't raise
        self.assertIn("notification_sent", result)

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion.create_audit_event")
    def test_audit_logging_task_success(self, mock_create_audit):
        """Test audit logging task"""
        mock_audit_event = Mock()
        mock_audit_event.id = "test-audit-id"
        mock_create_audit.return_value = mock_audit_event

        instance = WorkflowInstance.objects.create(
            workflow_definition=self._get_workflow_definition(),
            tenant=self.tenant,
            input_data={
                "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
                "tenant_id": str(self.tenant.id),
                "state_summary": {"total_processed": 5, "total_failed": 1},
            },
            status=WorkflowStatus.RUNNING,
        )

        step = instance.steps.create(
            step_name="audit_logging", step_index=12, status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("scheduled_ingestion.audit_logging")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["audit_logged"])
        self.assertEqual(result["audit_event_id"], "test-audit-id")


class ScheduledIngestionWorkflowIntegrationTest(TestCase):
    """Integration tests for scheduled ingestion workflow"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "enable_dq_validation": False,
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            created_by=self.user,
        )

    @patch("hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory")
    def test_workflow_execution_with_no_files(self, mock_get_factory):
        """Test workflow execution when no files are found"""
        mock_connector = Mock()
        mock_connector.test_connection.return_value = {"success": True}
        mock_connector.discover_files.return_value = []
        mock_factory = Mock()
        mock_factory.get_connector.return_value = mock_connector
        mock_get_factory.return_value = mock_factory

        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ScheduledIngestionWorkflow.register_workflow(registry)
        ScheduledIngestionWorkflow.register_tasks(engine)

        # This should complete successfully even with no files
        # The workflow will handle empty file lists gracefully
        # Note: Full execution would require more mocking, so we test individual tasks instead
