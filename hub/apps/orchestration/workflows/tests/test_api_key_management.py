"""
Unit and Integration tests for API Key Management Workflow

Tests verify:
1. Workflow definition registration
2. Task registration
3. Workflow step execution (creation and revocation)
4. Error handling
5. Compensation logic
6. Integration with services
7. E2E workflow execution
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    pytest = None
    pytestmark = None

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowDefinition, WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflows.api_key_management import APIKeyManagementWorkflow
from hub.apps.auth.models import APIKey as AuthAPIKey
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, Role, UserRole
from hub.apps.baas.models import APITierModel
from hub.apps.baas.services import UsageTrackingService

User = get_user_model()


class APIKeyManagementWorkflowDefinitionTest(TestCase):
    """Test APIKeyManagementWorkflow definition and registration"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()

    def test_workflow_name_is_correct(self):
        """Test that workflow name is 'api_key_management'"""
        self.assertEqual(APIKeyManagementWorkflow.WORKFLOW_NAME, "api_key_management")

    def test_workflow_version_is_correct(self):
        """Test that workflow version is '1.0.0'"""
        self.assertEqual(APIKeyManagementWorkflow.WORKFLOW_VERSION, "1.0.0")

    def test_register_workflow_creates_definition(self):
        """Test that register_workflow creates workflow definition"""
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        self.assertIsNotNone(workflow_def, "Workflow definition should be created")
        self.assertEqual(workflow_def.name, APIKeyManagementWorkflow.WORKFLOW_NAME)
        self.assertEqual(workflow_def.version, APIKeyManagementWorkflow.WORKFLOW_VERSION)
        self.assertTrue(workflow_def.is_active)

    def test_workflow_dsl_has_all_required_steps(self):
        """Test that workflow DSL has all required steps"""
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        self.assertIsNotNone(workflow_def)
        dsl = workflow_def.dsl_json

        # Verify required fields
        self.assertIn("version", dsl)
        self.assertIn("steps", dsl)
        self.assertIn("compensation", dsl)
        self.assertTrue(dsl["compensation"]["enabled"])

        # Verify all required steps exist
        step_names = [step["name"] for step in dsl["steps"]]
        required_steps = [
            "validate_request",
            "check_permissions",
            "check_quota",
            "generate_key",
            "store_key",
            "validate_revocation",
            "revoke_key",
            "notify_user",
            "complete"
        ]

        for required_step in required_steps:
            self.assertIn(required_step, step_names, f"Step '{required_step}' should be in workflow")

    def test_register_tasks_registers_all_tasks(self):
        """Test that register_tasks registers all workflow tasks"""
        APIKeyManagementWorkflow.register_tasks(self.engine)

        # Check that tasks are registered
        self.assertIn("api_key_management.validate_request", self.engine.task_registry)
        self.assertIn("api_key_management.check_permissions", self.engine.task_registry)
        self.assertIn("api_key_management.check_quota", self.engine.task_registry)
        self.assertIn("api_key_management.generate_key", self.engine.task_registry)
        self.assertIn("api_key_management.store_key", self.engine.task_registry)
        self.assertIn("api_key_management.notify_user", self.engine.task_registry)
        self.assertIn("api_key_management.complete", self.engine.task_registry)
        self.assertIn("api_key_management.validate_revocation", self.engine.task_registry)
        self.assertIn("api_key_management.revoke_key", self.engine.task_registry)

    def test_register_tasks_registers_compensation_tasks(self):
        """Test that register_tasks registers compensation tasks"""
        APIKeyManagementWorkflow.register_tasks(self.engine)

        # Check that compensation tasks are registered
        self.assertIn("api_key_management.rollback_key_generation", self.engine.task_registry)
        self.assertIn("api_key_management.rollback_key_revocation", self.engine.task_registry)


