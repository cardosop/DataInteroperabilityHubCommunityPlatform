"""
Integration tests for Transformation Pipeline Workflow

Tests workflow execution with real services and models.
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
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
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TransformationPipelineWorkflowIntegrationTest(TestCase):
    """Integration tests for transformation pipeline workflow"""

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
                    }
                ]
            },
            status=PipelineStatus.ACTIVE,
            version="1.0.0"
        )
        # Create source asset with contract and dataset for compatibility validation
        self.source_asset = Asset.objects.create(
            tenant=self.tenant,
            key="source-asset",
            name="Source Asset",
            description="Source asset for transformation",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user
        )

        # Create contract for asset
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.source_asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-contract", "name": "Test Contract", "schema": {"fields": []}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "test-contract",
                "name": "Test Contract",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "name", "type": "string"}
                    ]
                }
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        # Create CSV file content
        self.csv_content = b"id,name\n1,Alice\n2,Bob\n3,Charlie"

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            content_type="text/csv",
            size=len(self.csv_content),
            status=FileStatus.ACTIVE,
            storage_path=f"test/integration/{self.source_asset.id}/test.csv"
        )

        # Upload file to storage (real service)
        from hub.apps.files.storage import S3StorageClient
        try:
            storage_client = S3StorageClient()
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.csv_content
            )
            # Update file storage_path to match what was actually saved
            self.file.storage_path = storage_path
            self.file.save(update_fields=['storage_path'])
            self.storage_available = True
        except Exception as e:
            # Storage might not be available, tests will skip
            self.storage_available = False
            self.storage_error = str(e)

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.source_asset,
            file=self.file,
            format="CSV",
            version=1,
            row_count=3,
            schema_json={
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        TransformationPipelineWorkflow.register_workflow(self.registry)
        TransformationPipelineWorkflow.register_tasks(self.engine)

    def test_workflow_execution_complete_flow(self):
        """Test complete workflow execution flow"""
        # Skip if storage is not available
        if not getattr(self, 'storage_available', True):
            self.skipTest(f"Storage not available: {getattr(self, 'storage_error', 'Unknown error')}")

        # Execute workflow
        result = TransformationPipelineWorkflow.execute(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.source_asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode="ASYNC",
            engine=self.engine,
            registry=self.registry
        )

        # Verify workflow completed successfully
        self.assertIn("success", result)
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("execution_id", result)

        # Verify workflow instance
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(workflow_instance.workflow_name, TransformationPipelineWorkflow.WORKFLOW_NAME)

        # Verify execution was created
        execution = PipelineExecution.objects.get(id=result["execution_id"])
        self.assertEqual(execution.pipeline, self.pipeline)
        self.assertEqual(execution.asset, self.source_asset)
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)

        # Verify progress tracking
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)
        self.assertEqual(workflow_instance.state_data["current_step"], "complete")

    def test_workflow_execution_with_validation_failure(self):
        """Test workflow execution with validation failure"""
        # Create invalid pipeline using bulk_create to bypass model validation
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

        # Execute workflow - should fail at validation step
        with self.assertRaises(ValueError) as context:
            TransformationPipelineWorkflow.execute(
                pipeline_id=str(invalid_pipeline.id),
                asset_id=str(self.source_asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode="ASYNC",
                engine=self.engine,
                registry=self.registry
            )

        self.assertIn("failed", str(context.exception).lower())

    def test_workflow_state_data_persistence(self):
        """Test that workflow state data is persisted correctly"""
        # Skip if storage is not available
        if not getattr(self, 'storage_available', True):
            self.skipTest(f"Storage not available: {getattr(self, 'storage_error', 'Unknown error')}")

        result = TransformationPipelineWorkflow.execute(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.source_asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode="ASYNC",
            engine=self.engine,
            registry=self.registry
        )

        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])

        # Verify state data contains expected keys
        self.assertIn("pipeline_id", workflow_instance.state_data)
        self.assertIn("asset_id", workflow_instance.state_data)
        self.assertIn("execution_id", workflow_instance.state_data)
        self.assertIn("progress_percentage", workflow_instance.state_data)
        self.assertIn("validation_result", workflow_instance.state_data)
        self.assertIn("compatibility_result", workflow_instance.state_data)

        # Verify values
        self.assertEqual(workflow_instance.state_data["pipeline_id"], str(self.pipeline.id))
        self.assertEqual(workflow_instance.state_data["asset_id"], str(self.source_asset.id))

    def test_workflow_progress_tracking(self):
        """Test workflow progress tracking throughout execution"""
        # Skip if storage is not available
        if not getattr(self, 'storage_available', True):
            self.skipTest(f"Storage not available: {getattr(self, 'storage_error', 'Unknown error')}")

        result = TransformationPipelineWorkflow.execute(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.source_asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode="ASYNC",
            engine=self.engine,
            registry=self.registry
        )

        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])

        # Verify final progress is 100%
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

        # Verify progress was tracked at each step
        # (We can't verify intermediate progress values as they're overwritten,
        # but we can verify the final value and that progress tracking was called)
        self.assertIn("current_step", workflow_instance.state_data)
        self.assertEqual(workflow_instance.state_data["current_step"], "complete")

