"""
Shared base for concurrency tests. Uses real DB, real APIClient, no mocks/stubs.
"""

import time
import uuid
from typing import Any

from django.core.cache import cache
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus


def _disconnect_semantic_signals():
    """Disconnect semantic service signals to avoid timeouts during tests."""
    from django.db.models.signals import post_save

    try:
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract
        from hub.apps.semantic.signals import asset_saved, contract_saved

        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)
    except (ImportError, AttributeError):
        pass


class ConcurrencyTestBase(TransactionTestCase):
    """
    Base for concurrency tests. TransactionTestCase for proper isolation
    with concurrent threads. Real tenant, user, asset, APIClient.
    """

    def setUp(self):
        super().setUp()
        _disconnect_semantic_signals()
        cache.clear()

        unique = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name="Concurrency Tenant " + unique,
            slug="concurrency-" + unique,
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            email="concurrency-" + unique + "@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name=f"Concurrency Asset {unique}",
            status=AssetStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.sample_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test description",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
                    }
                },
            },
        }

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def create_contract_payload(self, product_id: str | None = None) -> dict[str, Any]:
        """Return ODPS payload for contract creation (unique product_id for concurrent creates)."""
        pid = product_id or f"product-{uuid.uuid4().hex[:12]}"
        return {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": pid,
                        "name": "Product " + pid,
                        "description": "Test",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": f"{pid}-contract",
                        "name": "Contract",
                        "version": "1.0.0",
                        "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
                    }
                },
            },
        }


class WorkflowConcurrencyTestBase(ConcurrencyTestBase):
    """
    Base for workflow concurrency tests. Adds WorkflowEngine, WorkflowRegistry,
    and helpers to create a simple workflow definition and register a test task.
    """

    def setUp(self):
        super().setUp()
        from hub.apps.orchestration.models import WorkflowDefinition
        from hub.apps.orchestration.registry import WorkflowRegistry
        from hub.apps.orchestration.workflow_engine import WorkflowEngine

        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        self._workflow_definition_model = WorkflowDefinition

    def create_simple_workflow_definition(
        self, workflow_name: str, num_steps: int = 3, version: str = "1.0.0"
    ):
        """Create a simple workflow definition for concurrency tests."""
        WorkflowDefinition = self._workflow_definition_model
        dsl_json = {
            "version": "1.0",
            "steps": [
                {"name": f"step_{i}", "type": "task", "task": "test_task"} for i in range(num_steps)
            ],
        }
        defaults = {"dsl_json": dsl_json, "is_active": True}
        wf, created = WorkflowDefinition.objects.get_or_create(
            name=workflow_name, version=version, defaults=defaults
        )
        if not created:
            wf.dsl_json = dsl_json
            wf.is_active = True
            wf.save(update_fields=["dsl_json", "is_active"])
        return wf

    def register_test_task(self):
        """Register a minimal test task (short sleep to simulate work)."""
        from hub.apps.orchestration.models import WorkflowInstance

        def test_task(
            input_data: dict[str, Any], instance: WorkflowInstance, step
        ) -> dict[str, Any]:
            time.sleep(0.005)
            return {"result": "success", "input": input_data}

        self.engine.task_registry["test_task"] = test_task
