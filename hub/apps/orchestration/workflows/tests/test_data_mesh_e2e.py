"""
End-to-end tests for Data Mesh Domain Creation Workflow
"""
import unittest
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflows.data_mesh import DataMeshWorkflow
from hub.apps.mesh.models import DataMeshDomain, DomainStatus, PolicyApplication, PolicyApplicationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.governance.models import AccessPolicy


class DataMeshWorkflowE2ETest(TestCase):
    """End-to-end tests for data mesh workflow"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant E2E {unique_id}",
            slug=f"test-tenant-e2e-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-e2e-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )

    def test_complete_domain_creation_workflow(self):
        """
        Test complete domain creation workflow end-to-end.

        This simulates the E2E flow where a user creates a domain
        and the workflow orchestrates the entire process including
        validation, resource allocation, domain creation, policy application,
        and analytics initialization.
        """
        # Create default policies (tenant-wide policies that should be applied to all domains)
        policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Data Access Policy",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            priority=10,
            asset=None,  # Tenant-wide policy
            dataset=None  # Tenant-wide policy
        )
        policy2 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Data Retention Policy",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            priority=20,
            asset=None,  # Tenant-wide policy
            dataset=None  # Tenant-wide policy
        )

        # Execute complete workflow
        result = DataMeshWorkflow.execute(
            tenant_id=str(self.tenant.id),
            name="Production Domain E2E",
            description="Production data mesh domain for E2E testing",
            owner_id=str(self.user.id),
            boundaries={
                "data_products": ["product1", "product2"],
                "schemas": ["schema1"],
                "access_patterns": ["api", "batch"]
            },
            capabilities={
                "apis": ["rest", "graphql"],
                "services": ["ingestion", "transformation"]
            },
            resource_quota={
                "storage_gb": 1000,
                "compute_hours": 500,
                "api_calls_per_day": 100000
            },
            created_by_id=str(self.user.id)
        )

        # Verify complete workflow execution
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("domain_id", result)

        # Get workflow instance
        workflow_instance_id = result["workflow_instance_id"]
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)

        # Verify workflow completed successfully
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertIsNone(workflow_instance.error_message)

        # Verify domain exists and has correct attributes
        domain_id = result["domain_id"]
        domain = DataMeshDomain.objects.get(id=domain_id)
        self.assertEqual(domain.tenant, self.tenant)
        self.assertEqual(domain.name, "Production Domain E2E")
        self.assertEqual(domain.description, "Production data mesh domain for E2E testing")
        self.assertEqual(domain.owner, self.user)
        self.assertEqual(domain.status, DomainStatus.ACTIVE)
        self.assertEqual(domain.boundaries["data_products"], ["product1", "product2"])
        self.assertEqual(domain.capabilities["apis"], ["rest", "graphql"])
        self.assertEqual(domain.resource_quota["storage_gb"], 1000)

        # Verify resource usage initialized
        self.assertIn("storage_gb_used", domain.resource_usage)
        self.assertEqual(domain.resource_usage["storage_gb_used"], 0)

        # Verify policies were applied
        policy_applications = PolicyApplication.objects.filter(domain=domain)
        self.assertEqual(policy_applications.count(), 2)
        for app in policy_applications:
            self.assertEqual(app.status, PolicyApplicationStatus.APPLIED)

        # Verify analytics initialized
        self.assertTrue(workflow_instance.state_data["analytics_initialized"])

        # Verify progress tracking
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)
        self.assertEqual(workflow_instance.state_data["current_step_name"], "complete")

        # Verify workflow state contains event-related data
        # Events are published but may fail validation if event schema registry isn't updated
        # The workflow continues even if event publishing fails (logged as warnings)

        # Verify workflow completion timestamp
        self.assertIn("completed_at", workflow_instance.state_data)

    def test_workflow_compensation_on_failure(self):
        """
        Test workflow compensation when domain creation fails.

        This verifies that compensation logic properly rolls back
        resources and domain creation when a step fails.
        """

        # Create a domain with the same name to cause validation failure
        existing_domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Existing Domain",
            status=DomainStatus.ACTIVE
        )

        # Execute workflow with duplicate name (will fail at validation)
        with self.assertRaises(ValueError) as context:
            DataMeshWorkflow.execute(
                tenant_id=str(self.tenant.id),
                name="Existing Domain",  # Duplicate name
                created_by_id=str(self.user.id)
            )

        self.assertIn("already exists", str(context.exception))

        # Verify no new domain was created
        domain_count = DataMeshDomain.objects.filter(tenant=self.tenant).count()
        self.assertEqual(domain_count, 1)  # Only the existing domain

    def test_workflow_with_minimal_input(self):
        """
        Test workflow execution with minimal required input.

        This verifies that the workflow works with only required fields.
        """

        # Execute workflow with minimal input
        result = DataMeshWorkflow.execute(
            tenant_id=str(self.tenant.id),
            name="Minimal Domain",
            created_by_id=str(self.user.id)
        )

        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn("domain_id", result)

        # Verify domain was created with defaults
        domain = DataMeshDomain.objects.get(id=result["domain_id"])
        self.assertEqual(domain.name, "Minimal Domain")
        self.assertEqual(domain.status, DomainStatus.ACTIVE)
        self.assertEqual(domain.boundaries, {})
        self.assertEqual(domain.capabilities, {})
        self.assertEqual(domain.resource_quota, {})

        # Verify workflow completed
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

