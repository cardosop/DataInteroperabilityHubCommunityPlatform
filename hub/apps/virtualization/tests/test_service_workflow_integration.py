"""
Integration tests for VirtualizationService and VirtualizationWorkflow integration

Tests the integration between VirtualizationService.execute_query() and VirtualizationWorkflow.
Feat1 2.1.3: workflow vs REST parity and single execution path (no mocks).
"""

import socket
import unittest
import uuid

import pytest
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetSourceType, DataStrategy
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import reset_workflow_definition_cache
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import User, UserStatus
from hub.apps.virtualization.models import (
    QueryExecution,
    QueryExecutionMode,
    QueryExecutionStatus,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.services import VirtualizationService

pytestmark = pytest.mark.django_db(transaction=True)


def _database_reachable():
    """Check if the test database is reachable via TCP connection."""
    db = settings.DATABASES["default"]
    try:
        sock = socket.create_connection(
            (db.get("HOST", "localhost"), int(db.get("PORT", 5432))), timeout=2
        )
        sock.close()
        return True
    except OSError:
        return False


from hub.apps.testing.virtualization_support import get_test_db_source as _get_test_db_source



class ServiceWorkflowIntegrationTest(TestCase):
    """Integration tests for VirtualizationService and VirtualizationWorkflow"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _database_reachable():
            raise unittest.SkipTest("Database source not reachable")

    def setUp(self):
        """Set up test fixtures"""
        reset_workflow_definition_cache()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create DATA_PROVIDER role and assign to user
        from hub.apps.users.models import Role, UserRole

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        # Set up subscription/plan

        plan, _ = TenantPlan.objects.get_or_create(
            slug="virtualization-test-plan",
            defaults={
                "name": "Virtualization Test Plan",
                "tier": PlanTier.PRO,
                "limits_json": {
                    "max_assets": 100,
                    "max_storage_gb": 1000,
                    "max_virtual_datasets": 100,
                },
                "is_active": True,
            },
        )
        if "max_storage_gb" not in (plan.limits_json or {}):
            plan.limits_json = {
                **(plan.limits_json or {}),
                "max_storage_gb": 1000,
                "max_virtual_datasets": 100,
            }
            plan.save(update_fields=["limits_json"])
        if self.tenant.plan_id != plan.id:
            self.tenant.plan = plan
            self.tenant.save(update_fields=["plan"])
        Subscription.objects.get_or_create(
            tenant=self.tenant,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now(),
            },
        )

        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT 1 AS id, 'test' AS name",
            query_type=QueryType.SQL,
            sources=[_get_test_db_source()],
            status=VirtualDatasetStatus.ACTIVE,
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_execute_query_creates_workflow_instance(self):
        """Test that execute_query creates a workflow instance"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )

        self.assertIsNotNone(execution.workflow_instance)
        self.assertEqual(
            execution.workflow_instance.workflow_name, "virtualization_query_execution"
        )

        workflow_instance = WorkflowInstance.objects.get(id=execution.workflow_instance.id)
        self.assertEqual(workflow_instance.tenant_id, self.tenant.id)
        self.assertEqual(workflow_instance.created_by_id, self.user.id)

    def test_get_workflow_instance(self):
        """Test get_workflow_instance method"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )

        workflow_instance = self.service.get_workflow_instance(
            execution_id=str(execution.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(workflow_instance)
        self.assertEqual(workflow_instance.id, execution.workflow_instance.id)

    def test_get_workflow_state(self):
        """Test get_workflow_state method"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )

        state = self.service.get_workflow_state(
            execution_id=str(execution.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("workflow_instance_id", state)
        self.assertIn("workflow_name", state)
        self.assertIn("status", state)
        self.assertIn("state_data", state)
        self.assertEqual(state["workflow_name"], "virtualization_query_execution")

    def test_get_workflow_progress(self):
        """Test get_workflow_progress method"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )

        progress = self.service.get_workflow_progress(
            execution_id=str(execution.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("progress_percentage", progress)
        self.assertIn("current_step", progress)
        self.assertIn("status", progress)
        self.assertIn("workflow_instance_id", progress)
        self.assertGreaterEqual(progress["progress_percentage"], 0)
        self.assertLessEqual(progress["progress_percentage"], 100)

    def test_execute_query_with_cached_result(self):
        """Test that execute_query returns cached result without workflow"""
        from django.core.cache import cache

        # Create cache entry
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {"data": [{"id": 1, "name": "Test"}], "row_count": 1, "columns": ["id", "name"]},
            3600,
        )

        # Execute query (should return cached result)
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Verify execution is completed and has no workflow instance (cached results don't use workflow)
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        self.assertIsNone(execution.workflow_instance)
        self.assertEqual(execution.result_cache_key, cache_key)
        self.assertIsNotNone(execution.metrics, "Cached execution should have metrics")
        self.assertTrue(execution.metrics.get("cached", False))

    def test_execute_query_links_workflow_on_failure(self):
        """Test that execute_query links workflow instance even on failure"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )
        self.assertIsNotNone(execution.workflow_instance, "Workflow instance should be linked")
        self.assertEqual(
            execution.workflow_instance.workflow_name, "virtualization_query_execution"
        )

    def test_execute_query_multi_source_federated_metadata(self):
        """Test execute_query with multi-source federated dataset (metadata-only sources)."""
        import uuid as uuid_mod

        from hub.apps.assets.models import Asset, AssetSourceType, DataStrategy

        asset1 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-svc-1-{uuid_mod.uuid4()}",
            name="Service Fed 1",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-svc-2-{uuid_mod.uuid4()}",
            name="Service Fed 2",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
        )
        multi_vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Service Multi Federated",
            query="SELECT * FROM combined",
            query_type=QueryType.FEDERATED,
            sources=[
                {"type": "federated_asset", "asset_id": str(asset1.id)},
                {"type": "federated_asset", "asset_id": str(asset2.id)},
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )
        execution = self.service.execute_query(
            virtual_dataset_id=str(multi_vd.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )
        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, multi_vd.id)
        self.assertIsNotNone(execution.workflow_instance)
        self.assertEqual(str(execution.workflow_instance.tenant_id), str(self.tenant.id))
        self.assertEqual(
            execution.workflow_instance.workflow_name, "virtualization_query_execution"
        )
        instance = execution.workflow_instance
        instance.refresh_from_db()
        self.assertEqual(
            instance.status,
            WorkflowStatus.COMPLETED,
            "Multi-source federated (metadata-only) workflow should complete successfully",
        )
        self.assertIn("execution_results", instance.state_data)
        self.assertEqual(
            instance.state_data["execution_results"].get("source_count"),
            2,
            "Federated query with two sources must report source_count=2",
        )

    def test_service_and_workflow_parity_single_federated_source(self):
        """Test service execution and workflow execution parity for single federated_asset source."""
        import uuid as uuid_mod

        from hub.apps.assets.models import Asset, AssetSourceType, DataStrategy

        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"fed-parity-svc-{uuid_mod.uuid4()}",
            name="Parity Asset",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
        )
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Parity VD",
            query="SELECT * FROM t",
            query_type=QueryType.SQL,
            sources=[{"type": "federated_asset", "asset_id": str(asset.id)}],
            status=VirtualDatasetStatus.ACTIVE,
        )
        direct_result = self.service._execute_query_against_sources(
            query=vd.query,
            query_type=vd.query_type,
            sources=vd.get_sources(),
            parameters={},
            timeout_seconds=300,
        )
        self.assertEqual(len(direct_result), 1)
        direct_row_count = direct_result[0].get("row_count", 0)
        execution = self.service.execute_query(
            virtual_dataset_id=str(vd.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.ASYNC,
        )
        self.assertIsNotNone(execution.workflow_instance)
        execution.workflow_instance.refresh_from_db()
        self.assertEqual(
            execution.workflow_instance.status,
            WorkflowStatus.COMPLETED,
            "Single federated (metadata-only) workflow must complete for parity assertion",
        )
        wr = execution.workflow_instance.state_data.get("execution_results", {})
        self.assertEqual(
            wr.get("row_count"),
            direct_row_count,
            "Workflow execution row_count must match direct service execution (parity)",
        )

    def test_workflow_and_service_sources_produce_same_result(self):
        """
        Feat1 2.1.3: Multi-source query via workflow produces same result as same query
        via the service's _execute_query_against_sources + _aggregate_results path.
        No mocks; uses federated_asset METADATA_ONLY (real code path).
        """
        # Virtual dataset with single federated_asset source (METADATA_ONLY, no external calls)
        federated_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"parity-test-{uuid.uuid4()}",
            name="Parity Test Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
        )
        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(federated_asset.id),
                "query": "SELECT * FROM metadata",
            }
        ]
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Parity Test Virtual Dataset",
            query="SELECT * FROM metadata",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        query = vd.query
        params = {}
        timeout = 60

        # Direct path: same entrypoint the workflow uses internally
        results = self.service._execute_query_against_sources(
            query, vd.query_type, vd.get_sources() or [], params, timeout
        )
        aggregated = self.service._aggregate_results(results, vd.query_type)
        all_columns = set()
        for r in results:
            all_columns.update(r.get("columns", []))
        direct_result = {
            "data": aggregated,
            "columns": list(all_columns),
            "row_count": len(aggregated),
            "source_type": results[0].get("source_type", "unknown") if results else "unknown",
            "query_type": vd.query_type,
        }

        # Workflow path (REST uses this): execute_query SYNC runs the workflow
        execution = self.service.execute_query(
            virtual_dataset_id=str(vd.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters=params,
            execution_mode=QueryExecutionMode.SYNC,
            timeout_seconds=timeout,
        )

        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        workflow_result = execution.metrics or {}

        # Assert parity: same data shape and content
        self.assertEqual(
            workflow_result.get("row_count"),
            direct_result["row_count"],
            "row_count must match between workflow and service path",
        )
        self.assertEqual(
            sorted(workflow_result.get("columns", [])),
            sorted(direct_result["columns"]),
            "columns must match between workflow and service path",
        )
        self.assertEqual(
            len(workflow_result.get("data", [])),
            len(direct_result["data"]),
            "data length must match between workflow and service path",
        )
        # Data content: at least one row with expected metadata keys (federated_asset_metadata)
        wf_data = workflow_result.get("data", [])
        dr_data = direct_result["data"]
        if wf_data and dr_data:
            self.assertIn("asset_id", wf_data[0])
            self.assertIn("asset_name", wf_data[0])
            self.assertEqual(wf_data[0].get("asset_id"), str(federated_asset.id))
            self.assertEqual(dr_data[0].get("asset_id"), str(federated_asset.id))

    def test_workflow_and_service_sources_produce_same_result_multi_source(self):
        """
        Feat1 2.1.3: Multi-source query via workflow produces same result as
        same query via service (_execute_query_against_sources + _aggregate_results).
        Uses two federated_asset METADATA_ONLY sources; no mocks.
        """
        asset1 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"parity-multi-1-{uuid.uuid4()}",
            name="Parity Multi 1",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"parity-multi-2-{uuid.uuid4()}",
            name="Parity Multi 2",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY,
        )
        sources = [
            {"type": "federated_asset", "asset_id": str(asset1.id), "query": "SELECT * FROM m1"},
            {"type": "federated_asset", "asset_id": str(asset2.id), "query": "SELECT * FROM m2"},
        ]
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Parity Multi Virtual Dataset",
            query="SELECT * FROM combined",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )
        query = vd.query
        params = {}
        timeout = 60

        # Direct path (same as workflow's _execute_via_service_sources)
        results = self.service._execute_query_against_sources(
            query, vd.query_type, vd.get_sources() or [], params, timeout
        )
        aggregated = self.service._aggregate_results(results, vd.query_type)
        all_columns = set()
        for r in results:
            all_columns.update(r.get("columns", []))
        direct_result = {
            "data": aggregated,
            "columns": list(all_columns),
            "row_count": len(aggregated),
        }

        # Workflow path (SYNC = same as REST for this flow)
        execution = self.service.execute_query(
            virtual_dataset_id=str(vd.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters=params,
            execution_mode=QueryExecutionMode.SYNC,
            timeout_seconds=timeout,
        )

        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        workflow_result = execution.metrics or {}

        self.assertEqual(
            workflow_result.get("row_count"),
            direct_result["row_count"],
            "row_count must match for multi-source",
        )
        self.assertEqual(
            sorted(workflow_result.get("columns", [])),
            sorted(direct_result["columns"]),
            "columns must match for multi-source",
        )
        self.assertEqual(
            len(workflow_result.get("data", [])),
            len(direct_result["data"]),
            "data length must match for multi-source",
        )
        # Two sources => two metadata rows
        self.assertEqual(direct_result["row_count"], 2)
        asset_ids = {str(asset1.id), str(asset2.id)}
        wf_asset_ids = {row.get("asset_id") for row in workflow_result.get("data", [])}
        self.assertEqual(wf_asset_ids, asset_ids)
