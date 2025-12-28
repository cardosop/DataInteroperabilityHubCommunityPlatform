"""
Unit tests for Virtualization Query Execution Workflow

Comprehensive tests without mocks/stubs, following engineering best practices.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
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


class VirtualizationWorkflowUnitTest(TestCase):
    """Unit tests for virtualization query execution workflow tasks"""

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

    def test_validate_query_task(self):
        """Test query validation task"""
        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_query",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._validate_query_task(
            input_data, instance, step
        )

        self.assertIn("validation_status", result)
        self.assertEqual(result["validation_status"], "VALID")
        self.assertIn("virtual_dataset_id", instance.state_data)
        self.assertEqual(instance.state_data["virtual_dataset_id"], str(self.virtual_dataset.id))
        self.assertEqual(instance.state_data["progress_percentage"], 10)

    def test_validate_query_task_invalid_query(self):
        """Test query validation with invalid query"""
        # Create virtual dataset with invalid query using bulk_create to bypass validation
        invalid_datasets = VirtualDataset.objects.bulk_create([
            VirtualDataset(
                tenant=self.tenant,
                created_by=self.user,
                name="Invalid Dataset",
                query="",  # Empty query
                query_type=QueryType.SQL,
                status=VirtualDatasetStatus.ACTIVE
            )
        ])
        invalid_dataset = invalid_datasets[0]

        input_data = {
            "virtual_dataset_id": str(invalid_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_query",
            step_type="task",
            status=StepStatus.PENDING
        )

        # Validation should fail
        with self.assertRaises(Exception):
            VirtualizationWorkflow._validate_query_task(
                input_data, instance, step
            )

    def test_validate_sources_task(self):
        """Test source compatibility validation task"""
        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["virtual_dataset_id"] = str(self.virtual_dataset.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="validate_sources",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._validate_sources_task(
            input_data, instance, step
        )

        self.assertIn("compatibility_status", result)
        self.assertIn("virtual_dataset_id", instance.state_data)
        self.assertEqual(instance.state_data["progress_percentage"], 20)

    def test_optimize_query_task(self):
        """Test query optimization task"""
        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["virtual_dataset_id"] = str(self.virtual_dataset.id)
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="optimize_query",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._optimize_query_task(
            input_data, instance, step
        )

        self.assertIn("optimized_query", result)
        self.assertIn("optimizations_applied", result)
        self.assertIn("optimized_query", instance.state_data)
        self.assertEqual(instance.state_data["progress_percentage"], 30)

    def test_aggregate_results_task(self):
        """Test result aggregation task"""
        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["execution_results"] = {
            "data": [{"id": 1, "name": "Test"}],
            "row_count": 1,
            "columns": ["id", "name"]
        }
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=4,
            step_name="aggregate_results",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._aggregate_results_task(
            input_data, instance, step
        )

        self.assertIn("aggregated_results", result)
        self.assertIn("row_count", result)
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(instance.state_data["progress_percentage"], 70)

    def test_cache_results_task(self):
        """Test result caching task"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
            status=QueryExecutionStatus.RUNNING
        )

        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "parameters": {}
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["execution_id"] = str(execution.id)
        instance.state_data["virtual_dataset_id"] = str(self.virtual_dataset.id)
        instance.state_data["aggregated_results"] = {
            "data": [{"id": 1, "name": "Test"}],
            "row_count": 1,
            "columns": ["id", "name"]
        }
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=5,
            step_name="cache_results",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._cache_results_task(
            input_data, instance, step
        )

        self.assertIn("cache_status", result)
        self.assertIn("cache_key", instance.state_data)
        self.assertEqual(instance.state_data["progress_percentage"], 85)

        # Verify cache entry exists
        cache_key = instance.state_data.get("cache_key")
        if cache_key:
            cached_data = cache.get(cache_key)
            self.assertIsNotNone(cached_data)

    def test_store_results_task(self):
        """Test result storage task"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
            status=QueryExecutionStatus.RUNNING
        )

        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["execution_id"] = str(execution.id)
        instance.state_data["aggregated_results"] = {
            "data": [{"id": 1, "name": "Test"}],
            "row_count": 1,
            "columns": ["id", "name"]
        }
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=6,
            step_name="store_results",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._store_results_task(
            input_data, instance, step
        )

        self.assertIn("storage_status", result)
        self.assertEqual(instance.state_data["progress_percentage"], 95)

    def test_complete_task(self):
        """Test workflow completion task"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
            status=QueryExecutionStatus.RUNNING,
            started_at=timezone.now()
        )

        input_data = {
            "virtual_dataset_id": str(self.virtual_dataset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["execution_id"] = str(execution.id)
        instance.state_data["execution_results"] = {
            "data": [{"id": 1, "name": "Test"}],
            "row_count": 1,
            "columns": ["id", "name"]
        }
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=7,
            step_name="complete",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._complete_task(
            input_data, instance, step
        )

        self.assertIn("completed", result)
        self.assertTrue(result["completed"])
        self.assertEqual(instance.state_data["progress_percentage"], 100)

        # Verify execution is marked as completed
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)

    def test_rollback_execution_task(self):
        """Test execution rollback compensation task"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
            status=QueryExecutionStatus.RUNNING
        )

        input_data = {
            "tenant_id": str(self.tenant.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
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

        result = VirtualizationWorkflow._rollback_execution_task(
            input_data, instance, step
        )

        self.assertIn("rolled_back", result)
        self.assertTrue(result["rolled_back"])

        # Verify execution is marked as failed
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.FAILED)

    def test_rollback_cache_task(self):
        """Test cache rollback compensation task"""
        input_data = {
            "tenant_id": str(self.tenant.id)
        }
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        # Create a cache entry
        cache_key = "test_cache_key"
        cache.set(cache_key, {"data": "test"}, timeout=3600)
        instance.state_data["cache_key"] = cache_key
        instance.save()

        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="rollback_cache",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = VirtualizationWorkflow._rollback_cache_task(
            input_data, instance, step
        )

        self.assertIn("rolled_back", result)
        self.assertTrue(result["rolled_back"])

        # Verify cache entry is deleted
        cached_data = cache.get(cache_key)
        self.assertIsNone(cached_data)

    def test_update_progress(self):
        """Test progress update method"""
        instance = self.engine.create_instance(
            workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
            input_data={"virtual_dataset_id": str(self.virtual_dataset.id)},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        VirtualizationWorkflow._update_progress(instance, 50, "test_step")

        instance.refresh_from_db()
        self.assertEqual(instance.state_data["progress_percentage"], 50)
        self.assertEqual(instance.state_data["current_step"], "test_step")

    def test_workflow_registration(self):
        """Test workflow registration"""
        registry = WorkflowRegistry()

        # Check if workflow already exists and delete it first
        try:
            existing = registry.get_workflow(VirtualizationWorkflow.WORKFLOW_NAME)
            if existing:
                # Delete existing workflow definition
                from hub.apps.orchestration.models import WorkflowDefinition
                WorkflowDefinition.objects.filter(
                    name=VirtualizationWorkflow.WORKFLOW_NAME,
                    version=VirtualizationWorkflow.WORKFLOW_VERSION
                ).delete()
        except Exception:
            pass  # Workflow doesn't exist, which is fine

        VirtualizationWorkflow.register_workflow(registry)

        # Verify workflow is registered
        workflow_def = registry.get_workflow(VirtualizationWorkflow.WORKFLOW_NAME)
        self.assertIsNotNone(workflow_def)
        if workflow_def:
            # get_workflow returns a WorkflowDefinition model instance, not a dict
            if hasattr(workflow_def, 'version'):
                self.assertEqual(workflow_def.version, VirtualizationWorkflow.WORKFLOW_VERSION)
            elif isinstance(workflow_def, dict):
                self.assertEqual(workflow_def.get("version"), VirtualizationWorkflow.WORKFLOW_VERSION)

    def test_task_registration(self):
        """Test task registration"""
        engine = WorkflowEngine()
        VirtualizationWorkflow.register_tasks(engine)

        # Verify tasks are registered
        self.assertIn("virtualization.validate_query", engine.task_registry)
        self.assertIn("virtualization.validate_sources", engine.task_registry)
        self.assertIn("virtualization.optimize_query", engine.task_registry)
        self.assertIn("virtualization.execute_query", engine.task_registry)
        self.assertIn("virtualization.aggregate_results", engine.task_registry)
        self.assertIn("virtualization.cache_results", engine.task_registry)
        self.assertIn("virtualization.store_results", engine.task_registry)
        self.assertIn("virtualization.complete", engine.task_registry)
        self.assertIn("virtualization.rollback_execution", engine.task_registry)
        self.assertIn("virtualization.rollback_cache", engine.task_registry)

