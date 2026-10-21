"""
Performance Tests for Search Endpoints

Tests performance requirements for search endpoints:
- GET /api/v1/search/search/ - Target: < 200ms p95

These tests use real services and infrastructure (no mocks).
"""

import statistics
import time
import uuid

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
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE"
        )
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

        for _i in range(iterations):
            reset_queries()
            start_queries = len(connection.queries)

            start_time = time.perf_counter()

            if method == "GET":
                self.client.get(url, format="json")
            elif method == "POST":
                self.client.post(url, data, format="json")

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

    def _assert_sunset(self, response):
        """P3-1 (sunset 2026-08-10): the deprecated /api/v1/search/
        surface 410s via APIVersionMiddleware BEFORE any view code —
        the pre-sunset performance/caching targets are dead with the
        surface. These tests pin the sunset contract; the live-surface
        performance pin (GET /api/search/) is recorded for the search
        owning lane."""
        self.assertEqual(response.status_code, 410, response.content)
        body = response.json()
        self.assertEqual(body.get("code"), "ENDPOINT_SUNSET", response.content)
        self.assertEqual(
            body.get("details", {}).get("replacement"), "/api/search/",
            response.content,
        )

    def test_search_sunset(self):
        """GET /api/v1/search/search/ — sunset contract (the perf
        target migrates to /api/search/ per the search lane)."""
        response = self.client.get("/api/v1/search/search/?q=test", format="json")
        self._assert_sunset(response)

    def test_search_query_count_sunset(self):
        """The sunset 410 fires before any query work — zero DB queries."""
        reset_queries()
        start_queries = len(connection.queries)

        response = self.client.get("/api/v1/search/search/?q=test", format="json")

        query_count = len(connection.queries) - start_queries
        self._assert_sunset(response)
        self.assertEqual(query_count, 0)

    def test_search_caching_sunset(self):
        """Two requests both 410 — the surface is gone for everyone."""
        response1 = self.client.get("/api/v1/search/search/?q=test", format="json")
        self._assert_sunset(response1)
        response2 = self.client.get("/api/v1/search/search/?q=test", format="json")
        self._assert_sunset(response2)

    def test_search_unauthenticated_sunset(self):
        """The 410 fires BEFORE authentication — same refusal unauthenticated."""
        self.client.force_authenticate(user=None)
        self.client.credentials()
        response = self.client.get("/api/v1/search/search/?q=test", format="json")
        self._assert_sunset(response)

    def test_search_empty_query_returns_200_filter_only(self):
        """Edge case: search with empty q (filter_only) returns 200 and structure."""
        response = self.client.get("/api/search/?q=", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json() if hasattr(response, "json") else response.data
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)

    def test_search_performance_tdd_sunset(self):
        """TDD: the sunset refusal carries the standard envelope."""
        response = self.client.get("/api/v1/search/search/?q=test", format="json")
        self._assert_sunset(response)
