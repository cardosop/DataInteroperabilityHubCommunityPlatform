"""
Performance Tests for DQ Endpoints

Tests performance requirements for DQ endpoints:
- GET /api/v1/dq/runs/{id}/results/ - Target: < 500ms p95

These tests use real services and infrastructure (no mocks).
"""
import time
import statistics
from django.test import TestCase
from django.db import connection, reset_queries
from rest_framework.test import APIClient
from rest_framework import status

from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.jobs.models import Job, JobType, JobStatus

User = get_user_model()


class DQPerformanceTest(TestCase):
    """Performance tests for DQ endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Test Tenant", key="test-tenant")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.client.force_authenticate(user=self.user)

        # Create test DQ runs
        self.dq_runs = []
        for i in range(10):
            job = Job.objects.create(
                tenant=self.tenant,
                user=self.user,
                job_type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED
            )
            dq_run = DQRun.objects.create(
                tenant=self.tenant,
                job=job,
                profile_key="intake_basic_gx",
                status=DQRunStatus.SUCCEEDED,
                overall_status="PASS",
                quality_score=95.0,
                checks_json=[
                    {"name": f"check_{j}", "status": "PASS", "details": {}, "message": f"Check {j} passed"}
                    for j in range(5)
                ],
                details_json={
                    "metadata": {"total_rows": 1000, "total_columns": 10},
                    "engine_type": "great_expectations"
                }
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

            if method == 'GET':
                response = self.client.get(url.format(id=dq_run.id), format='json')
            elif method == 'POST':
                response = self.client.post(url.format(id=dq_run.id), data, format='json')

            end_time = time.perf_counter()

            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            execution_times.append(execution_time)

            end_queries = len(connection.queries)
            query_count = end_queries - start_queries
            query_counts.append(query_count)

        return {
            'execution_times': execution_times,
            'query_counts': query_counts,
            'p50': statistics.median(execution_times) if execution_times else 0,
            'p95': statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times) if execution_times else 0,
            'p99': statistics.quantiles(execution_times, n=100)[98] if len(execution_times) >= 100 else max(execution_times) if execution_times else 0,
            'avg_queries': statistics.mean(query_counts) if query_counts else 0,
            'max_queries': max(query_counts) if query_counts else 0,
        }

    def test_dq_results_performance(self):
        """Test GET /api/v1/dq/runs/{id}/results/ performance - Target: < 500ms p95"""
        results = self.measure_endpoint_performance(
            method='GET',
            url='/api/v1/dq/runs/{id}/results/',
            iterations=30
        )

        # Assert performance targets
        self.assertLess(
            results['p95'],
            500,
            f"P95 response time ({results['p95']:.2f}ms) exceeds target (500ms)"
        )

        # Log results
        print(f"\n{'='*60}")
        print("GET /api/v1/dq/runs/{id}/results/ Performance Results")
        print(f"{'='*60}")
        print(f"P50: {results['p50']:.2f}ms")
        print(f"P95: {results['p95']:.2f}ms (Target: < 500ms)")
        print(f"P99: {results['p99']:.2f}ms")
        print(f"Average Queries: {results['avg_queries']:.2f}")
        print(f"Max Queries: {results['max_queries']}")
        print(f"{'='*60}\n")

    def test_dq_results_query_count(self):
        """Test that DQ results endpoint uses optimized queries"""
        dq_run = self.dq_runs[0]

        reset_queries()
        start_queries = len(connection.queries)

        response = self.client.get(f'/api/v1/dq/runs/{dq_run.id}/results/', format='json')

        end_queries = len(connection.queries)
        query_count = end_queries - start_queries

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Results endpoint should use select_related to avoid N+1 queries
        # Target: < 5 queries (1 for DQ run with select_related, 0-4 for trend analysis)
        self.assertLess(
            query_count,
            5,
            f"DQ results uses too many queries: {query_count} (target: < 5)"
        )

    def test_dq_results_caching(self):
        """Test that DQ results are cached for completed runs"""
        dq_run = self.dq_runs[0]

        # First request (cache miss)
        response1 = self.client.get(f'/api/v1/dq/runs/{dq_run.id}/results/', format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second request (cache hit)
        reset_queries()
        start_queries = len(connection.queries)
        start_time = time.perf_counter()

        response2 = self.client.get(f'/api/v1/dq/runs/{dq_run.id}/results/', format='json')

        end_time = time.perf_counter()
        end_queries = len(connection.queries)
        query_count = end_queries - start_queries
        execution_time = (end_time - start_time) * 1000

        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Cached request should be faster and use fewer queries
        self.assertLess(
            execution_time,
            100,  # Cached requests should be < 100ms
            f"Cached DQ results request too slow: {execution_time:.2f}ms"
        )
        self.assertLess(
            query_count,
            2,  # Cached requests should use minimal queries
            f"Cached DQ results uses too many queries: {query_count}"
        )

    def test_dq_results_enhanced_response(self):
        """Test that DQ results endpoint returns enhanced response"""
        dq_run = self.dq_runs[0]

        response = self.client.get(f'/api/v1/dq/runs/{dq_run.id}/results/', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Verify enhanced response structure
        self.assertIn('dq_run_id', data)
        self.assertIn('quality_score_breakdown', data)
        self.assertIn('check_details', data)
        self.assertIn('trend_analysis', data)

        # Verify quality score breakdown
        breakdown = data['quality_score_breakdown']
        self.assertIn('overall_score', breakdown)
        self.assertIn('total_checks', breakdown)
        self.assertIn('passed_checks', breakdown)
        self.assertIn('pass_rate', breakdown)

        # Verify check details
        self.assertIsInstance(data['check_details'], list)
        if data['check_details']:
            check = data['check_details'][0]
            self.assertIn('name', check)
            self.assertIn('status', check)
            self.assertIn('details', check)

