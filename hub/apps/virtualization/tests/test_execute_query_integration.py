"""
Integration tests for execute_query() method.

Tests federated query execution and E2E workflows using real services.
"""

import contextlib
import socket
import unittest
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.virtualization_support import get_test_db_source as _get_test_db_source
from hub.apps.users.models import Role, UserRole
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
User = get_user_model()


def _database_reachable():
    """Check if the test database is reachable via TCP connection."""
    from django.conf import settings

    db = settings.DATABASES["default"]
    try:
        sock = socket.create_connection(
            (db.get("HOST", "localhost"), int(db.get("PORT", 5432))), timeout=2
        )
        sock.close()
        return True
    except OSError:
        return False


def semantic_service_available() -> bool:
    """Check if SemanticService is available (for SPARQL queries).

    Returns True if the service health check succeeds, False otherwise.
    Does NOT cache the result — callers should guard against repeated
    network calls in tight loops.
    """
    try:
        from hub.apps.semantic.service_client import SemanticServiceClient

        client = SemanticServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except (ConnectionError, OSError, TimeoutError):
        return False


class VirtualizationExecuteQueryIntegrationTest(TestCase):
    """Integration tests for execute_query() using real services"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _database_reachable():
            raise unittest.SkipTest("Database source not reachable")
        if not semantic_service_available():
            raise unittest.SkipTest("SemanticService not available")

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache

        reset_workflow_definition_cache()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        ensure_tenant_has_active_subscription(self.tenant)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Clear cache
        cache.clear()

    def test_federated_query_execution_sparql(self):
        """Test executing a federated query with SPARQL source"""
        sparql_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Integration Dataset",
            query="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        execution = self.service.execute_query(
            virtual_dataset_id=str(sparql_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, sparql_dataset.id)
        self.assertIn(
            execution.status, [QueryExecutionStatus.COMPLETED, QueryExecutionStatus.FAILED]
        )

    def test_federated_query_execution_multiple_sources(self):
        """Test executing a federated query across multiple sources"""
        db_source = _get_test_db_source()
        federated_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Federated Integration Dataset",
            query="SELECT 1 AS id, 'federated' AS name",
            query_type=QueryType.FEDERATED,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[db_source, db_source],
        )

        execution = self.service.execute_query(
            virtual_dataset_id=str(federated_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.ASYNC,
            parameters={},
        )

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, federated_dataset.id)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)
        self.assertIn(
            execution.status,
            [
                QueryExecutionStatus.PENDING,
                QueryExecutionStatus.RUNNING,
                QueryExecutionStatus.COMPLETED,
            ],
        )
        self.assertIsNotNone(execution.execution_log)
        self.assertIsInstance(execution.execution_log, list)

    def test_query_execution_result_caching(self):
        """Test that query results are properly cached"""
        simple_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Caching Test Dataset",
            query="SELECT 1 as test_value",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()],
        )

        execution1 = self.service.execute_query(
            virtual_dataset_id=str(simple_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )
        execution2 = self.service.execute_query(
            virtual_dataset_id=str(simple_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )

        self.assertIsNotNone(execution1)
        self.assertIsNotNone(execution2)
        self.assertEqual(
            execution1.status, QueryExecutionStatus.COMPLETED,
            f"First execution should complete; got {execution1.status}"
        )
        self.assertEqual(
            execution2.status, QueryExecutionStatus.COMPLETED,
            f"Second execution should complete; got {execution2.status}"
        )
        self.assertIsNotNone(execution1.result_cache_key)
        self.assertIsNotNone(execution2.result_cache_key)
        self.assertEqual(execution1.result_cache_key, execution2.result_cache_key)


class VirtualizationExecuteQueryE2ETest(TestCase):
    """End-to-end tests for complete query execution workflow"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _database_reachable():
            raise unittest.SkipTest("Database source not reachable")

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache

        reset_workflow_definition_cache()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        ensure_tenant_has_active_subscription(self.tenant)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Clear cache
        cache.clear()

    def test_e2e_query_execution_workflow(self):
        """Test complete E2E workflow: create dataset -> execute query -> check results"""
        # Create virtual dataset
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Test Dataset",
            query="SELECT 1 as test_column",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()],
        )

        execution = self.service.execute_query(
            virtual_dataset_id=str(dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )

        self.assertIsNotNone(
            execution, "execute_query() must return an execution record"
        )
        self.assertEqual(execution.virtual_dataset_id, dataset.id)
        # SYNC execution with valid sources should complete
        self.assertEqual(
            execution.status, QueryExecutionStatus.COMPLETED,
            f"SYNC E2E execution should complete; got {execution.status}"
        )
        self.assertIsNotNone(execution.query)
        self.assertGreater(len(execution.query), 0)
        self.assertIsNotNone(execution.metrics)
        self.assertIsInstance(execution.metrics, dict)
        self.assertIsNotNone(execution.execution_log)
        self.assertIsInstance(execution.execution_log, list)
        self.assertIsNotNone(execution.started_at)
        self.assertIsNotNone(execution.completed_at)
        self.assertLessEqual(execution.started_at, execution.completed_at)

    def test_e2e_async_query_execution_workflow(self):
        """Test complete E2E workflow for async query execution"""
        # Create virtual dataset
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Async Test Dataset",
            query="SELECT 1 AS id, 'async_test' AS name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()],
        )

        execution = self.service.execute_query(
            virtual_dataset_id=str(dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.ASYNC,
            parameters={},
        )

        self.assertIsNotNone(
            execution, "execute_query() must return an execution record"
        )
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)
        self.assertIn(
            execution.status,
            [
                QueryExecutionStatus.PENDING,
                QueryExecutionStatus.RUNNING,
                QueryExecutionStatus.COMPLETED,
            ],
            f"ASYNC execution should not fail with valid sources; got {execution.status}"
        )

        execution.refresh_from_db()
        retrieved_execution = QueryExecution.objects.get(id=execution.id)
        self.assertIsNotNone(retrieved_execution)
        self.assertEqual(retrieved_execution.id, execution.id)
        self.assertEqual(retrieved_execution.virtual_dataset_id, dataset.id)


