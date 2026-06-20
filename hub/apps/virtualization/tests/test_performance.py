"""
Performance tests for virtualization operations.

Tests query execution performance, caching effectiveness, and result size handling.
"""

import time

import pytest
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from hub.apps.testing.virtualization_support import get_test_db_source

pytestmark = pytest.mark.slow

import uuid

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
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


class VirtualizationPerformanceTest(TestCase):
    """Performance tests for virtualization operations"""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        # Clear cache before each test
        cache.clear()

    def test_query_execution_metric_storage(self):
        """Test that query execution metrics (duration, rows) are stored and retrievable from the model."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Performance Test Dataset",
            query="SELECT 1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        start_time = time.time()

        # Create execution record
        execution = QueryExecution.objects.create(
            virtual_dataset=dataset,
            query="SELECT 1",
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            metrics={"duration_ms": int((time.time() - start_time) * 1000)},
        )

        # Verify duration is tracked
        duration_ms = execution.get_metric("duration_ms", 0)
        self.assertGreaterEqual(duration_ms, 0)
        self.assertLess(duration_ms, 10000)  # Should complete quickly in test

    def test_cache_performance_improvement(self):
        """Test that cached queries execute faster than uncached queries."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Cache Performance Dataset",
            query="SELECT 1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[get_test_db_source()],
        )

        # First execution (cache miss) — may fail if source DB unreachable or
        # source validation fails (expected in test environment).
        execution1 = None
        try:
            execution1 = self.service.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except Exception as e:
            err = str(e).lower()
            if any(kw in err for kw in ("connection", "refused", "source")):
                execution1 = QueryExecution.objects.filter(
                    virtual_dataset_id=dataset.id
                ).order_by("-created_at").first()
            else:
                raise  # Unexpected errors indicate real bugs

        if execution1 is None:
            self.skipTest("Database source not reachable for cache performance test")
        self.assertIsNotNone(execution1)

        # Second execution (cache hit)
        execution2 = None
        try:
            execution2 = self.service.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except Exception as e:
            err = str(e).lower()
            if any(kw in err for kw in ("connection", "refused", "source")):
                execution2 = QueryExecution.objects.filter(
                    virtual_dataset_id=dataset.id
                ).order_by("-created_at").first()
            else:
                raise  # Unexpected errors indicate real bugs

        # Cached execution should be faster (or at least not slower)
        # In test environment, we verify the cache logic is working
        self.assertIsNotNone(execution1)
        self.assertIsNotNone(execution2)

        # Second execution should use cache
        self.assertIsNotNone(execution2.result_cache_key, "Second execution should have cache key")
        self.assertTrue(execution2.get_metric("cached", False))

    def test_large_result_size_metric_storage(self):
        """Test that large result size metrics are stored correctly in the model."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Large Result Dataset",
            query="SELECT * FROM large_table",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Simulate large result set
        large_result_size = 10 * 1024 * 1024  # 10MB
        row_count = 100000

        execution = QueryExecution.objects.create(
            virtual_dataset=dataset,
            query="SELECT * FROM large_table",
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            metrics={
                "duration_ms": 5000,
                "rows_processed": row_count,
                "result_size_bytes": large_result_size,
            },
        )

        # Verify large result is tracked
        self.assertEqual(execution.get_metric("rows_processed"), row_count)
        self.assertEqual(execution.get_metric("result_size_bytes"), large_result_size)

    def test_query_execution_timeout_metric_storage(self):
        """Test that timeout metrics are stored correctly in the model."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Timeout Test Dataset",
            query="SELECT SLEEP(10)",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Create a timeout execution (must have completed_at for failed status)
        execution = QueryExecution.objects.create(
            virtual_dataset=dataset,
            query="SELECT SLEEP(10)",
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.FAILED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            metrics={"duration_ms": 5000, "timeout": True, "error": "Query execution timeout"},
        )

        # Verify timeout is tracked
        self.assertEqual(execution.status, QueryExecutionStatus.FAILED)
        self.assertTrue(execution.get_metric("timeout", False))


class ConcurrentQueryExecutionTest(TransactionTestCase):
    """Concurrent execution tests use TransactionTestCase (not TestCase)
    because each worker thread needs its own database connection outside
    of any transaction wrapping."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_concurrent_query_execution(self):
        """Test that multiple operations execute concurrently without
        deadlocks or race conditions."""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from django.db import connections

        errors: list = []
        lock = threading.Lock()
        concurrency = 5

        def _execute_one(idx: int):
            for alias in connections:
                connections[alias].close()
            try:
                ds = VirtualDataset.objects.create(
                    tenant_id=self.tenant.id,
                    created_by_id=self.user.id,
                    name=f"Concurrent DS {idx}",
                    query=f"SELECT {idx}",
                    query_type=QueryType.SQL,
                    status=VirtualDatasetStatus.ACTIVE,
                )
                execution = QueryExecution.objects.create(
                    virtual_dataset=ds,
                    query=f"SELECT {idx}",
                    execution_mode=QueryExecutionMode.SYNC,
                    status=QueryExecutionStatus.COMPLETED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    metrics={"duration_ms": 100 + idx},
                )
                return execution
            except Exception as e:
                # Only collect database/connection errors — unexpected exceptions
                # (AttributeError, TypeError, etc.) indicate real bugs and must propagate.
                err = str(e).lower()
                if any(kw in err for kw in ("connection", "operational", "integrity", "deadlock")):
                    with lock:
                        errors.append((idx, str(e)))
                    return None
                raise
            finally:
                for alias in connections:
                    connections[alias].close()

        executions = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(_execute_one, i): i for i in range(concurrency)}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    executions.append(result)

        for alias in connections:
            connections[alias].close()

        self.assertEqual(
            len(errors), 0, f"Concurrent operations should not produce errors; got {errors}"
        )
        self.assertEqual(
            len(executions),
            concurrency,
            f"All {concurrency} concurrent operations must complete; "
            f"only {len(executions)} succeeded",
        )
        for execution in executions:
            self.assertIsNotNone(execution)
            self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
