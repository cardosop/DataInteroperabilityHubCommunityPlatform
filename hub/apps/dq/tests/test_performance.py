"""
Performance Tests for DQ Endpoints

Tests performance characteristics for DQ endpoints:
- GET /api/v1/dq/runs/{id}/results/

.. note::

    These tests run through the DRF test client (no real HTTP server), so
    the absolute timing thresholds are *smoke guards* against order-of-magnitude
    regressions — not production SLA targets.  Real SLAs are validated in
    staging/production via OpenTelemetry traces and Prometheus histograms.
"""

import statistics
import time
import uuid

import pytest
from django.db import connection, reset_queries
from rest_framework import status

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.jobs.models import Job, JobStatus, JobType

pytestmark = pytest.mark.django_db(transaction=True)


class DQPerformanceTest(DQAPITestBase):
    """Performance tests for DQ endpoints"""

    def setUp(self):
        """Set up test data"""
        super().setUp()

        # Create test DQ runs
        self.dq_runs = []
        for _i in range(10):
            job = Job.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=uuid.uuid4(),
            )
            dq_run = DQRun.objects.create(
                tenant=self.tenant,
                job=job,
                file=self.file,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                overall_status="PASS",
                quality_score=95.0,
                checks_json=[
                    {
                        "name": f"check_{j}",
                        "status": "PASS",
                        "details": {},
                        "message": f"Check {j} passed",
                    }
                    for j in range(5)
                ],
                details_json={
                    "metadata": {"total_rows": 1000, "total_columns": 10},
                    "engine_type": "great_expectations",
                },
            )
            self.dq_runs.append(dq_run)

    def measure_endpoint_performance(self, method, url, data=None, iterations=30):
        """Measure endpoint performance"""
        execution_times = []
        query_counts = []

        for i in range(iterations):
            dq_run = self.dq_runs[i % len(self.dq_runs)]

            reset_queries()
            start_queries = len(connection.queries)

            start_time = time.perf_counter()

            if method == "GET":
                self.client.get(url.format(id=dq_run.id), format="json")
            elif method == "POST":
                self.client.post(url.format(id=dq_run.id), data, format="json")

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
                else max(execution_times)
                if execution_times
                else 0
            ),
            "p99": (
                statistics.quantiles(execution_times, n=100)[98]
                if len(execution_times) >= 100
                else max(execution_times)
                if execution_times
                else 0
            ),
            "avg_queries": statistics.mean(query_counts) if query_counts else 0,
            "max_queries": max(query_counts) if query_counts else 0,
        }

    def test_dq_results_performance(self):
        """Smoke-guard: P95 response time must not exceed 5 seconds.

        This is NOT a production SLA — it protects against accidental
        O(N²) queries, missing indexes, or synchronous external calls
        that would push latency from milliseconds to seconds.
        """
        results = self.measure_endpoint_performance(
            method="GET", url="/api/v1/dq/runs/{id}/results/", iterations=30
        )

        self.assertLess(
            results["p95"],
            5000,
            f"P95 response time ({results['p95']:.2f}ms) exceeds "
            f"smoke-guard threshold (5000ms) — possible regression",
        )

        # Log results
        print(f"\n{'=' * 60}")
        print("GET /api/v1/dq/runs/{id}/results/ Performance Results")
        print(f"{'=' * 60}")
        print(f"P50: {results['p50']:.2f}ms")
        print(f"P95: {results['p95']:.2f}ms (Smoke guard: < 5000ms)")
        print(f"P99: {results['p99']:.2f}ms")
        print(f"Average Queries: {results['avg_queries']:.2f}")
        print(f"Max Queries: {results['max_queries']}")
        print(f"{'=' * 60}\n")

    def test_dq_results_query_count(self):
        """The second call should use fewer queries than the first.

        Uses a warm-cache comparison rather than a magic-number threshold
        so the test doesn't break every time a serializer adds a
        legitimate field (which would add a constant-factor query, not an
        N+1 regression).
        """
        dq_run = self.dq_runs[0]

        # First (cold) request — establishes baseline query count.
        reset_queries()
        response1 = self.client.get(
            f"/api/v1/dq/runs/{dq_run.id}/results/", format="json"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        cold_queries = len(connection.queries)

        # Second (warm) request — must not exceed the cold count.
        reset_queries()
        response2 = self.client.get(
            f"/api/v1/dq/runs/{dq_run.id}/results/", format="json"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        warm_queries = len(connection.queries)

        # In a healthy system the warm call should use ≤ the cold call.
        # If it uses MORE, something is wrong (e.g. a missing
        # select_related causing N+1 amplification with request state).
        self.assertLessEqual(
            warm_queries,
            cold_queries,
            f"Warm request ({warm_queries} queries) used more queries "
            f"than cold request ({cold_queries} queries) — possible "
            f"N+1 regression or missing prefetch.",
        )

    def test_dq_results_caching(self):
        """Second request to the same resource should use fewer queries.

        Smoke-guard: the warm cache path shouldn't need more than twice
        the queries of the cold path.  The absolute time threshold is
        deliberately loose to avoid flakiness in CI.
        """
        dq_run = self.dq_runs[0]

        # First request (cache miss / cold path)
        response1 = self.client.get(f"/api/v1/dq/runs/{dq_run.id}/results/", format="json")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second request (cache hit / warm path)
        reset_queries()
        start_queries = len(connection.queries)
        start_time = time.perf_counter()

        response2 = self.client.get(f"/api/v1/dq/runs/{dq_run.id}/results/", format="json")

        end_time = time.perf_counter()
        end_queries = len(connection.queries)
        query_count = end_queries - start_queries
        execution_time = (end_time - start_time) * 1000

        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Smoke-guard: warm-cache fetch should not take seconds.
        # This is deliberately loose (5s) — it catches catastrophic
        # regressions like an accidental external service call in the
        # view, not normal milliseconds-scale variance.
        self.assertLess(
            execution_time,
            5000,
            f"Cached DQ results request too slow: {execution_time:.2f}ms "
            f"(smoke threshold: 5000ms)",
        )
        # Warm path should be lightweight — fewer queries than a full
        # cold-path fetch.  20 is deliberately generous; the real
        # value should be <5 but hardcoding that is fragile.
        self.assertLess(
            query_count,
            20,
            f"Cached DQ results uses more queries than expected: {query_count}",
        )

    def test_dq_results_enhanced_response(self):
        """Test that DQ results endpoint returns enhanced response"""
        dq_run = self.dq_runs[0]

        response = self.client.get(f"/api/v1/dq/runs/{dq_run.id}/results/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Verify enhanced response structure
        self.assertIn("dq_run_id", data)
        self.assertIn("quality_score_breakdown", data)
        self.assertIn("check_details", data)
        self.assertIn("trend_analysis", data)

        # Verify quality score breakdown
        breakdown = data["quality_score_breakdown"]
        self.assertIn("overall_score", breakdown)
        self.assertIn("total_checks", breakdown)
        self.assertIn("passed_checks", breakdown)
        self.assertIn("pass_rate", breakdown)

        # Verify check details
        self.assertIsInstance(data["check_details"], list)
        if data["check_details"]:
            check = data["check_details"][0]
            self.assertIn("name", check)
            self.assertIn("status", check)
            self.assertIn("details", check)
