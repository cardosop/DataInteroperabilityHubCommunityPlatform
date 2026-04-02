"""
Minimal test to verify workflow execution_start returns quickly
This test isolates the issue to see if execute_start itself is hanging
"""
import json
import time
from django.test import TestCase

from hub.apps.contracts.models import Contract
from hub.apps.orchestration.models import WorkflowInstance
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
import uuid


def create_valid_odps_document(product_id: str = None) -> dict:
    """Create a valid ODPS 4.1 document for testing"""
    if not product_id:
        product_id = f"test-{int(time.time() * 1000)}"

    return {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": product_id,
                    "name": f"Test Product {product_id}",
                    "description": f"ODPS product for testing - {product_id}",
                }
            },
            "contract": {
                "spec": {
                    "apiVersion": "odcs/v3",
                    "kind": "DataContract",
                    "id": f"{product_id}-contract",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "required": True},
                            {"name": "name", "type": "string", "required": True},
                        ]
                    },
                }
            },
            "dataSchema": {
                "fields": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "name", "type": "string", "required": True},
                ]
            },
        },
    }


class MinimalWorkflowExecutionTest(TestCase):
    """Minimal test to verify execute_start returns quickly"""

    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        # Create test tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug="test",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        # Create test user
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="test-password-123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Pre-register workflow
        from hub.apps.orchestration.registry import WorkflowRegistry
        from hub.apps.orchestration.workflow_engine import WorkflowEngine

        self.workflow_engine = WorkflowEngine()
        self.workflow_registry = WorkflowRegistry()
        ProductCreationWorkflow.register_tasks(self.workflow_engine)
        ProductCreationWorkflow.register_workflow(self.workflow_registry)

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush"""
        pass

    def test_execute_start_returns_quickly(self):
        """Test that execute_start returns quickly (< 2 seconds)"""
        odps_doc = create_valid_odps_document("minimal-test")

        # Measure execution time
        start_time = time.time()
        result = ProductCreationWorkflow.execute_start(
            original_raw=json.dumps(odps_doc),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,
            engine=self.workflow_engine,
            registry=self.workflow_registry,
        )
        duration = time.time() - start_time

        # Verify it returned quickly
        self.assertLess(
            duration,
            2.0,
            f"execute_start took {duration:.2f}s, exceeds 2s target",
        )

        # Verify workflow_instance_id is returned
        self.assertIn("workflow_instance_id", result)
        self.assertIsNotNone(result["workflow_instance_id"])

        print(f"✅ execute_start returned in {duration:.2f}s with workflow_instance_id: {result['workflow_instance_id']}")
