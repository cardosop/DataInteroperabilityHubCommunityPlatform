"""
Performance Tests for Search Endpoints

Tests performance requirements for search endpoints:
- GET /api/v1/search/search/ - Target: < 200ms p95

These tests use real services and infrastructure (no mocks).
"""
import uuid

import statistics
import time

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.search.models import SearchIndex
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class SearchPerformanceTest(TestCase):
    """Performance tests for search endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

        # Create test search indices
        self.search_indices = []
        for i in range(20):
            index = SearchIndex.objects.create(
                tenant=self.tenant,
                resource_id=uuid.uuid4(),
                resource_type="ASSET",
                title=f"Test Asset {i}",
                description=f"Description {i}",
                domain="test",
                quality_status="PASS",
                compliance_status="PASS",
            )
            self.search_indices.append(index)

    def measure_endpoint_performance(self, method, url, data=None, iterations=50):
        """Measure endpoint performance"""
        execution_times = []
        query_counts = []

        for i in range(iterations):
            reset_queries()
            start_queries = len(connection.queries)

            start_time = time.perf_counter()

            if method == "GET":
                response = self.client.get(url, format="json")
            elif method == "POST":
                response = self.client.post(url, data, format="json")

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

    def test_search_performance(self):
        """Test GET /api/v1/search/search/ performance - Target: < 200ms p95"""
        results = self.measure_endpoint_performance(
            method="GET", url="/api/v1/search/search/?q=test", iterations=50
        )

        # Assert performance targets
        self.assertLess(
            results["p95"],
            200,
            f"P95 response time ({results['p95']:.2f}ms) exceeds target (200ms)",
        )

        # Log results
        print(f"\n{'='*60}")
        print("GET /api/v1/search/search/ Performance Results")
        print(f"{'='*60}")
        print(f"P50: {results['p50']:.2f}ms")
        print(f"P95: {results['p95']:.2f}ms (Target: < 200ms)")
        print(f"P99: {results['p99']:.2f}ms")
        print(f"Average Queries: {results['avg_queries']:.2f}")
        print(f"Max Queries: {results['max_queries']}")
        print(f"{'='*60}\n")

    def test_search_query_count(self):
        """Test that search uses optimized queries"""
        reset_queries()
        start_queries = len(connection.queries)

        response = self.client.get("/api/v1/search/search/?q=test", format="json")

        end_queries = len(connection.queries)
        query_count = end_queries - start_queries

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Search should use optimized queries
        # Target: < 5 queries (1 for search, 1 for count, 0-3 for analytics)
        self.assertLess(
            query_count, 5, f"Search uses too many queries: {query_count} (target: < 5)"
        )

    def test_search_caching(self):
        """Test that search results are cached"""
        # First request (cache miss)
        response1 = self.client.get("/api/v1/search/search/?q=test", format="json")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second request (cache hit)
        reset_queries()
        start_queries = len(connection.queries)
        start_time = time.perf_counter()

        response2 = self.client.get("/api/v1/search/search/?q=test", format="json")

        end_time = time.perf_counter()
        end_queries = len(connection.queries)
        query_count = end_queries - start_queries
        execution_time = (end_time - start_time) * 1000

        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Cached request should be faster and use fewer queries
        self.assertLess(
            execution_time,
            100,  # Cached requests should be < 100ms
            f"Cached search request too slow: {execution_time:.2f}ms",
        )
        self.assertLess(
            query_count,
            3,  # Cached requests should use fewer queries
            f"Cached search uses too many queries: {query_count}",
        )

    def test_search_unauthenticated_returns_401(self):
        """Error handling: unauthenticated request to search returns 401."""
        self.client.force_authenticate(user=None)
        self.client.credentials()
        response = self.client.get("/api/v1/search/search/?q=test", format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_empty_query_returns_200_filter_only(self):
        """Edge case: search with empty q (filter_only) returns 200 and structure."""
        response = self.client.get("/api/v1/search/search/?q=", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("total", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertIsInstance(response.data["total"], int)

    def test_search_performance_tdd_assert_status_and_structure(self):
        """TDD: Performance test asserts response status and required keys."""
        response = self.client.get("/api/v1/search/search/?q=test", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("total", response.data)
        self.assertIn("limit", response.data)
        self.assertIn("offset", response.data)
        self.assertIn("query", response.data)
