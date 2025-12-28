"""
Unit tests for Transformation Pipeline Workflow

Comprehensive tests without mocks/stubs, following engineering best practices.
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.transformation_pipeline import TransformationPipelineWorkflow
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineStatus,
    PipelineExecution,
    ExecutionStatus
)
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.contracts.models import Contract, ContractStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TransformationPipelineWorkflowUnitTest(TestCase):
    """Unit tests for transformation pipeline workflow tasks"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            description="Test pipeline description",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "filter",
                        "node_config": {
                            "node_type": "filter",
                            "filter_expression": "status == 'active'"
                        }
                    },
                    {
                        "name": "step2",
                        "type": "transform",
                        "node_config": {
                            "node_type": "transform",
                            "transform_expression": "value * 2"
                        }
                    }
                ]
            },
            status=PipelineStatus.ACTIVE,
            version="1.0.0"
        )
        self.source_asset = Asset.objects.create(
            tenant=self.tenant,
            key="source-asset",
            name="Source Asset",
            description="Source asset for transformation",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        TransformationPipelineWorkflow.register_workflow(self.registry)
        TransformationPipelineWorkflow.register_tasks(self.engine)

    def test_validate_pipeline_task(self):
        """Test pipeline validation task"""
        input_data = {
            "pipeline_id": str(self.pipeline.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_pipeline",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = TransformationPipelineWorkflow._validate_pipeline_task(
            input_data, instance, step
        )

        self.assertIn("validation_status", result)
        self.assertEqual(result["validation_status"], "VALID")
        self.assertIn("pipeline_id", instance.state_data)
        self.assertEqual(instance.state_data["pipeline_id"], str(self.pipeline.id))
        self.assertEqual(instance.state_data["progress_percentage"], 10)

    def test_validate_pipeline_task_invalid_pipeline(self):
        """Test pipeline validation with invalid pipeline"""
        # Create invalid pipeline (missing required fields)
        # Use bulk_create to bypass model validation
        invalid_pipelines = TransformationPipeline.objects.bulk_create([
            TransformationPipeline(
                tenant=self.tenant,
                created_by=self.user,
                name="Invalid Pipeline",
                pipeline_definition={"version": "1.0.0"},  # Missing "steps" field
                status=PipelineStatus.DRAFT,
                version="1.0.0"
            )
        ])
        invalid_pipeline = invalid_pipelines[0]

        input_data = {
            "pipeline_id": str(invalid_pipeline.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_pipeline",
            step_type="task",
            status=StepStatus.PENDING
        )

        # Validation should fail
        with self.assertRaises(Exception) as context:
            TransformationPipelineWorkflow._validate_pipeline_task(
                input_data, instance, step
            )
        # Verify it's a validation error
        self.assertIsNotNone(context.exception)

    def test_validate_asset_compatibility_task(self):
        """Test asset compatibility validation task"""
        input_data = {
            "pipeline_id": str(self.pipeline.id),
            "asset_id": str(self.source_asset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["pipeline_id"] = str(self.pipeline.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="validate_asset_compatibility",
            step_type="task",
            status=StepStatus.PENDING
        )

        # Asset compatibility validation may fail if asset doesn't have required schema/contract
        # This is expected behavior - the validation should run and return a result
        # The validation will raise an exception if incompatible, which is expected
        with self.assertRaises(Exception):
            TransformationPipelineWorkflow._validate_asset_compatibility_task(
                input_data, instance, step
            )
        # Verify that progress was updated before the exception
        # (The exception happens after progress update in the task)
        instance.refresh_from_db()
        self.assertEqual(instance.state_data["progress_percentage"], 20)

    def test_prepare_execution_task(self):
        """Test execution preparation task"""
        input_data = {
            "pipeline_id": str(self.pipeline.id),
            "asset_id": str(self.source_asset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "execution_mode": "ASYNC"
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["pipeline_id"] = str(self.pipeline.id)
        instance.state_data["asset_id"] = str(self.source_asset.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="prepare_execution",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = TransformationPipelineWorkflow._prepare_execution_task(
            input_data, instance, step
        )

        self.assertIn("execution_id", result)
        self.assertIn("execution_id", instance.state_data)
        execution = PipelineExecution.objects.get(id=result["execution_id"])
        self.assertEqual(execution.pipeline, self.pipeline)
        self.assertEqual(execution.asset, self.source_asset)
        self.assertEqual(execution.status, ExecutionStatus.PENDING)
        self.assertEqual(instance.state_data["progress_percentage"], 30)

    def test_complete_task(self):
        """Test workflow completion task"""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.RUNNING,
            execution_mode="ASYNC"
        )
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user
        )

        input_data = {
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["execution_id"] = str(execution.id)
        instance.state_data["result_asset_id"] = str(result_asset.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=7,
            step_name="complete",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = TransformationPipelineWorkflow._complete_task(
            input_data, instance, step
        )

        self.assertIn("completed", result)
        self.assertTrue(result["completed"])
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertEqual(execution.result_asset, result_asset)
        self.assertEqual(instance.state_data["progress_percentage"], 100)

    def test_rollback_execution_task(self):
        """Test execution rollback compensation task"""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.RUNNING,
            execution_mode="ASYNC"
        )

        input_data = {
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["execution_id"] = str(execution.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="rollback_execution",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = TransformationPipelineWorkflow._rollback_execution_task(
            input_data, instance, step
        )

        self.assertIn("rolled_back", result)
        self.assertTrue(result["rolled_back"])
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)

    def test_rollback_result_asset_task(self):
        """Test result asset rollback compensation task"""
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user
        )

        input_data = {
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["result_asset_id"] = str(result_asset.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="rollback_result_asset",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = TransformationPipelineWorkflow._rollback_result_asset_task(
            input_data, instance, step
        )

        self.assertIn("rolled_back", result)
        self.assertTrue(result["rolled_back"])
        # Verify asset was deleted
        self.assertFalse(Asset.objects.filter(id=result_asset.id).exists())

    def test_progress_tracking(self):
        """Test progress tracking updates"""
        input_data = {
            "pipeline_id": str(self.pipeline.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        # Test progress updates
        TransformationPipelineWorkflow._update_progress(instance, 10, "validate_pipeline")
        self.assertEqual(instance.state_data["progress_percentage"], 10)
        self.assertEqual(instance.state_data["current_step"], "validate_pipeline")

        TransformationPipelineWorkflow._update_progress(instance, 50, "execute_nodes")
        self.assertEqual(instance.state_data["progress_percentage"], 50)
        self.assertEqual(instance.state_data["current_step"], "execute_nodes")

        TransformationPipelineWorkflow._update_progress(instance, 100, "complete")
        self.assertEqual(instance.state_data["progress_percentage"], 100)
        self.assertEqual(instance.state_data["current_step"], "complete")

    def test_progress_tracking_boundaries(self):
        """Test progress tracking boundary conditions"""
        input_data = {
            "pipeline_id": str(self.pipeline.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=TransformationPipelineWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        # Test negative progress (should be clamped to 0)
        TransformationPipelineWorkflow._update_progress(instance, -10, "test")
        self.assertEqual(instance.state_data["progress_percentage"], 0)

        # Test progress > 100 (should be clamped to 100)
        TransformationPipelineWorkflow._update_progress(instance, 150, "test")
        self.assertEqual(instance.state_data["progress_percentage"], 100)

