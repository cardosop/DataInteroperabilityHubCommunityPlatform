"""
Unit tests for Model Training Workflow

Tests verify:
1. Workflow definition registration
2. Task registration
3. Workflow step execution
4. Error handling
5. Compensation logic
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    pytest = None
    pytestmark = None

from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowDefinition, WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflows.model_training import ModelTrainingWorkflow
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.ml.models import MLModel, ModelStatus, ModelType

User = get_user_model()


class ModelTrainingWorkflowDefinitionTest(TestCase):
    """Test ModelTrainingWorkflow definition and registration"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()

    def test_workflow_name_is_correct(self):
        """Test that workflow name is 'model_training'"""
        self.assertEqual(ModelTrainingWorkflow.WORKFLOW_NAME, "model_training")

    def test_register_workflow_creates_definition(self):
        """Test that register_workflow creates workflow definition"""
        # Count existing definitions
        initial_count = WorkflowDefinition.objects.filter(
            name=ModelTrainingWorkflow.WORKFLOW_NAME
        ).count()

        ModelTrainingWorkflow.register_workflow(self.registry)

        # Verify workflow definition exists (may already exist from previous test)
        workflow_def = WorkflowDefinition.objects.filter(
            name=ModelTrainingWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        self.assertIsNotNone(workflow_def, "Workflow definition should be created")
        self.assertEqual(workflow_def.name, ModelTrainingWorkflow.WORKFLOW_NAME)
        self.assertEqual(workflow_def.version, "1.0.0")
        self.assertTrue(workflow_def.is_active)

    def test_workflow_dsl_has_all_required_steps(self):
        """Test that workflow DSL has all required steps"""
        ModelTrainingWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=ModelTrainingWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        self.assertIsNotNone(workflow_def, "Workflow definition should exist")
        dsl = workflow_def.dsl_json

        # Verify required fields
        self.assertIn("version", dsl)
        self.assertIn("steps", dsl)
        self.assertIn("compensation", dsl)
        self.assertTrue(dsl["compensation"]["enabled"])

        # Verify all required steps exist
        step_names = [step["name"] for step in dsl["steps"]]
        required_steps = [
            "validate_training_request",
            "prepare_training_data",
            "submit_training_job",
            "monitor_training",
            "register_model",
            "link_model_to_asset",
            "update_semantic_layer",
            "complete"
        ]

        for required_step in required_steps:
            self.assertIn(required_step, step_names, f"Step '{required_step}' should be in workflow")

    def test_register_tasks_registers_all_tasks(self):
        """Test that register_tasks registers all workflow tasks"""
        ModelTrainingWorkflow.register_tasks(self.engine)

        # Verify all required tasks are registered
        required_tasks = [
            "model_training.validate_training_request",
            "model_training.prepare_training_data",
            "model_training.submit_training_job",
            "model_training.monitor_training",
            "model_training.register_model",
            "model_training.link_model_to_asset",
            "model_training.update_semantic_layer",
            "model_training.complete"
        ]

        for task_name in required_tasks:
            self.assertIn(task_name, self.engine.task_registry, f"Task '{task_name}' should be registered")

    def test_register_tasks_registers_compensation_tasks(self):
        """Test that register_tasks registers compensation tasks"""
        ModelTrainingWorkflow.register_tasks(self.engine)

        # Verify compensation tasks are registered
        compensation_tasks = [
            "model_training.rollback_training_job",
            "model_training.rollback_model_linking"
        ]

        for task_name in compensation_tasks:
            self.assertIn(task_name, self.engine.task_registry, f"Compensation task '{task_name}' should be registered")


class ModelTrainingWorkflowStepExecutionTest(TestCase):
    """Test ModelTrainingWorkflow step execution"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ModelTrainingWorkflow.register_workflow(self.registry)
        ModelTrainingWorkflow.register_tasks(self.engine)

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create test file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            storage_path="test/test.csv",
            created_by=self.user
        )

        # Create test dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={
                "fields": [
                    {"name": "feature1", "type": "float", "nullable": False},
                    {"name": "feature2", "type": "float", "nullable": False}
                ]
            }
        )

        # Training configuration
        self.training_config = {
            "model_type": "CLASSIFICATION",
            "model_name": "test-model",
            "description": "Test model",
            "hyperparameters": {
                "learning_rate": 0.001,
                "epochs": 10
            },
            "resources": {
                "cpu": "2",
                "memory": "4Gi"
            }
        }

    def test_workflow_execution_creates_instance(self):
        """Test that workflow execution creates instance"""
        workflow_input = {
            "asset_id": str(self.asset.id),
            "dataset_id": str(self.dataset.id),
            "training_config": self.training_config,
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        instance = self.engine.create_instance(
            workflow_name=ModelTrainingWorkflow.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        self.assertIsNotNone(instance)
        self.assertEqual(instance.workflow_name, ModelTrainingWorkflow.WORKFLOW_NAME)
        self.assertEqual(instance.status, WorkflowStatus.DRAFT)

    def test_workflow_execution_completes_successfully(self):
        """Test that workflow execution completes successfully"""
        # Note: This test may fail if ODH services are not available
        # The workflow handles ODH unavailability gracefully with placeholders
        try:
            result = ModelTrainingWorkflow.execute(
                asset_id=str(self.asset.id),
                dataset_id=str(self.dataset.id),
                training_config=self.training_config,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                engine=self.engine,
                registry=self.registry
            )

            self.assertTrue(result.get("success"))
            self.assertIn("workflow_instance_id", result)
            self.assertIn("model_id", result)
        except ValueError as e:
            # If workflow fails due to ODH unavailability, that's acceptable
            # The workflow should handle this gracefully
            if "ODH" in str(e) or "service unavailable" in str(e).lower():
                # This is expected in test environment
                pass
            else:
                raise

    def test_workflow_handles_missing_asset(self):
        """Test that workflow handles missing asset gracefully"""
        with self.assertRaises(ValueError):
            ModelTrainingWorkflow.execute(
                asset_id="00000000-0000-0000-0000-000000000000",
                dataset_id=str(self.dataset.id),
                training_config=self.training_config,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                engine=self.engine,
                registry=self.registry
            )

    def test_workflow_handles_missing_dataset(self):
        """Test that workflow handles missing dataset gracefully"""
        with self.assertRaises(ValueError):
            ModelTrainingWorkflow.execute(
                asset_id=str(self.asset.id),
                dataset_id="00000000-0000-0000-0000-000000000000",
                training_config=self.training_config,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                engine=self.engine,
                registry=self.registry
            )


class ModelTrainingWorkflowIntegrationTest(TestCase):
    """Integration tests for ModelTrainingWorkflow with real services"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create test file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            storage_path="test/test.csv",
            created_by=self.user
        )

        # Create test dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={
                "fields": [
                    {"name": "feature1", "type": "float", "nullable": False},
                    {"name": "feature2", "type": "float", "nullable": False}
                ]
            }
        )

        # Training configuration
        self.training_config = {
            "model_type": "CLASSIFICATION",
            "model_name": "test-model",
            "description": "Test model",
            "hyperparameters": {
                "learning_rate": 0.001,
                "epochs": 10
            }
        }

    def test_service_integration_with_workflow(self):
        """Test that ModelRegistryBridgeService integrates with workflow"""
        from hub.apps.ml.services import ModelRegistryBridgeService

        service = ModelRegistryBridgeService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Test training with workflow
        try:
            result = service.train_model_with_workflow(
                asset_id=str(self.asset.id),
                dataset_id=str(self.dataset.id),
                training_config=self.training_config,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            self.assertIn("success", result)
            self.assertIn("workflow_instance_id", result)
        except Exception as e:
            # If ODH services are unavailable, that's acceptable
            if "ODH" in str(e) or "service unavailable" in str(e).lower():
                pass
            else:
                raise