class APIKeyManagementWorkflowStepExecutionTest(TestCase):
    """Test API key management workflow step execution"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()

        # Register workflow and tasks
        APIKeyManagementWorkflow.register_workflow(self.registry)
        APIKeyManagementWorkflow.register_tasks(self.engine)

        # Create test tenant and user
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create TENANT_ADMIN role (required for API key creation)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Assign TENANT_ADMIN role to user
        UserRole.objects.get_or_create(user=self.user, role=self.admin_role)

        # Create API tier
        self.tier = APITierModel.objects.create(
            name="FREE",
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            max_requests_per_month=100000
        )

    def test_validate_request_task_success(self):
        """Test validate_request task with valid input"""
        input_data = {
            "operation": "create",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "name": "Test API Key",
            "tier": "FREE",
            "expires_at": None
        }

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT
        )

        # Create mock step object (like product_creation tests)
        step = type('Step', (), {"name": "validate_request"})()

        result = APIKeyManagementWorkflow._validate_request_task(input_data, instance, step)

        self.assertTrue(result.get("validated"))
        self.assertEqual(result["state"]["tenant_id"], str(self.tenant.id))
        self.assertEqual(result["state"]["user_id"], str(self.user.id))
        self.assertEqual(result["state"]["name"], "Test API Key")

    def test_validate_request_task_missing_required_fields(self):
        """Test validate_request task with missing required fields"""
        input_data = {
            "operation": "create",
            "tenant_id": str(self.tenant.id),
            # Missing user_id and name
        }

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT
        )

        # Create mock step object
        step = type('Step', (), {"name": "validate_request"})()

        with self.assertRaises(ValueError):
            APIKeyManagementWorkflow._validate_request_task(input_data, instance, step)

    def test_generate_key_task_success(self):
        """Test generate_key task generates secure key"""
        input_data = {
            "operation": "create"
        }

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={"operation": "create"}
        )

        # Create mock step object
        step = type('Step', (), {"name": "generate_key"})()

        result = APIKeyManagementWorkflow._generate_key_task(input_data, instance, step)

        self.assertIn("plaintext_key", result["state"])
        self.assertIn("key_hash", result["state"])
        self.assertEqual(len(result["state"]["plaintext_key"]), 43)  # URL-safe base64 without padding
        self.assertEqual(len(result["state"]["key_hash"]), 64)  # SHA-256 hex digest

    def test_store_key_task_success(self):
        """Test store_key task stores API key in database"""
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data={"operation": "create"},
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={
                "operation": "create",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "name": "Test API Key",
                "tier_id": str(self.tier.id),
                "key_hash": key_hash,
                "expires_at": None
            }
        )

        # Create mock step object
        step = type('Step', (), {"name": "store_key"})()

        result = APIKeyManagementWorkflow._store_key_task({}, instance, step)

        self.assertIn("api_key_id", result["state"])

        # Verify auth API key was created (single identity D2)
        api_key = AuthAPIKey.objects.get(id=result["state"]["api_key_id"])
        self.assertEqual(api_key.name, "Test API Key")
        self.assertEqual(api_key.key_hash, key_hash)
        self.assertEqual(api_key.tenant, self.tenant)
        self.assertEqual(api_key.user, self.user)

    def test_validate_revocation_task_success(self):
        """Test validate_revocation task with valid API key (auth APIKey — D2)"""
        # Create auth API key first
        api_key = AuthAuthAPIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            tier=self.tier,
            name="Test API Key",
            key_hash=AuthAPIKey.hash_key(AuthAPIKey.generate_key())
        )

        input_data = {
            "operation": "revoke",
            "api_key_id": str(api_key.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT
        )

        # Create mock step object
        step = type('Step', (), {"name": "validate_revocation"})()

        result = APIKeyManagementWorkflow._validate_revocation_task(input_data, instance, step)

        self.assertTrue(result.get("validated"))
        self.assertEqual(result["state"]["api_key_id"], str(api_key.id))

    def test_revoke_key_task_success(self):
        """Test revoke_key task revokes API key (auth APIKey — D2)"""
        # Create auth API key first
        api_key = AuthAuthAPIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            tier=self.tier,
            name="Test API Key",
            key_hash=AuthAPIKey.hash_key(AuthAPIKey.generate_key())
        )

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data={"operation": "revoke"},
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={
                "operation": "revoke",
                "api_key_id": str(api_key.id)
            }
        )

        # Create mock step object
        step = type('Step', (), {"name": "revoke_key"})()

        result = APIKeyManagementWorkflow._revoke_key_task({}, instance, step)

        self.assertTrue(result.get("revoked"))

        # Verify API key was revoked
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)


class APIKeyManagementWorkflowCompensationTest(TestCase):
    """Test API key management workflow compensation logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()

        APIKeyManagementWorkflow.register_workflow(self.registry)
        APIKeyManagementWorkflow.register_tasks(self.engine)

        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create TENANT_ADMIN role (required for API key creation)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Assign TENANT_ADMIN role to user
        UserRole.objects.get_or_create(user=self.user, role=self.admin_role)

        self.tier = APITierModel.objects.create(
            name="FREE",
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            max_requests_per_month=100000
        )

    def test_rollback_key_generation_deletes_key(self):
        """Test rollback_key_generation deletes created API key"""
        # Create API key
        api_key = AuthAPIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            tier=self.tier,
            name="Test API Key",
            key_hash=AuthAPIKey.hash_key(AuthAPIKey.generate_key())
        )

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data={},
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={"api_key_id": str(api_key.id)}
        )

        # Create mock step object
        step = type('Step', (), {"name": "rollback_key_generation"})()

        result = APIKeyManagementWorkflow._rollback_key_generation_task({}, instance, step)

        self.assertTrue(result.get("rolled_back"))

        # Verify API key was deleted
        self.assertFalse(APIKey.objects.filter(id=api_key.id).exists())

    def test_rollback_key_revocation_restores_key(self):
        """Test rollback_key_revocation restores revoked key"""
        # Create and revoke API key
        api_key = AuthAPIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            tier=self.tier,
            name="Test API Key",
            key_hash=AuthAPIKey.hash_key(AuthAPIKey.generate_key())
        )
        api_key.revoke()

        # Register workflow first
        APIKeyManagementWorkflow.register_workflow(self.registry)

        workflow_def = WorkflowDefinition.objects.filter(
            name=APIKeyManagementWorkflow.WORKFLOW_NAME
        ).order_by('-created_at').first()

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            workflow_version=APIKeyManagementWorkflow.WORKFLOW_VERSION,
            tenant=self.tenant,
            input_data={},
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={"api_key_id": str(api_key.id)}
        )

        # Create mock step object
        step = type('Step', (), {"name": "rollback_key_revocation"})()

        result = APIKeyManagementWorkflow._rollback_key_revocation_task({}, instance, step)

        self.assertTrue(result.get("rolled_back"))

        # Verify API key was restored
        api_key.refresh_from_db()
        self.assertIsNone(api_key.revoked_at)


