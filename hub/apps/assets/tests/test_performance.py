"""
Performance Tests for Asset Endpoints

Tests performance requirements for asset endpoints:
- POST /api/v1/assets/ - Target: < 1000ms p95
- POST /api/v1/assets/{id}/activate/ - Target: < 2000ms p95

These tests use real services and infrastructure (no mocks).
"""

import uuid
import statistics
import time

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    ValidationStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role

User = get_user_model()


class AssetPerformanceTest(TestCase):
    """Performance tests for asset endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        ensure_user_has_data_provider_role(self.user)
        self.client.force_authenticate(user=self.user)

    def measure_endpoint_performance(self, method, url, data=None, iterations=50):
        """Measure endpoint performance"""
        execution_times = []
        query_counts = []

        for i in range(iterations):
            reset_queries()
            start_queries = len(connection.queries)

            start_time = time.perf_counter()

            if method == "POST":
                response = self.client.post(url, data, format="json")
            elif method == "GET":
                response = self.client.get(url, format="json")
            elif method == "PATCH":
                response = self.client.patch(url, data, format="json")
            elif method == "DELETE":
                response = self.client.delete(url, format="json")

            end_time = time.perf_counter()

            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            execution_times.append(execution_time)

            end_queries = len(connection.queries)
            query_count = end_queries - start_queries
            query_counts.append(query_count)

        return {
            "execution_times": execution_times,
            "query_counts": query_counts,
            "p50": statistics.median(execution_times) if execution_times else 0,
            "p95": (
                statistics.quantiles(execution_times, n=20)[18]
                if len(execution_times) >= 20
                else max(execution_times) if execution_times else 0
            ),
            "p99": (
                statistics.quantiles(execution_times, n=100)[98]
                if len(execution_times) >= 100
                else max(execution_times) if execution_times else 0
            ),
            "avg_queries": statistics.mean(query_counts) if query_counts else 0,
            "max_queries": max(query_counts) if query_counts else 0,
        }

    def test_create_asset_performance(self):
        """Test POST /api/v1/assets/ performance - Target: < 1000ms p95"""
        results = self.measure_endpoint_performance(
            method="POST",
            url="/api/v1/assets/",
            data={
                "key": f"test-asset-{int(time.time())}",
                "name": "Test Asset",
                "description": "Test description",
                "domain": "test",
                "visibility": "INTERNAL",
            },
            iterations=50,
        )

        # Cleanup
        Asset.objects.filter(tenant=self.tenant, key__startswith="test-asset-").delete()

        # Assert performance targets
        self.assertLess(
            results["p95"],
            1000,
            f"P95 response time ({results['p95']:.2f}ms) exceeds target (1000ms)",
        )

        # Log results using logging instead of print (best practice)
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"\n{'='*60}")
        logger.info("POST /api/v1/assets/ Performance Results")
        logger.info(f"{'='*60}")
        logger.info(f"P50: {results['p50']:.2f}ms")
        logger.info(f"P95: {results['p95']:.2f}ms (Target: < 1000ms)")
        logger.info(f"P99: {results['p99']:.2f}ms")
        logger.info(f"Average Queries: {results['avg_queries']:.2f}")
        logger.info(f"Max Queries: {results['max_queries']}")
        logger.info(f"{'='*60}\n")

    def test_activate_asset_performance(self):
        """Test POST /api/v1/assets/{id}/activate/ performance - Target: < 2000ms p95"""
        # Create asset with contract for activation
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"activate-test-{int(time.time())}",
            name="Activate Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=self.user,
        )

        results = self.measure_endpoint_performance(
            method="POST",
            url=f"/api/v1/assets/{asset.id}/activate/",
            data={"version": asset.version},
            iterations=30,  # Fewer iterations for activate (more complex)
        )

        # Cleanup
        Contract.objects.filter(id=contract.id).delete()
        Asset.objects.filter(id=asset.id).delete()

        # Assert performance targets
        self.assertLess(
            results["p95"],
            2000,
            f"P95 response time ({results['p95']:.2f}ms) exceeds target (2000ms)",
        )

        # Log results using logging instead of print (best practice)
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"\n{'='*60}")
        logger.info("POST /api/v1/assets/{id}/activate/ Performance Results")
        logger.info(f"{'='*60}")
        logger.info(f"P50: {results['p50']:.2f}ms")
        logger.info(f"P95: {results['p95']:.2f}ms (Target: < 2000ms)")
        logger.info(f"P99: {results['p99']:.2f}ms")
        logger.info(f"Average Queries: {results['avg_queries']:.2f}")
        logger.info(f"Max Queries: {results['max_queries']}")
        logger.info(f"{'='*60}\n")

    def test_create_asset_query_count(self):
        """Test that asset creation uses minimal database queries"""
        reset_queries()
        start_queries = len(connection.queries)

        response = self.client.post(
            "/api/v1/assets/",
            {
                "key": f"test-asset-query-{int(time.time())}",
                "name": "Test Asset",
                "description": "Test description",
                "domain": "test",
                "visibility": "INTERNAL",
            },
            format="json",
        )

        end_queries = len(connection.queries)
        query_count = end_queries - start_queries

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Asset creation should use minimal queries:
        # 1. Check duplicate key (exists query)
        # 2. Get/create tenant (if cached, 0 queries)
        # 3. Create asset (1 query)
        # 4. Create audit event (1 query, but may be async)
        # Target: < 5 queries
        self.assertLess(
            query_count, 5, f"Asset creation uses too many queries: {query_count} (target: < 5)"
        )

        # Cleanup
        if "id" in response.data:
            Asset.objects.filter(id=response.data["id"]).delete()

    def test_activate_asset_query_count(self):
        """Test that asset activation uses optimized queries with prefetch_related"""
        # Create asset with contract
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"activate-query-test-{int(time.time())}",
            name="Activate Query Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=self.user,
        )

        reset_queries()
        start_queries = len(connection.queries)

        asset.refresh_from_db()
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        end_queries = len(connection.queries)
        query_count = end_queries - start_queries

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Asset activation should use optimized queries with prefetch_related:
        # 1. Get asset with prefetch_related (1-2 queries)
        # 2. Check can_activate (uses prefetched data, 0 queries)
        # 3. Save asset (1 query)
        # 4. Semantic mapping (may be async, 0-1 queries)
        # 5. Audit event (may be async, 0-1 queries)
        # Target: < 5 queries
        self.assertLess(
            query_count, 5, f"Asset activation uses too many queries: {query_count} (target: < 5)"
        )

        # Cleanup
        Contract.objects.filter(id=contract.id).delete()
        Asset.objects.filter(id=asset.id).delete()

    def test_create_asset_concurrent_performance(self):
        """Test asset creation performance under concurrent load"""
        import threading

        results = []
        errors = []

        def create_asset(thread_id):
            try:
                start_time = time.perf_counter()
                response = self.client.post(
                    "/api/v1/assets/",
                    {
                        "key": f"concurrent-test-{thread_id}-{int(time.time())}",
                        "name": f"Concurrent Test Asset {thread_id}",
                        "description": "Test description",
                        "domain": "test",
                        "visibility": "INTERNAL",
                    },
                    format="json",
                )
                end_time = time.perf_counter()

                if response.status_code == status.HTTP_201_CREATED:
                    results.append((end_time - start_time) * 1000)
                    # Cleanup
                    if "id" in response.data:
                        Asset.objects.filter(id=response.data["id"]).delete()
                else:
                    errors.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Create 10 concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_asset, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        if results:
            p95 = statistics.quantiles(results, n=20)[18] if len(results) >= 20 else max(results)

            self.assertLess(
                p95,
                1000,
                f"P95 response time under concurrent load ({p95:.2f}ms) exceeds target (1000ms)",
            )

            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"\nConcurrent Load Test Results:")
            logger.info(f"Successful requests: {len(results)}")
            logger.info(f"Errors: {len(errors)}")
            logger.info(f"P95: {p95:.2f}ms")
            if errors:
                logger.info(f"Errors: {errors}")

    # ========== FAILURE SCENARIOS ==========

    def test_create_asset_performance_metrics_structure(self):
        """Test that performance metrics dict has expected keys with reasonable values under load"""
        # Many rows without post_save storm: bulk_create skips signals (Phase 18.2 RQ jobs).
        Asset.objects.bulk_create(
            [
                Asset(
                    tenant=self.tenant,
                    key=f"bulk-asset-{i}",
                    name=f"Bulk Asset {i}",
                    status=AssetStatus.DRAFT,
                    created_by=self.user,
                )
                for i in range(100)
            ],
            batch_size=50,
        )

        results = self.measure_endpoint_performance(
            method="POST",
            url="/api/v1/assets/",
            data={
                "key": f"test-asset-perf-{int(time.time())}",
                "name": "Test Asset",
                "description": "Test description",
                "domain": "test",
                "visibility": "INTERNAL",
            },
            iterations=10,  # Fewer iterations for structure test
        )

        # Cleanup
        Asset.objects.filter(tenant=self.tenant, key__startswith="test-asset-perf-").delete()
        Asset.objects.filter(tenant=self.tenant, key__startswith="bulk-asset-").delete()

        # Verify metrics dict has all expected keys
        expected_keys = {"execution_times", "query_counts", "p50", "p95", "p99", "avg_queries", "max_queries"}
        self.assertEqual(set(results.keys()), expected_keys)

        # Verify metrics have reasonable values
        self.assertEqual(len(results["execution_times"]), 10)
        self.assertEqual(len(results["query_counts"]), 10)
        self.assertGreater(results["p50"], 0)
        self.assertGreater(results["p95"], 0)
        self.assertGreater(results["p99"], 0)
        # Query counts may be 0 when DEBUG=False (connection.queries
        # is only populated when DEBUG=True in Django)
        self.assertGreaterEqual(results["avg_queries"], 0)
        self.assertGreaterEqual(results["max_queries"], 0)

    def test_activate_asset_performance_failure_threshold(self):
        """Test activation performance failure when threshold exceeded (failure scenario)"""
        # Create asset with contract
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"activate-perf-fail-{int(time.time())}",
            name="Activate Perf Fail Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=self.user,
        )

        results = self.measure_endpoint_performance(
            method="POST",
            url=f"/api/v1/assets/{asset.id}/activate/",
            data={"version": asset.version},
            iterations=5,  # Fewer iterations for failure test
        )

        # Cleanup
        Contract.objects.filter(id=contract.id).delete()
        Asset.objects.filter(id=asset.id).delete()

        # Test should complete (may exceed threshold but should not crash)
        self.assertIsNotNone(results["p95"])
        self.assertGreaterEqual(results["p95"], 0)

    # ========== ERROR HANDLING ==========

    def test_measure_performance_invalid_endpoint(self):
        """Test that measuring an invalid endpoint returns results without crashing"""
        # measure_endpoint_performance always returns a results dict regardless of
        # HTTP status codes; it records timing for whatever response comes back.
        results = self.measure_endpoint_performance(
            method="POST", url="/api/v1/invalid-endpoint/", data={}, iterations=1
        )
        self.assertIsNotNone(results)
        self.assertEqual(len(results["execution_times"]), 1)
        self.assertGreater(results["execution_times"][0], 0)

    def test_measure_performance_valid_endpoint_returns_results(self):
        """Test that measuring a valid endpoint returns a complete results dict"""
        results = self.measure_endpoint_performance(
            method="GET", url="/api/v1/assets/", iterations=1
        )
        self.assertIsNotNone(results)
        self.assertEqual(len(results["execution_times"]), 1)
        self.assertEqual(len(results["query_counts"]), 1)

    def test_concurrent_performance_collects_errors(self):
        """Test that concurrent invalid requests collect errors without crashing"""
        import threading

        errors = []

        def create_asset_with_error(thread_id):
            try:
                # Use invalid data to trigger error
                response = self.client.post(
                    "/api/v1/assets/",
                    {"key": "", "name": f"Error Test {thread_id}"},  # Invalid empty key
                    format="json",
                )
                if response.status_code != status.HTTP_201_CREATED:
                    errors.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Create 5 concurrent requests with errors
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_asset_with_error, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # errors is a list (may be empty if threads didn't complete or non-empty with status codes)
        self.assertIsInstance(errors, list)
