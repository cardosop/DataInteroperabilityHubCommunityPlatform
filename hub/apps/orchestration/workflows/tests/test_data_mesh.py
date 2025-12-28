"""
Unit tests for Data Mesh Domain Creation Workflow
"""
import unittest
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus, WorkflowStep
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.data_mesh import DataMeshWorkflow
from hub.apps.mesh.models import DataMeshDomain, DomainStatus, PolicyApplication, PolicyApplicationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.governance.models import AccessPolicy


class DataMeshWorkflowUnitTest(TestCase):
    """Unit tests for data mesh workflow tasks"""

    def setUp(self):
        self.tenant, _ = Tenant.objects.get_or_create(name="Test Tenant")
        self.user, _ = User.objects.get_or_create(
            email="test@example.com",
            defaults={"password": "testpass123", "tenant": self.tenant}
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        DataMeshWorkflow.register_workflow(self.registry)
        DataMeshWorkflow.register_tasks(self.engine)

    def test_validate_domain_task(self):
        """Test domain validation task"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "name": "Test Domain",
            "description": "Test description",
            "owner_id": str(self.user.id),
            "boundaries": {"data_products": []},
            "capabilities": {},
            "resource_quota": {"storage_gb": 100}
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_domain",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._validate_domain_task(
            input_data, instance, step
        )

        self.assertIn("validated", result)
        self.assertTrue(result["validated"])
        self.assertEqual(result["domain_name"], "Test Domain")

        # Verify validated data stored in state_data
        instance.refresh_from_db()
        self.assertEqual(instance.state_data["validated_name"], "Test Domain")
        self.assertEqual(instance.state_data["validated_description"], "Test description")
        self.assertEqual(instance.state_data["validated_owner_id"], str(self.user.id))

    def test_validate_domain_task_missing_name(self):
        """Test domain validation fails with missing name"""
        input_data = {
            "tenant_id": str(self.tenant.id),
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_domain",
            step_type="task",
            status=StepStatus.PENDING
        )

        with self.assertRaises(ValueError) as context:
            DataMeshWorkflow._validate_domain_task(
                input_data, instance, step
            )

        self.assertIn("Domain name is required", str(context.exception))

    def test_validate_domain_task_duplicate_name(self):
        """Test domain validation fails with duplicate name"""
        # Create existing domain
        DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Existing Domain",
            status=DomainStatus.ACTIVE
        )

        input_data = {
            "tenant_id": str(self.tenant.id),
            "name": "Existing Domain",
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_domain",
            step_type="task",
            status=StepStatus.PENDING
        )

        with self.assertRaises(ValueError) as context:
            DataMeshWorkflow._validate_domain_task(
                input_data, instance, step
            )

        self.assertIn("already exists", str(context.exception))

    def test_validate_domain_task_invalid_boundaries(self):
        """Test domain validation fails with invalid boundaries"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "name": "Test Domain",
            "boundaries": {"data_products": "not a list"}  # Invalid: should be list
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="validate_domain",
            step_type="task",
            status=StepStatus.PENDING
        )

        with self.assertRaises(ValueError) as context:
            DataMeshWorkflow._validate_domain_task(
                input_data, instance, step
            )

        self.assertIn("must be a list", str(context.exception))

    @patch('hub.apps.governance.services.GovernanceService.validate_resource_quota_allocation')
    def test_allocate_resources_task(self, mock_validate_quota):
        """Test resource allocation task"""
        mock_validate_quota.return_value = {"storage_gb": 100, "compute_hours": 50}

        input_data = {
            "tenant_id": str(self.tenant.id),
            "resource_quota": {"storage_gb": 100, "compute_hours": 50}
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "validated_resource_quota": {"storage_gb": 100, "compute_hours": 50}
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="allocate_resources",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._allocate_resources_task(
            input_data, instance, step
        )

        self.assertIn("allocated_quota", result)
        self.assertEqual(result["allocated_quota"]["storage_gb"], 100)
        self.assertIn("resource_usage", result)
        self.assertIn("storage_gb_used", result["resource_usage"])

        # Verify allocated resources stored in state_data
        instance.refresh_from_db()
        self.assertIn("allocated_resource_quota", instance.state_data)
        self.assertIn("resource_usage", instance.state_data)

    @patch('hub.apps.governance.services.GovernanceService.validate_resource_quota_allocation')
    def test_allocate_resources_task_validation_fails(self, mock_validate_quota):
        """Test resource allocation fails when validation fails"""
        from hub.apps.core.services.base import ValidationError
        mock_validate_quota.side_effect = ValidationError("Quota exceeded")

        input_data = {
            "tenant_id": str(self.tenant.id),
            "resource_quota": {"storage_gb": 10000}
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "validated_resource_quota": {"storage_gb": 10000}
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="allocate_resources",
            step_type="task",
            status=StepStatus.PENDING
        )

        with self.assertRaises(ValueError) as context:
            DataMeshWorkflow._allocate_resources_task(
                input_data, instance, step
            )

        self.assertIn("Resource quota allocation failed", str(context.exception))

    @patch('hub.apps.orchestration.workflows.data_mesh.DataMeshWorkflow._update_progress')
    def test_create_domain_task(self, mock_update_progress):
        """Test domain creation task"""
        input_data = {
            "tenant_id": str(self.tenant.id),
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "validated_name": "Test Domain",
            "validated_description": "Test description",
            "validated_owner_id": str(self.user.id),
            "validated_boundaries": {},
            "validated_capabilities": {},
            "allocated_resource_quota": {"storage_gb": 100},
            "resource_usage": {"storage_gb_used": 0}
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="create_domain",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._create_domain_task(
            input_data, instance, step
        )

        self.assertIn("domain_id", result)
        self.assertEqual(result["domain_name"], "Test Domain")
        self.assertEqual(result["status"], DomainStatus.ACTIVE)

        # Verify domain was created
        domain = DataMeshDomain.objects.get(id=result["domain_id"])
        self.assertEqual(domain.tenant, self.tenant)
        self.assertEqual(domain.name, "Test Domain")
        self.assertEqual(domain.status, DomainStatus.ACTIVE)

        # Verify domain_id stored in state_data
        instance.refresh_from_db()
        self.assertEqual(instance.state_data["domain_id"], result["domain_id"])

    @patch('hub.apps.mesh.services.DataMeshService.apply_policy')
    def test_apply_default_policies_task(self, mock_apply_policy):
        """Test applying default policies task"""
        # Create domain
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE
        )

        # Create default policies (tenant-wide)
        policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Default Policy 1",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True
        )
        policy2 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Default Policy 2",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True
        )

        # Mock policy application
        mock_application1 = MagicMock()
        mock_application1.id = uuid.uuid4()
        mock_application2 = MagicMock()
        mock_application2.id = uuid.uuid4()
        mock_apply_policy.side_effect = [mock_application1, mock_application2]

        input_data = {
            "tenant_id": str(self.tenant.id),
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "domain_id": str(domain.id)
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="apply_default_policies",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._apply_default_policies_task(
            input_data, instance, step
        )

        self.assertIn("applied_policies", result)
        self.assertEqual(len(result["applied_policies"]), 2)

        # Verify applied policies stored in state_data
        instance.refresh_from_db()
        self.assertIn("applied_policies", instance.state_data)
        self.assertEqual(len(instance.state_data["applied_policies"]), 2)

    def test_initialize_analytics_task(self):
        """Test analytics initialization task"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE
        )

        input_data = {
            "tenant_id": str(self.tenant.id),
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "domain_id": str(domain.id)
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=4,
            step_name="initialize_analytics",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._initialize_analytics_task(
            input_data, instance, step
        )

        self.assertIn("analytics_initialized", result)
        self.assertTrue(result["analytics_initialized"])

        # Verify analytics status stored in state_data
        instance.refresh_from_db()
        self.assertTrue(instance.state_data["analytics_initialized"])

    @patch('hub.apps.orchestration.workflows.data_mesh.EventPublisher')
    def test_complete_task(self, mock_event_publisher_class):
        """Test workflow completion task"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE
        )

        mock_event_publisher = MagicMock()
        mock_event_publisher_class.return_value = mock_event_publisher

        input_data = {
            "tenant_id": str(self.tenant.id),
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.started_at = timezone.now()
        instance.state_data = {
            "domain_id": str(domain.id),
            "applied_policies": []
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=5,
            step_name="complete",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._complete_task(
            input_data, instance, step
        )

        self.assertIn("completed", result)
        self.assertTrue(result["completed"])
        self.assertEqual(result["domain_id"], str(domain.id))

        # Verify completion status stored in state_data
        instance.refresh_from_db()
        self.assertTrue(instance.state_data["completed"])
        self.assertIn("completed_at", instance.state_data)

        # Verify events were published
        # _update_progress publishes step_completed, _complete_task publishes started (if not already) and completed
        # So we expect at least 2 events (step_completed + completed), possibly 3 if started is also published
        self.assertGreaterEqual(mock_event_publisher.publish.call_count, 2)

    def test_rollback_domain_creation_task(self):
        """Test domain creation rollback task"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE
        )

        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "domain_id": str(domain.id)
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="rollback_domain_creation",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._rollback_domain_creation_task(
            input_data, instance, step
        )

        self.assertIn("rolled_back", result)
        self.assertTrue(result["rolled_back"])

        # Verify domain was deleted
        with self.assertRaises(DataMeshDomain.DoesNotExist):
            DataMeshDomain.objects.get(id=domain.id)

    def test_rollback_policy_application_task(self):
        """Test policy application rollback task"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE
        )

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True
        )

        policy_application = PolicyApplication.objects.create(
            domain=domain,
            policy=policy,
            status=PolicyApplicationStatus.APPLIED,
            applied_by=self.user
        )

        input_data = {
            "tenant_id": str(self.tenant.id),
        }
        instance = self.engine.create_instance(
            workflow_name=DataMeshWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "domain_id": str(domain.id),
            "applied_policies": [{
                "policy_id": str(policy.id),
                "application_id": str(policy_application.id)
            }]
        }
        instance.save()

        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="rollback_policy_application",
            step_type="task",
            status=StepStatus.PENDING
        )

        result = DataMeshWorkflow._rollback_policy_application_task(
            input_data, instance, step
        )

        self.assertIn("rolled_back", result)
        self.assertTrue(result["rolled_back"])
        self.assertEqual(result["revoked_count"], 1)

        # Verify policy application was revoked
        policy_application.refresh_from_db()
        self.assertEqual(policy_application.status, PolicyApplicationStatus.REVOKED)