class APIKeyManagementWorkflowIntegrationTest(TestCase):
    """Integration tests for API key management workflow"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()

        APIKeyManagementWorkflow.register_workflow(self.registry)
        APIKeyManagementWorkflow.register_tasks(self.engine)

        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create TENANT_ADMIN role (required for API key creation)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Assign TENANT_ADMIN role to user
        UserRole.objects.get_or_create(user=self.user, role=self.admin_role)

        self.tier = APITierModel.objects.create(
            name="FREE",
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            max_requests_per_month=100000
        )

    def test_create_api_key_workflow_complete(self):
        """Test complete API key creation workflow"""
        input_data = {
            "operation": "create",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "name": "Test API Key",
            "tier": "FREE",
            "expires_at": None
        }

        instance = self.engine.create_instance(
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        # Initialize state_data
        instance.state_data = input_data.copy()
        instance.save(update_fields=['state_data'])

        # Start and execute workflow
        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Check workflow completed
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify API key was created
        api_key_id = instance.state_data.get("api_key_id")
        self.assertIsNotNone(api_key_id)

        api_key = AuthAPIKey.objects.get(id=api_key_id)
        self.assertEqual(api_key.name, "Test API Key")
        self.assertEqual(api_key.tenant, self.tenant)
        self.assertEqual(api_key.user, self.user)

    def test_revoke_api_key_workflow_complete(self):
        """Test complete API key revocation workflow"""
        # Create API key first
        api_key = AuthAPIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            tier=self.tier,
            name="Test API Key",
            key_hash=AuthAPIKey.hash_key(AuthAPIKey.generate_key())
        )

        input_data = {
            "operation": "revoke",
            "api_key_id": str(api_key.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        instance = self.engine.create_instance(
            workflow_name=APIKeyManagementWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        # Initialize state_data
        instance.state_data = input_data.copy()
        instance.save(update_fields=['state_data'])

        # Start and execute workflow
        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Check workflow completed
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify API key was revoked
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)


class APIKeyManagementWorkflowE2ETest(TestCase):
    """E2E tests for API key management workflow with service integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create TENANT_ADMIN role (required for API key creation)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Assign TENANT_ADMIN role to user
        UserRole.objects.get_or_create(user=self.user, role=self.admin_role)

        self.tier = APITierModel.objects.create(
            name="FREE",
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            max_requests_per_month=100000
        )

    def test_service_create_api_key_with_workflow(self):
        """Test UsageTrackingService.create_api_key_with_workflow"""
        service = UsageTrackingService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = service.create_api_key_with_workflow(
            name="Test API Key",
            tier_name="FREE",
            expires_at=None,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        self.assertIn("api_key_id", result)
        self.assertIn("plaintext_key", result)
        self.assertIn("workflow_instance_id", result)

        # Verify API key was created
        api_key = AuthAPIKey.objects.get(id=result["api_key_id"])
        self.assertEqual(api_key.name, "Test API Key")
        self.assertEqual(api_key.tenant, self.tenant)
        self.assertEqual(api_key.user, self.user)

    def test_service_revoke_api_key_with_workflow(self):
        """Test UsageTrackingService.revoke_api_key_with_workflow"""
        # Create API key first
        api_key = AuthAPIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            tier=self.tier,
            name="Test API Key",
            key_hash=AuthAPIKey.hash_key(AuthAPIKey.generate_key())
        )

        service = UsageTrackingService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = service.revoke_api_key_with_workflow(
            api_key_id=str(api_key.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        self.assertIn("api_key_id", result)
        self.assertIn("workflow_instance_id", result)

        # Verify API key was revoked
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)
