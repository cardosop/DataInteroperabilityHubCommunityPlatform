"""
Integration tests for Data Mesh Domain Creation Workflow
"""
import unittest
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.data_mesh import DataMeshWorkflow
from hub.apps.mesh.models import DataMeshDomain, DomainStatus, PolicyApplication, PolicyApplicationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.governance.models import AccessPolicy


class DataMeshWorkflowIntegrationTest(TestCase):
    """Integration tests for data mesh workflow execution"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Integration {unique_id}",
            slug=f"test-tenant-integration-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-integration-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )

    def test_full_workflow_execution(self):
        """Test full workflow execution"""
        # Create default policies (tenant-wide policies that should be applied to all domains)
        policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Default Policy 1",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            asset=None,  # Tenant-wide policy
            dataset=None  # Tenant-wide policy
        )
        policy2 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Default Policy 2",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            asset=None,  # Tenant-wide policy
            dataset=None  # Tenant-wide policy
        )

        # Execute workflow
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataMeshWorkflow.register_workflow(registry)
        DataMeshWorkflow.register_tasks(engine)

        result = DataMeshWorkflow.execute(
            tenant_id=str(self.tenant.id),
            name="Test Domain Integration",
            description="Test description",
            owner_id=str(self.user.id),
            boundaries={"data_products": []},
            capabilities={},
            resource_quota={"storage_gb": 100, "compute_hours": 50},
            created_by_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("domain_id", result)

        # Get workflow instance
        workflow_instance_id = result["workflow_instance_id"]
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)

        # Verify workflow status
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

        # Verify domain was created
        domain_id = result["domain_id"]
        domain = DataMeshDomain.objects.get(id=domain_id)
        self.assertEqual(domain.tenant, self.tenant)
        self.assertEqual(domain.name, "Test Domain Integration")
        self.assertEqual(domain.status, DomainStatus.ACTIVE)
        self.assertEqual(domain.resource_quota["storage_gb"], 100)

        # Verify policies were applied
        policy_applications = PolicyApplication.objects.filter(domain=domain)
        self.assertEqual(policy_applications.count(), 2)

        # Verify progress tracking
        self.assertIn("progress_percentage", workflow_instance.state_data)
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

    def test_workflow_execution_with_compensation(self):
        """Test workflow execution with compensation on failure"""

        # Create a domain with the same name to cause validation failure
        DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Duplicate Domain",
            status=DomainStatus.ACTIVE
        )

        # Execute workflow with duplicate name
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataMeshWorkflow.register_workflow(registry)
        DataMeshWorkflow.register_tasks(engine)

        with self.assertRaises(ValueError) as context:
            DataMeshWorkflow.execute(
                tenant_id=str(self.tenant.id),
                name="Duplicate Domain",  # Duplicate name
                created_by_id=str(self.user.id),
                engine=engine,
                registry=registry
            )

        self.assertIn("already exists", str(context.exception))

    def test_workflow_execution_with_policy_application_failure(self):
        """Test workflow execution when policy application fails (should continue)"""
        # Create default policies
        policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Default Policy 1",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            asset=None,  # Tenant-wide policy
            dataset=None  # Tenant-wide policy
        )

        # Create a second policy that will fail application (by making it belong to a different tenant)
        # This will cause a validation error when trying to apply it
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        policy2 = AccessPolicy.objects.create(
            tenant=other_tenant,  # Different tenant - will cause validation error
            name="Default Policy 2 (Wrong Tenant)",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            asset=None,  # Tenant-wide policy
            dataset=None  # Tenant-wide policy
        )

        # Execute workflow
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataMeshWorkflow.register_workflow(registry)
        DataMeshWorkflow.register_tasks(engine)

        result = DataMeshWorkflow.execute(
            tenant_id=str(self.tenant.id),
            name="Test Domain With Policy Failure",
            created_by_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify workflow still completed (policy failure is non-fatal)
        self.assertTrue(result["success"])
        self.assertIn("domain_id", result)

        # Get workflow instance
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])

        # Verify domain was created
        domain = DataMeshDomain.objects.get(id=result["domain_id"])

        # Verify only the enabled policy was applied (disabled policies are not queried)
        policy_applications = PolicyApplication.objects.filter(domain=domain)
        self.assertEqual(policy_applications.count(), 1)  # Only policy1 (enabled) was applied

        # Verify the applied policy is policy1
        self.assertEqual(policy_applications.first().policy, policy1)

    def test_workflow_progress_tracking(self):
        """Test workflow progress tracking throughout execution"""

        # Execute workflow
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataMeshWorkflow.register_workflow(registry)
        DataMeshWorkflow.register_tasks(engine)

        result = DataMeshWorkflow.execute(
            tenant_id=str(self.tenant.id),
            name="Test Domain Progress",
            created_by_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Get workflow instance
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])

        # Verify progress reached 100%
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

        # Verify progress is tracked in state_data
        self.assertIn("current_step_name", workflow_instance.state_data)

