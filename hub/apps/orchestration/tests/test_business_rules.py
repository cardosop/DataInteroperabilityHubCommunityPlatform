"""
Unit tests for Orchestration Business Rules

Tests for orchestration business rules validation, including:
- OrchestrationBusinessRules initialization
- Rule registration in business rules registry
- OrchestrationRuleExecutionContext
"""

import uuid

from django.test import TestCase

from hub.apps.core.business_rules.registry import get_registry
from hub.apps.orchestration.business_rules import (
    OrchestrationBusinessRules,
    OrchestrationRuleExecutionContext,
)
from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


class OrchestrationBusinessRulesInitializationTest(TestCase):
    """Test OrchestrationBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_orchestration_business_rules_initialization_with_tenant_and_user(self):
        """Test OrchestrationBusinessRules initialization with tenant and user"""
        rules = OrchestrationBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))
        self.assertTrue(rules.enable_caching)
        self.assertTrue(rules.enable_metrics)
        self.assertTrue(rules.enable_tracing)
        self.assertTrue(rules.enable_logging)

    def test_orchestration_business_rules_initialization_without_tenant(self):
        """Test OrchestrationBusinessRules initialization without tenant"""
        rules = OrchestrationBusinessRules(user_id=str(self.user.id))
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_orchestration_business_rules_initialization_without_user(self):
        """Test OrchestrationBusinessRules initialization without user"""
        rules = OrchestrationBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_orchestration_business_rules_initialization_without_tenant_and_user(self):
        """Test OrchestrationBusinessRules initialization without tenant and user"""
        rules = OrchestrationBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_orchestration_business_rules_get_rule_name(self):
        """Test OrchestrationBusinessRules get_rule_name method"""
        rules = OrchestrationBusinessRules()
        self.assertEqual(rules.get_rule_name(), "OrchestrationBusinessRules")


class OrchestrationBusinessRulesRegistrationTest(TestCase):
    """Test OrchestrationBusinessRules registration in business rules registry"""

    def test_orchestration_business_rules_registered(self):
        """Test OrchestrationBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("orchestration_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "orchestration_validation")
        self.assertEqual(rule.rule_class, OrchestrationBusinessRules)
        self.assertIn("orchestration", rule.tags)
        self.assertIn("validation", rule.tags)
        self.assertIn("workflow", rule.tags)
        self.assertIn("step", rule.tags)

    def test_orchestration_business_rules_priority(self):
        """Test OrchestrationBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("orchestration_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)

    def test_orchestration_business_rules_description(self):
        """Test OrchestrationBusinessRules has correct description"""
        registry = get_registry()
        rule = registry.get_rule("orchestration_validation")
        self.assertIsNotNone(rule)
        self.assertIn("workflow", rule.description.lower())
        self.assertIn("validates", rule.description.lower())


class OrchestrationRuleExecutionContextTest(TestCase):
    """Test OrchestrationRuleExecutionContext"""

    def setUp(self):
        """Set up test fixtures"""
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Create workflow definition
        self.wf_name = f"test_workflow_{self.uid}"
        self.workflow_definition = WorkflowDefinition.objects.create(
            name=self.wf_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "test_step", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )
        # Create workflow instance
        self.workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_definition,
            workflow_name=self.wf_name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )
        # Create workflow step
        self.step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="test_step",
            step_type="task",
            status=StepStatus.PENDING,
        )

    def test_orchestration_rule_execution_context_creation(self):
        """Test OrchestrationRuleExecutionContext creation and behavior"""
        context = OrchestrationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            workflow=self.workflow,
            step=self.step,
            workflow_definition=self.workflow_definition,
            tenant=self.tenant,
            user=self.user,
        )
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.workflow, self.workflow)
        self.assertEqual(context.step, self.step)
        self.assertEqual(context.workflow_definition, self.workflow_definition)
        self.assertEqual(context.tenant, self.tenant)
        self.assertEqual(context.user, self.user)

        # Verify behavior: to_dict() produces a dict with the expected keys
        context_dict = context.to_dict()
        self.assertIsInstance(context_dict, dict)
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["workflow_id"], str(self.workflow.id))
        self.assertEqual(context_dict["step_name"], self.step.step_name)

    def test_orchestration_rule_execution_context_to_dict(self):
        """Test OrchestrationRuleExecutionContext to_dict method"""
        context = OrchestrationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            workflow=self.workflow,
            step=self.step,
            workflow_definition=self.workflow_definition,
            tenant=self.tenant,
            user=self.user,
        )
        context_dict = context.to_dict()
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        self.assertEqual(context_dict["workflow_id"], str(self.workflow.id))
        self.assertEqual(context_dict["workflow_name"], self.workflow.workflow_name)
        self.assertEqual(context_dict["workflow_status"], self.workflow.status)
        self.assertEqual(context_dict["workflow_version"], self.workflow.workflow_version)
        self.assertEqual(context_dict["step_id"], str(self.step.id))
        self.assertEqual(context_dict["step_name"], self.step.step_name)
        self.assertEqual(context_dict["step_status"], self.step.status)
        self.assertEqual(context_dict["step_index"], self.step.step_index)
        self.assertEqual(context_dict["workflow_definition_id"], str(self.workflow_definition.id))
        self.assertEqual(context_dict["tenant_id_from_object"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id_from_object"], str(self.user.id))


class WorkflowDefinitionValidationTest(TestCase):
    """Test comprehensive workflow definition validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = OrchestrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_workflow_structure_valid(self):
        """Test workflow structure validation with valid workflow"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_structure(workflow_def)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("dsl_valid", False))
        # Verify structure_validation is present and truthy (valid structure was checked)
        self.assertIn("structure_validation", result.details)
        self.assertTrue(
            result.details["structure_validation"],
            f"structure_validation should be truthy, got: {result.details.get('structure_validation')}",
        )

    def test_validate_workflow_structure_missing_name(self):
        """Test workflow structure validation with missing name"""
        workflow_def = WorkflowDefinition(
            name="",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )
        result = self.rules._validate_workflow_structure(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_structure_invalid_dsl(self):
        """Test workflow structure validation with invalid DSL"""
        workflow_def = WorkflowDefinition(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                # Missing steps field
            },
        )
        result = self.rules._validate_workflow_structure(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_structure_empty_steps(self):
        """Test workflow structure validation with empty steps"""
        workflow_def = WorkflowDefinition(
            name="test_workflow", version="1.0.0", dsl_json={"version": "1.0.0", "steps": []}
        )
        result = self.rules._validate_workflow_structure(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_steps_valid(self):
        """Test workflow step validation with valid steps"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task2"},
                ],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_steps(workflow_def)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("steps_valid", False))
        self.assertEqual(result.details.get("steps_count"), 2)

    def test_validate_workflow_steps_duplicate_names(self):
        """Test workflow step validation with duplicate step names"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {
                        "name": "step1",  # Duplicate
                        "type": "task",
                        "task": "test_task2",
                    },
                ],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_steps(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_steps_invalid_type(self):
        """Test workflow step validation with invalid step type"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "invalid_type", "task": "test_task"}],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_steps(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_steps_task_missing_task_field(self):
        """Test workflow step validation with task step missing task field"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        # Missing task field
                    }
                ],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_steps(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_steps_parallel_missing_steps(self):
        """Test workflow step validation with parallel step missing steps field"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "parallel_step",
                        "type": "parallel",
                        # Missing steps field
                    }
                ],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_steps(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_steps_retry_invalid_max_retries(self):
        """Test workflow step validation with retry step having invalid max_retries"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "retry_step",
                        "type": "retry",
                        "max_retries": -1,  # Invalid: negative
                        "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
                    }
                ],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_steps(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_workflow_cycles_no_cycles(self):
        """Test workflow cycle detection with no cycles"""
        dep_name = f"dependency_workflow_{self.uid}"
        # Create dependency workflow
        WorkflowDefinition.objects.create(
            name=dep_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            is_active=True,
            created_by=self.user,
        )
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "dependencies": [dep_name],
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_cycles(workflow_def)
        self.assertTrue(result.is_valid)
        self.assertFalse(result.details.get("has_cycles", True))

    def test_validate_workflow_cycles_self_dependency(self):
        """Test workflow cycle detection with self-dependency"""
        wf_name = f"test_workflow_{self.uid}"
        workflow_def = WorkflowDefinition.objects.create(
            name=wf_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "dependencies": [wf_name],  # Self-dependency
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_cycles(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.details.get("has_self_dependency", False))

    def test_validate_workflow_resources_valid_dependencies(self):
        """Test workflow resource validation with valid dependencies"""
        dep_name = f"dependency_workflow_{self.uid}"
        # Create dependency workflow
        WorkflowDefinition.objects.create(
            name=dep_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            is_active=True,
            created_by=self.user,
        )
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "dependencies": [dep_name],
                "steps": [{"name": "step1", "type": "task", "task": "test.task"}],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_resources(workflow_def)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("dependencies_valid", False))

    def test_validate_workflow_resources_missing_dependency(self):
        """Test workflow resource validation with missing dependency"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "dependencies": ["nonexistent_workflow"],
                "steps": [{"name": "step1", "type": "task", "task": "test.task"}],
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_resources(workflow_def)
        self.assertFalse(result.is_valid)
        self.assertIn("missing_workflows", result.details)

    def test_validate_workflow_definition_comprehensive(self):
        """Test comprehensive workflow definition validation"""
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test.task"}],
                "compensation": {"enabled": True},
            },
            created_by=self.user,
        )
        result = self.rules._validate_workflow_definition(workflow_def)
        self.assertTrue(result.is_valid)
        self.assertIn("validation_checks", result.details)
        self.assertTrue(result.details["validation_checks"].get("structure", False))
        self.assertTrue(result.details["validation_checks"].get("steps", False))
        self.assertTrue(result.details["validation_checks"].get("cycles", False))
        self.assertTrue(result.details["validation_checks"].get("resources", False))

    def test_validate_workflow_definition_integration_with_engine(self):
        """Test workflow definition validation integration with WorkflowEngine"""
        from hub.apps.orchestration.registry import WorkflowRegistry
        from hub.apps.orchestration.workflow_engine import WorkflowEngine

        # Create workflow definition
        workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test.task"}],
            },
            created_by=self.user,
        )

        # Validate workflow definition
        result = self.rules._validate_workflow_definition(workflow_def)
        self.assertTrue(result.is_valid)

        # Create workflow registry
        registry = WorkflowRegistry()

        # Register workflow (should succeed if validation passed)
        try:
            registered_def = registry.register_workflow(
                workflow_name=workflow_def.name,
                dsl_json=workflow_def.dsl_json,
                version=workflow_def.version,
                created_by_id=str(self.user.id),
            )
            self.assertIsNotNone(registered_def)
            self.assertEqual(registered_def.name, workflow_def.name)
        except Exception as e:
            self.fail(f"Workflow registration should succeed after validation: {e!s}")