class VirtualizationGetQueryResultIntegrationTest(TestCase):
    """Integration tests for get_query_result() method"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache

        reset_workflow_definition_cache()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        ensure_tenant_has_active_subscription(self.tenant)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create a test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM test_table",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Clear cache
        cache.clear()

    def test_get_query_result_integration_cached_result(self):
        """Integration test: Retrieve query result from cache after execution"""
        from django.core.cache import cache

        # Create test results
        test_results = [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
            {"id": 3, "name": "Item 3", "value": 300},
        ]

        # Simulate query execution by creating execution with cached results
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": self.virtual_dataset.query_type,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 150, "rows_processed": len(test_results)},
        )

        # Retrieve results
        result = self.service.get_query_result(execution_id=str(execution.id), format="json")

        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result["execution_id"], str(execution.id))
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["total_count"], len(test_results))
        self.assertEqual(result["returned_count"], len(test_results))
        self.assertEqual(len(result["data"]), len(test_results))
        self.assertEqual(result["data"][0]["id"], 1)
        self.assertEqual(result["data"][0]["name"], "Item 1")

    def test_get_query_result_integration_pagination_workflow(self):
        """Integration test: Full workflow with pagination"""
        from django.core.cache import cache

        # Create large test dataset
        test_results = [
            {"id": i, "name": f"Item {i}", "value": i * 10}
            for i in range(1, 251)  # 250 items
        ]

        # Cache results
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": self.virtual_dataset.query_type,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 200, "rows_processed": len(test_results)},
        )

        # Test pagination across multiple pages
        page_size = 50
        total_pages = (len(test_results) + page_size - 1) // page_size

        for page in range(1, min(4, total_pages + 1)):  # Test first 3 pages
            result = self.service.get_query_result(
                execution_id=str(execution.id),
                tenant_id=str(self.tenant.id),
                format="json",
                page=page,
                page_size=page_size,
            )

            # Verify pagination metadata
            self.assertIsNotNone(result["pagination"])
            self.assertEqual(result["pagination"]["page"], page)
            self.assertEqual(result["pagination"]["page_size"], page_size)
            self.assertEqual(result["pagination"]["total_pages"], total_pages)
            self.assertEqual(result["total_count"], len(test_results))
            self.assertEqual(
                result["returned_count"], min(page_size, len(test_results) - (page - 1) * page_size)
            )

            # Verify data integrity
            expected_start_id = (page - 1) * page_size + 1
            self.assertEqual(result["data"][0]["id"], expected_start_id)

    def test_get_query_result_integration_format_conversion(self):
        """Integration test: Format conversion (JSON -> CSV -> Parquet)"""
        import base64
        import io

        import pandas as pd
        from django.core.cache import cache

        # Create test results
        test_results = [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
        ]

        # Cache results
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": self.virtual_dataset.query_type,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Test JSON format
        json_result = self.service.get_query_result(execution_id=str(execution.id), format="json")
        self.assertEqual(json_result["format"], "json")
        self.assertIsInstance(json_result["data"], list)
        self.assertEqual(len(json_result["data"]), 2)

        # Test CSV format
        csv_result = self.service.get_query_result(execution_id=str(execution.id), format="csv")
        self.assertEqual(csv_result["format"], "csv")
        self.assertIsInstance(csv_result["data"], str)
        self.assertIn("id,name,value", csv_result["data"])
        # Verify CSV can be parsed
        df = pd.read_csv(io.StringIO(csv_result["data"]))
        self.assertEqual(len(df), 2)

        # Test Parquet format
        parquet_result = self.service.get_query_result(
            execution_id=str(execution.id), format="parquet"
        )
        self.assertEqual(parquet_result["format"], "parquet")
        self.assertIsInstance(parquet_result["data"], str)
        # Verify Parquet can be decoded and parsed
        decoded = base64.b64decode(parquet_result["data"])
        df_parquet = pd.read_parquet(io.BytesIO(decoded))
        self.assertEqual(len(df_parquet), 2)
        self.assertEqual(list(df_parquet.columns), ["id", "name", "value"])
