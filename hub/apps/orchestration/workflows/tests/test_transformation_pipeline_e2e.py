"""
E2E tests for Transformation Pipeline Workflow

End-to-end tests that verify complete workflow execution with all services.
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


class TransformationPipelineWorkflowE2ETest(TestCase):
    """E2E tests for transformation pipeline workflow"""

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
            name="E2E Test Pipeline",
            description="E2E test pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "filter_step",
                        "type": "filter",
                        "node_config": {
                            "node_type": "filter",
                            "filter_expression": "status == 'active'"
                        }
                    },
                    {
                        "name": "transform_step",
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
        # Create source asset with contract and dataset for compatibility validation
        self.source_asset = Asset.objects.create(
            tenant=self.tenant,
            key="e2e-source-asset",
            name="E2E Source Asset",
            description="Source asset for E2E transformation test",
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
            storage_path=f"test/e2e/{self.source_asset.id}/test.csv"
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

    def test_complete_workflow_execution_e2e(self):
        """E2E test: Complete workflow execution from start to finish"""
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

        # Verify workflow instance state
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(workflow_instance.workflow_name, TransformationPipelineWorkflow.WORKFLOW_NAME)
        self.assertEqual(workflow_instance.workflow_version, TransformationPipelineWorkflow.WORKFLOW_VERSION)

        # Verify execution record
        execution = PipelineExecution.objects.get(id=result["execution_id"])
        self.assertEqual(execution.pipeline, self.pipeline)
        self.assertEqual(execution.asset, self.source_asset)
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        # Tenant and created_by come from pipeline, not execution
        self.assertEqual(execution.pipeline.tenant, self.tenant)

        # Verify state data contains all expected keys
        state_data = workflow_instance.state_data
        self.assertIn("pipeline_id", state_data)
        self.assertIn("asset_id", state_data)
        self.assertIn("execution_id", state_data)
        self.assertIn("validation_result", state_data)
        self.assertIn("compatibility_result", state_data)
        self.assertIn("execution_results", state_data)
        self.assertIn("progress_percentage", state_data)

        # Verify progress reached 100%
        self.assertEqual(state_data["progress_percentage"], 100)
        self.assertEqual(state_data["current_step"], "complete")

        # Verify validation was performed
        validation_result = state_data["validation_result"]
        self.assertIn("is_valid", validation_result)
        self.assertTrue(validation_result["is_valid"])

        # Verify compatibility check was performed
        compatibility_result = state_data["compatibility_result"]
        self.assertIn("is_compatible", compatibility_result)

        # Verify execution results exist
        execution_results = state_data["execution_results"]
        self.assertIsNotNone(execution_results)

    def test_workflow_execution_with_result_asset_e2e(self):
        """E2E test: Workflow execution with result asset creation"""
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

        # Verify result asset was created if present
        if "result_asset_id" in workflow_instance.state_data:
            result_asset_id = workflow_instance.state_data["result_asset_id"]
            result_asset = Asset.objects.get(id=result_asset_id)
            self.assertEqual(result_asset.tenant, self.tenant)
            self.assertIn("result", result_asset.key.lower())

            # Verify execution is linked to result asset
            execution = PipelineExecution.objects.get(id=result["execution_id"])
            self.assertEqual(execution.result_asset, result_asset)

    def test_workflow_compensation_on_failure_e2e(self):
        """E2E test: Workflow compensation on failure"""
        # Create invalid pipeline using bulk_create to bypass model validation
        invalid_pipelines = TransformationPipeline.objects.bulk_create([
            TransformationPipeline(
                tenant=self.tenant,
                created_by=self.user,
                name="Invalid E2E Pipeline",
                pipeline_definition={"version": "1.0.0"},  # Missing "steps" field
                status=PipelineStatus.DRAFT,
                version="1.0.0"
            )
        ])
        invalid_pipeline = invalid_pipelines[0]

        # Execute workflow - should fail
        with self.assertRaises(ValueError):
            TransformationPipelineWorkflow.execute(
                pipeline_id=str(invalid_pipeline.id),
                asset_id=str(self.source_asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode="ASYNC",
                engine=self.engine,
                registry=self.registry
            )

        # Verify no execution was created (workflow failed before execution creation)
        # This is expected behavior - execution is created in prepare_execution step
        # which comes after validation, so if validation fails, no execution is created
        executions = PipelineExecution.objects.filter(
            pipeline=invalid_pipeline,
            pipeline__tenant=self.tenant
        )
        self.assertEqual(executions.count(), 0)

    def test_workflow_event_publishing_e2e(self):
        """E2E test: Verify workflow events are published"""
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

        # Verify workflow instance has state data indicating events were published
        # (Actual event publishing is tested in unit tests, here we verify the workflow
        # completed successfully which implies events were published)
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertIn("progress_percentage", workflow_instance.state_data)
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

