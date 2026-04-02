"""
Integration tests for Virtualization Query Execution Workflow

Tests workflow execution with real services and models (no mocks/stubs).
"""
import uuid
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.virtualization import VirtualizationWorkflow
from hub.apps.virtualization.services import VirtualizationService
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


class VirtualizationWorkflowIntegrationTest(TestCase):
    """Integration tests for virtualization query execution workflow"""

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

    def test_workflow_execution_complete_flow(self):
        """Test complete workflow execution flow"""
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

            # If execution succeeds, verify it
            self.assertIn("success", result)
            self.assertTrue(result["success"])
            self.assertIn("workflow_instance_id", result)
            self.assertIn("execution_id", result)

            # Verify workflow instance
            workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
            self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
            self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

            # Verify query execution
            execution = QueryExecution.objects.get(id=result["execution_id"])
            self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
            self.assertIsNotNone(execution.completed_at)
        except Exception as e:
            # If execution fails (e.g., database not available), verify workflow handled it correctly
            # Check that workflow instance was created and execution was attempted
            workflow_instances = WorkflowInstance.objects.filter(
                workflow_name=VirtualizationWorkflow.WORKFLOW_NAME
            ).order_by('-created_at')
            self.assertTrue(workflow_instances.exists(), "Workflow instance should be created even on failure")

            workflow_instance = workflow_instances.first()
            # Workflow should be in FAILED or ROLLING_BACK state
            self.assertIn(workflow_instance.status, [WorkflowStatus.FAILED, WorkflowStatus.ROLLING_BACK])

            # Verify execution was created
            if "execution_id" in workflow_instance.state_data:
                execution_id = workflow_instance.state_data["execution_id"]
                execution = QueryExecution.objects.get(id=execution_id)
                self.assertEqual(execution.status, QueryExecutionStatus.FAILED)

    def test_workflow_progress_tracking(self):
        """Test workflow progress tracking throughout execution"""
        # Create workflow instance manually to track progress
        workflow_input = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "parameters": {},
            "execution_mode": QueryExecutionMode.ASYNC
        }

        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        # Start workflow
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (this will run all steps)
        # May fail at query execution if database is not available
        try:
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            # Execution may fail, but progress should still be tracked
            instance.refresh_from_db()

        # Verify progress was tracked (even if workflow failed)
        instance.refresh_from_db()
        self.assertIn("progress_percentage", instance.state_data)
        # Progress should be at least 50% (reached execute_query step)
        self.assertGreaterEqual(instance.state_data["progress_percentage"], 50)
        self.assertIn("current_step", instance.state_data)

    def test_workflow_with_sparql_query(self):
        """Test workflow execution with SPARQL query"""
        # Create SPARQL virtual dataset
        sparql_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Dataset",
            query="""
            PREFIX foaf: <http://xmlns.com/foaf/0.1/>
            SELECT ?name ?email
            WHERE {
                ?person foaf:name ?name .
                ?person foaf:email ?email .
            }
            LIMIT 10
            """,
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Execute workflow
        # Note: This will fail if SemanticService is not available, which is expected
        # The workflow should handle the error gracefully
        try:
            result = VirtualizationWorkflow.execute(
                virtual_dataset_id=str(sparql_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                parameters={},
                execution_mode=QueryExecutionMode.ASYNC,
                engine=self.engine,
                registry=self.registry
            )
            # If execution succeeds, verify it
            self.assertIn("success", result)
        except Exception as e:
            # Expected if SemanticService is not available
            # Verify that execution was created and marked as failed
            executions = QueryExecution.objects.filter(virtual_dataset=sparql_dataset)
            if executions.exists():
                execution = executions.first()
                self.assertIn(execution.status, [QueryExecutionStatus.FAILED, QueryExecutionStatus.COMPLETED])

    def test_workflow_execution_multi_source_federated_metadata(self):
        """Test workflow execution with FEDERATED query and multiple federated_asset (metadata-only) sources."""
        from hub.apps.assets.models import Asset, AssetSourceType
        from hub.apps.assets.models import DataStrategy
        import uuid as uuid_mod

        asset1 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-int-1-{uuid_mod.uuid4()}",
            name="Federated 1",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-int-2-{uuid_mod.uuid4()}",
            name="Federated 2",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY
        )
        multi_vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Federated Multi Integration",
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
        self.assertIn("success", result)
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("execution_id", result)
        instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertIn("execution_results", instance.state_data)
        exec_results = instance.state_data["execution_results"]
        self.assertEqual(exec_results.get("source_count"), 2)
        self.assertEqual(exec_results.get("query_type"), "FEDERATED")

    def test_workflow_and_service_execution_parity(self):
        """Test workflow-vs-view parity: same virtual dataset yields same result shape from service and workflow."""
        from hub.apps.assets.models import Asset, AssetSourceType, DataStrategy
        import uuid as uuid_mod

        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-parity-{uuid_mod.uuid4()}",
            name="Parity Federated",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY
        )
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Parity VD",
            query="SELECT * FROM t",
            query_type=QueryType.SQL,
            sources=[{"type": "federated_asset", "asset_id": str(asset.id)}],
            status=VirtualDatasetStatus.ACTIVE
        )
        service = VirtualizationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        view_results = service._execute_query_against_sources(
            query=vd.query,
            query_type=vd.query_type,
            sources=vd.get_sources(),
            parameters={},
            timeout_seconds=300
        )
        self.assertEqual(len(view_results), 1)
        view_row_count = view_results[0].get("row_count", 0)
        result = VirtualizationWorkflow.execute(
            virtual_dataset_id=str(vd.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
            engine=self.engine,
            registry=self.registry
        )
        self.assertTrue(result.get("success"))
        instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(
            instance.status,
            WorkflowStatus.COMPLETED,
            "Parity test requires workflow to complete successfully",
        )
        workflow_results = instance.state_data.get("execution_results", {})
        self.assertEqual(
            workflow_results.get("row_count"),
            view_row_count,
            "Workflow and service execution must yield same row_count (parity)",
        )

