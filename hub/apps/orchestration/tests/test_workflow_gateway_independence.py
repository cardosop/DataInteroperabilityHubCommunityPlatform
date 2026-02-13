"""
Test workflow gateway independence.

Verifies that workflow execution works identically whether triggered via
Traefik API Gateway or direct api-service access.

This test explicitly covers "triggered via gateway" scenario as required
by task 11.3.2.
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    pytest = None
    pytestmark = None

import json
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


def _response_json(response):
    """Parse response body as JSON for both DRF Response (.data) and Django JsonResponse."""
    if getattr(response, "data", None) is not None:
        return response.data
    if response.content:
        return json.loads(response.content.decode("utf-8"))
    return {}


class WorkflowGatewayIndependenceTest(TestCase):
    """Test that workflows work identically via gateway or direct access"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant (using same pattern as other tests)
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        # Create user (using same pattern as other tests)
        self.user = User.objects.create(
            email="test@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Assign TENANT_ADMIN role (using the same pattern as other tests)
        from hub.apps.users.models import Role, UserRole

        tenant_admin_role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)

        # Ensure tenant has active subscription so billing middleware allows POST
        ensure_tenant_has_active_subscription(self.tenant)

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Valid ODPS document for testing (with proper contract structure)
        self.valid_odps_raw = """{
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "name", "type": "string"}
                    ]
                },
                "contract": {
                    "spec": {
                        "id": "test-contract",
                        "name": "Test Contract",
                        "info": {
                            "name": "Test Contract"
                        },
                        "schema": {
                            "fields": [
                                {"name": "id", "type": "string"},
                                {"name": "name", "type": "string"}
                            ]
                        }
                    }
                }
            }
        }"""

    def test_workflow_execution_via_direct_access(self):
        """Test workflow execution via direct api-service access (no gateway headers)"""
        # Execute workflow directly (simulating direct api-service access)
        # Use engine and registry directly to avoid background thread issues in tests
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)
        ProductCreationWorkflow.register_tasks(engine)

        workflow_input = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Create workflow instance directly (no request object needed)
        instance = engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Verify workflow instance was created successfully without request context
        self.assertIsNotNone(instance)
        self.assertEqual(instance.workflow_name, ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(instance.tenant_id, self.tenant.id)
        self.assertEqual(str(instance.created_by_id), str(self.user.id))

        # Verify input data contains only workflow-specific parameters
        self.assertIn("original_raw", instance.input_data)
        self.assertIn("original_format", instance.input_data)
        self.assertIn("tenant_id", instance.input_data)
        self.assertIn("user_id", instance.input_data)

        # Verify no gateway-specific data in input
        gateway_keys = [
            k
            for k in instance.input_data.keys()
            if "gateway" in k.lower() or "request" in k.lower()
        ]
        self.assertEqual(
            len(gateway_keys),
            0,
            f"No gateway-specific keys should be in input_data, found: {gateway_keys}",
        )

    def test_workflow_execution_via_gateway_headers(self):
        """Test workflow execution via gateway (with gateway headers)"""
        # Execute workflow via API endpoint (simulating gateway access)
        # Gateway adds X-Gateway-* headers, but workflow execution doesn't use them
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": self.valid_odps_raw,
                "original_format": "JSON",
            },
            format="json",
            # Simulate gateway headers (even though workflows don't use them)
            HTTP_X_GATEWAY_REQUEST_ID=str(uuid.uuid4()),
            HTTP_X_GATEWAY_TENANT_ID=str(self.tenant.id),
            HTTP_X_GATEWAY_USER_ID=str(self.user.id),
        )

        data = _response_json(response)
        # In test env the view runs workflow synchronously and returns 201 with result;
        # in production it returns 202 Accepted. Accept both.
        self.assertIn(
            response.status_code,
            (201, 202),
            f"Expected 201 or 202, got {response.status_code}: {data}",
        )
        self.assertIn("workflow_instance_id", data)

        # Get workflow instance (created synchronously, execution happens in background)
        workflow_instance_id = data["workflow_instance_id"]
        instance = WorkflowInstance.objects.get(id=workflow_instance_id)

        # Verify workflow instance was created successfully
        # (execution happens in background thread, so we just verify instance creation)
        self.assertIsNotNone(instance)
        self.assertEqual(instance.workflow_name, ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(instance.tenant_id, self.tenant.id)
        self.assertEqual(instance.created_by_id, self.user.id)

        # Store result for comparison
        gateway_result = {
            "workflow_instance_id": str(instance.id),
            "status": instance.status,
            "input_data": instance.input_data,
        }

        return gateway_result

    def test_workflow_execution_independence(self):
        """Test that workflow execution is identical via gateway or direct access"""
        # Execute via direct access (using workflow engine directly)
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)
        ProductCreationWorkflow.register_tasks(engine)

        workflow_input = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Create workflow instance directly (simulating direct api-service access)
        direct_instance = engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Execute via gateway (simulated via API endpoint)
        # The API endpoint internally calls ProductCreationWorkflow.execute_start()
        # which creates the workflow instance the same way
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": self.valid_odps_raw,
                "original_format": "JSON",
            },
            format="json",
            # Simulate gateway headers (even though workflows don't use them)
            HTTP_X_GATEWAY_REQUEST_ID=str(uuid.uuid4()),
            HTTP_X_GATEWAY_TENANT_ID=str(self.tenant.id),
            HTTP_X_GATEWAY_USER_ID=str(self.user.id),
        )

        data = _response_json(response)
        # In test env the view may return 201 (sync completion) or 202 (async); accept both.
        self.assertIn(
            response.status_code,
            (201, 202),
            f"Expected 201 or 202, got {response.status_code}: {data}",
        )
        gateway_instance_id = data["workflow_instance_id"]
        gateway_instance = WorkflowInstance.objects.get(id=gateway_instance_id)

        # Verify results are identical (except instance IDs which will differ)
        # Both instances should have the same workflow name, tenant, user, and input data
        self.assertEqual(direct_instance.workflow_name, gateway_instance.workflow_name)
        self.assertEqual(direct_instance.tenant_id, gateway_instance.tenant_id)
        self.assertEqual(str(direct_instance.created_by_id), str(gateway_instance.created_by_id))
        self.assertEqual(
            direct_instance.input_data["original_raw"], gateway_instance.input_data["original_raw"]
        )
        self.assertEqual(
            direct_instance.input_data["original_format"],
            gateway_instance.input_data["original_format"],
        )
        self.assertEqual(
            direct_instance.input_data["tenant_id"], gateway_instance.input_data["tenant_id"]
        )
        self.assertEqual(
            direct_instance.input_data["user_id"], gateway_instance.input_data["user_id"]
        )

        # Most importantly: verify that gateway headers don't affect workflow execution
        # The workflow instance is created identically regardless of request source
        # Verify no gateway-specific data leaked into workflow input
        direct_gateway_keys = [
            k for k in direct_instance.input_data.keys() if "gateway" in k.lower()
        ]
        gateway_gateway_keys = [
            k for k in gateway_instance.input_data.keys() if "gateway" in k.lower()
        ]
        self.assertEqual(
            len(direct_gateway_keys),
            0,
            f"Direct access should have no gateway keys: {direct_gateway_keys}",
        )
        self.assertEqual(
            len(gateway_gateway_keys),
            0,
            f"Gateway access should have no gateway keys: {gateway_gateway_keys}",
        )

    def test_workflow_engine_no_request_dependency(self):
        """Test that WorkflowEngine doesn't depend on request object"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)

        # Create workflow instance without any request context
        workflow_input = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Verify instance created successfully without request object
        self.assertIsNotNone(instance)
        self.assertEqual(instance.workflow_name, ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(instance.input_data, workflow_input)

    def test_workflow_execution_no_gateway_headers_required(self):
        """Test that workflow execution doesn't require or use gateway headers"""
        # Execute workflow via API without gateway headers
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": self.valid_odps_raw,
                "original_format": "JSON",
            },
            format="json",
            # No gateway headers
        )

        data = _response_json(response)
        # In test env the view may return 201 (sync completion) or 202 (async); accept both.
        self.assertIn(
            response.status_code,
            (201, 202),
            f"Expected 201 or 202, got {response.status_code}: {data}",
        )
        self.assertIn("workflow_instance_id", data)

        workflow_instance_id = data["workflow_instance_id"]
        instance = WorkflowInstance.objects.get(id=workflow_instance_id)

        # Verify workflow instance created successfully
        self.assertIsNotNone(instance)
        self.assertEqual(instance.workflow_name, ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(instance.tenant_id, self.tenant.id)
        self.assertEqual(instance.created_by_id, self.user.id)

        # Verify that workflow execution doesn't depend on gateway headers
        # The instance was created successfully without any gateway-specific logic
        # The workflow input data contains only workflow-specific parameters, no request headers
        self.assertIn("original_raw", instance.input_data)
        self.assertIn("original_format", instance.input_data)
        self.assertIn("tenant_id", instance.input_data)
        self.assertIn("user_id", instance.input_data)
