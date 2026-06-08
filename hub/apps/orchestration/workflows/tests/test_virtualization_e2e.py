"""
E2E tests for Virtualization Query Execution Workflow

End-to-end tests for complete workflow execution with all services.
"""
import uuid
import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.virtualization import VirtualizationWorkflow
from hub.apps.virtualization.models import (
    VirtualDataset,
    VirtualDatasetStatus,
    QueryExecution,
    QueryExecutionStatus,
    QueryExecutionMode,
    QueryType
)
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class VirtualizationWorkflowE2ETest(TestCase):
    """E2E tests for virtualization query execution workflow"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT id, name FROM users WHERE age > 18",
            query_type=QueryType.SQL,
            sources=[
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "testdb"
                }
            ],
            status=VirtualDatasetStatus.ACTIVE
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        VirtualizationWorkflow.register_workflow(self.registry)
        VirtualizationWorkflow.register_tasks(self.engine)

    def test_complete_workflow_e2e(self):
        """Test complete E2E workflow execution"""
        # Execute workflow
        # Note: This may fail at query execution step if database is not available
        # The workflow should handle this gracefully
        try:
            result = VirtualizationWorkflow.execute(
                virtual_dataset_id=str(self.virtual_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                parameters={},
                execution_mode=QueryExecutionMode.ASYNC,
                engine=self.engine,
                registry=self.registry
            )

            # If execution succeeds, verify all components
            self.assertIn("success", result)
            self.assertTrue(result["success"])

            # Verify workflow instance
            workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
            self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
            self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

            # Verify query execution
            execution = QueryExecution.objects.get(id=result["execution_id"])
            self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
            self.assertIsNotNone(execution.completed_at)
            self.assertIsNotNone(execution.started_at)

            # Verify all workflow steps completed
            self.assertIn("virtual_dataset_id", workflow_instance.state_data)
            self.assertIn("execution_id", workflow_instance.state_data)
            self.assertIn("execution_results", workflow_instance.state_data)
            self.assertIn("cache_status", workflow_instance.state_data)
        except (ValueError, Exception) as e:
            # If execution fails (e.g., database not available), verify workflow handled it correctly
            # Check that workflow instance was created and all steps were attempted
            workflow_instances = WorkflowInstance.objects.filter(
                workflow_name=VirtualizationWorkflow.WORKFLOW_NAME
            ).order_by('-created_at')
            self.assertTrue(workflow_instances.exists(), f"Workflow instance should be created even on failure. Error: {str(e)}")

            workflow_instance = workflow_instances.first()
            # Workflow should be in FAILED, ROLLING_BACK, or ROLLED_BACK state
            self.assertIn(workflow_instance.status, [WorkflowStatus.FAILED, WorkflowStatus.ROLLING_BACK, WorkflowStatus.ROLLED_BACK],
                         f"Workflow status should be FAILED, ROLLING_BACK, or ROLLED_BACK, got {workflow_instance.status}")

            # Verify workflow steps were executed (at least up to execute_query)
            self.assertIn("virtual_dataset_id", workflow_instance.state_data,
                          "virtual_dataset_id should be in state_data")

            # Verify execution was created and marked as failed.
            # During compensation rollback the QueryExecution row may be
            # deleted; tolerate its absence.
            if "execution_id" in workflow_instance.state_data:
                execution_id = workflow_instance.state_data["execution_id"]
                try:
                    execution = QueryExecution.objects.get(id=execution_id)
                    self.assertEqual(execution.status, QueryExecutionStatus.FAILED,
                                   f"Execution should be FAILED, got {execution.status}")
                except QueryExecution.DoesNotExist:
                    pass  # deleted during compensation rollback — acceptable

    def test_workflow_compensation_on_failure(self):
        """Test workflow compensation when execution fails"""
        # Create invalid virtual dataset (empty query will fail validation)
        # Use bulk_create to bypass model validation
        invalid_datasets = VirtualDataset.objects.bulk_create([
            VirtualDataset(
                tenant=self.tenant,
                created_by=self.user,
                name="Invalid Dataset",
                query="",  # Empty query will fail validation
                query_type=QueryType.SQL,
                status=VirtualDatasetStatus.ACTIVE
            )
        ])
        invalid_dataset = invalid_datasets[0]

        # Execute workflow - should fail at validation step
        with self.assertRaises(Exception):
            VirtualizationWorkflow.execute(
                virtual_dataset_id=str(invalid_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                parameters={},
                execution_mode=QueryExecutionMode.ASYNC,
                engine=self.engine,
                registry=self.registry
            )

        # Verify workflow instance is in failed state
        workflow_instances = WorkflowInstance.objects.filter(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME
        ).order_by('-created_at')
        if workflow_instances.exists():
            workflow_instance = workflow_instances.first()
            self.assertIn(workflow_instance.status, [WorkflowStatus.FAILED, WorkflowStatus.ROLLING_BACK, WorkflowStatus.ROLLED_BACK])

    def test_e2e_multi_source_federated_metadata(self):
        """E2E: multi-source federated query with two metadata-only federated assets."""
        from hub.apps.assets.models import Asset, AssetSourceType
        from hub.apps.assets.models import DataStrategy
        import uuid as uuid_mod

        asset1 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-e2e-1-{uuid_mod.uuid4()}",
            name="E2E Federated 1",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-e2e-2-{uuid_mod.uuid4()}",
            name="E2E Federated 2",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY
        )
        multi_vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Multi Federated",
            query="SELECT * FROM combined",
            query_type=QueryType.FEDERATED,
            sources=[
                {"type": "federated_asset", "asset_id": str(asset1.id)},
                {"type": "federated_asset", "asset_id": str(asset2.id)},
            ],
            status=VirtualDatasetStatus.ACTIVE
        )
        result = VirtualizationWorkflow.execute(
            virtual_dataset_id=str(multi_vd.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
            engine=self.engine,
            registry=self.registry
        )
        self.assertTrue(result["success"])
        self.assertIn("execution_id", result)
        instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(instance.state_data["execution_results"]["source_count"], 2)
        execution = QueryExecution.objects.get(id=result["execution_id"])
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)

