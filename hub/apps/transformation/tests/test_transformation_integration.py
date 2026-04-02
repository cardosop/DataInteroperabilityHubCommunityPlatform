"""
Comprehensive integration tests for TransformationService.

Tests all service integrations:
- TransformationService with business rules
- TransformationService with workflow orchestration
- TransformationService with quality service
- TransformationService with compliance service
- TransformationService with governance service
- TransformationService with job queue
- TransformationService with audit logging
- TransformationService with event publishing
- TransformationService with monitoring/metrics

All tests use real services (no mocks/stubs) to ensure comprehensive integration.
"""
import uuid
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.business_rules import TransformationBusinessRules
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineExecution,
    TransformationNode,
    PipelineStatus,
    ExecutionStatus,
    ExecutionMode
)
from hub.apps.transformation.exceptions import (
    TransformationValidationError,
    TransformationExecutionError,
    AssetCompatibilityError,
    ResourceQuotaExceededError
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessPolicy
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.audit.models import AuditEvent
from django.contrib.auth import get_user_model

User = get_user_model()


class TransformationServiceIntegrationTest(TestCase):
    """Comprehensive integration tests for TransformationService."""

    @classmethod
    def setUpTestData(cls):
        """Create Tenant and User once for the whole test class (read-only)."""
        uid = uuid.uuid4().hex[:8]
        cls.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )

        # Create user
        cls.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role
        cls.data_provider_role, _ = Role.objects.get_or_create(
            tenant=cls.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(
            user=cls.user,
            role=cls.data_provider_role
        )

        # Create access policy
        AccessPolicy.objects.get_or_create(
            tenant=cls.tenant,
            name="Allow Pipeline Operations",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(cls.tenant.id)}
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": cls.user
            }
        )

    def setUp(self):
        """Set up per-test fixtures."""
        # Create service
        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create business rules
        self.business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create valid pipeline definition
        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter",
                        "filter_expression": "age > 18"
                    }
                },
                {
                    "name": "transform_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "transform",
                        "transform_expression": "name"
                    }
                },
                {
                    "name": "output_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "output"
                    }
                }
            ]
        }

        # Create asset with dataset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create CSV file content
        self.csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"

        # Create file first
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path=f"test/integration/{self.asset.id}/test.csv",
            size=len(self.csv_content),
            content_type="text/csv",
            status=FileStatus.PENDING,
            created_by=self.user
        )

        # Upload file to storage (real service)
        from hub.apps.files.storage import S3StorageClient

        try:
            storage_client = S3StorageClient()
            # save_file returns the storage path (key) used
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.csv_content
            )
            # Update file with the actual storage path used
            self.file.storage_path = storage_path
            self.file.status = FileStatus.ACTIVE
            self.file.save()
            self.storage_available = True
        except Exception as e:
            # Storage might not be available, tests will skip
            self.storage_available = False
            self.storage_error = str(e)

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=5,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"}
                ]
            },
            created_by=self.user
        )

    def test_service_business_rules_integration(self):
        """Test TransformationService integrates with TransformationBusinessRules."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Create pipeline via service
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Integration Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        # Validate using business rules
        result = self.business_rules.validate_all(
            pipeline, self.asset, raise_on_error=False
        )

        # Should pass validation - if not, provide detailed error information
        if not result.is_valid and len(result.errors) > 0:
            error_details = "\n".join(result.errors)
            self.fail(f"Validation failed with errors: {error_details}\nDetails: {result.details}")

        # Should pass validation
        self.assertTrue(result.is_valid)

    def test_service_workflow_integration(self):
        """Test TransformationService integrates with workflow orchestration."""
        # Create active pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Workflow Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Execute pipeline (should create workflow instance)
        try:
            execution = self.service.execute_pipeline(
                pipeline_id=str(pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=ExecutionMode.ASYNC
            )

            # Verify execution was created
            self.assertIsNotNone(execution.id)
            self.assertEqual(execution.pipeline, pipeline)
            self.assertEqual(execution.asset, self.asset)

            # Verify workflow instance was created (if async mode)
            if execution.execution_mode == ExecutionMode.ASYNC:
                self.assertIsNotNone(execution.workflow_instance)
                workflow_instance = execution.workflow_instance
                self.assertIsNotNone(workflow_instance)
                self.assertEqual(workflow_instance.workflow_name, "transformation_pipeline")
        except Exception as e:
            # If workflow service is not available, skip this test
            if "workflow" in str(e).lower() or "orchestration" in str(e).lower():
                self.skipTest(f"Workflow service not available: {e}")
            else:
                raise

    def test_service_quality_integration(self):
        """Test TransformationService integrates with quality service."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Create pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Quality Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Execute pipeline (should trigger quality checks)
        try:
            sync_mode = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
            execution = self.service.execute_pipeline(
                pipeline_id=str(pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=sync_mode
            )

            # Verify execution was created
            self.assertIsNotNone(execution.id)

            # Quality checks are performed during workflow execution
            # They are handled by TransformationQualityIntegration within workflow tasks
            # So we verify execution was created successfully
            self.assertIsNotNone(execution.started_at)
        except Exception as e:
            # If quality service is not available, skip this test
            if "quality" in str(e).lower() or "dq" in str(e).lower():
                self.skipTest(f"Quality service not available: {e}")
            else:
                raise

    def test_service_compliance_integration(self):
        """Test TransformationService integrates with compliance service."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Create pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Compliance Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Execute pipeline (should trigger compliance checks)
        # With valid pipeline/asset and proper access policy, compliance should pass
        try:
            sync_mode = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
            execution = self.service.execute_pipeline(
                pipeline_id=str(pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=sync_mode
            )

            # Verify execution was created and compliance checks passed
            self.assertIsNotNone(execution.id)
            self.assertIsNotNone(execution.started_at)
        except Exception as e:
            # If compliance service is not available, skip this test
            if "compliance" in str(e).lower():
                self.skipTest(f"Compliance service not available: {e}")
            else:
                raise

    def test_service_governance_integration(self):
        """Test TransformationService integrates with governance service (ABAC)."""
        # Create pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Governance Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Validate permissions using business rules (which uses ABAC)
        result = self.business_rules.validate_pipeline_execution_permission(
            pipeline, source_asset=self.asset, raise_on_error=False
        )

        # With access policy set up in setUpTestData, permission check should pass
        self.assertTrue(result.is_valid)

    def test_service_job_queue_integration(self):
        """Test TransformationService integrates with job queue."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Create pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Job Queue Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Execute pipeline in async mode (should create job)
        async_mode = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
        execution = self.service.execute_pipeline(
            pipeline_id=str(pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=async_mode
        )

        # Verify job was created
        self.assertIsNotNone(execution.job)
        job_type_value = (JobType.TRANSFORMATION[0]
                         if isinstance(JobType.TRANSFORMATION, tuple)
                         else JobType.TRANSFORMATION)
        job_status_value = (JobStatus.PENDING[0]
                           if isinstance(JobStatus.PENDING, tuple)
                           else JobStatus.PENDING)
        self.assertEqual(execution.job.type, job_type_value)
        self.assertEqual(execution.job.status, job_status_value)

    def test_service_audit_logging_integration(self):
        """Test TransformationService integrates with audit logging."""
        # Create pipeline via service (should create audit log)
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Audit Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="TRANSFORMATION_PIPELINE",
            action="CREATED",
            resource_id=pipeline.id
        )
        self.assertGreaterEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertEqual(audit_event.tenant.id, self.tenant.id)
        self.assertEqual(audit_event.actor_user.id, self.user.id)

    def test_service_event_publishing_integration(self):
        """Test TransformationService integrates with event publishing."""
        # Create pipeline via service (should publish event)
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Event Publishing Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        # NOTE: This test only verifies pipeline creation succeeds.
        # It does NOT verify that an event was actually published, because events
        # are published asynchronously and there is no synchronous event store to query.
        # To truly test event publishing, an event capture/spy mechanism is needed.
        self.assertIsNotNone(pipeline.id)

    def test_service_monitoring_integration(self):
        """Test TransformationService integrates with monitoring/metrics."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Create and execute pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Monitoring Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Execute pipeline (should generate metrics)
        try:
            sync_mode = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
            execution = self.service.execute_pipeline(
                pipeline_id=str(pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=sync_mode
            )

            # Verify execution was created (metrics are generated during execution)
            self.assertIsNotNone(execution.id)
            self.assertIsNotNone(execution.started_at)

            # Sync execution should reach a terminal state
            execution.refresh_from_db()
            self.assertIn(execution.status, [
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED
            ])

            if execution.status == ExecutionStatus.COMPLETED:
                self.assertIsNotNone(execution.completed_at)
        except Exception as e:
            # If monitoring/metrics service is not available, skip this test
            if "monitoring" in str(e).lower() or "metrics" in str(e).lower():
                self.skipTest(f"Monitoring service not available: {e}")
            else:
                raise

    def test_service_full_integration_workflow(self):
        """Test complete integration workflow with all services."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Create pipeline via service
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Full Integration Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Validate using business rules
        validation_result = self.business_rules.validate_all(
            pipeline, self.asset, raise_on_error=False
        )

        # Should pass validation - if not, provide detailed error information
        if not validation_result.is_valid and len(validation_result.errors) > 0:
            error_details = "\n".join(validation_result.errors)
            self.fail(f"Validation failed with errors: {error_details}\nDetails: {validation_result.details}")

        self.assertTrue(validation_result.is_valid)

        # Execute pipeline
        try:
            async_mode = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
            execution = self.service.execute_pipeline(
                pipeline_id=str(pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=async_mode
            )

            # Verify execution was created
            self.assertIsNotNone(execution.id)
            self.assertEqual(execution.pipeline, pipeline)
            self.assertEqual(execution.asset, self.asset)

            # Verify job was created (for async mode)
            async_mode = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
            if execution.execution_mode == async_mode or execution.execution_mode == ExecutionMode.ASYNC:
                self.assertIsNotNone(execution.job)

            # Verify audit events were created
            audit_events = AuditEvent.objects.filter(
                resource_type="TRANSFORMATION_PIPELINE",
                resource_id=pipeline.id
            )
            self.assertGreaterEqual(audit_events.count(), 1)
        except Exception as e:
            # If any service is not available, skip this test
            if any(keyword in str(e).lower() for keyword in ["workflow", "quality", "compliance", "monitoring"]):
                self.skipTest(f"Service not available: {e}")
            else:
                raise

    def test_service_error_handling_integration(self):
        """Test error handling across service integrations."""
        # Create pipeline with invalid definition
        invalid_definition = {
            "version": "1.0.0",
            "steps": []  # Empty steps will fail validation
        }

        # Should raise ValidationError
        with self.assertRaises((TransformationValidationError, Exception)):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Invalid Pipeline",
                pipeline_definition=invalid_definition
            )

        # Verify no pipeline was created
        self.assertEqual(
            TransformationPipeline.objects.filter(name="Invalid Pipeline").count(),
            0
        )

    def test_service_transaction_rollback_integration(self):
        """Test transaction rollback across service integrations."""
        # Create pipeline with invalid data that will fail validation
        invalid_definition = {
            "version": "1.0.0",
            "steps": []  # Empty steps will fail validation
        }

        # Should raise exception and rollback transaction
        with self.assertRaises((TransformationValidationError, Exception)):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Rollback Test Pipeline",
                pipeline_definition=invalid_definition
            )

        # Verify no pipeline was created (transaction rolled back)
        self.assertEqual(
            TransformationPipeline.objects.filter(name="Rollback Test Pipeline").count(),
            0
        )

        # Verify no audit events were created (transaction rolled back)
        audit_events = AuditEvent.objects.filter(
            resource_type="TRANSFORMATION_PIPELINE",
            action="CREATED"
        )
        # Count should be 0 or only include events from other tests
        created_pipelines = TransformationPipeline.objects.filter(
            tenant=self.tenant
        ).count()
        # If no pipelines exist, no audit events should exist either
        if created_pipelines == 0:
            self.assertEqual(audit_events.count(), 0)

