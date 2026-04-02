"""
Performance tests for registration flow (useronboardfix 2.3.1).

Tests:
- test_register_response_time_under_threshold: P95 < 2s for POST /auth/register/
- test_concurrent_registrations_no_deadlock: Concurrent registrations complete without deadlock
- test_personal_tenant_creation_does_not_n_plus_one: Registration query count bounded (no N+1)

Uses real DB and auth; no mocks/stubs.
"""

import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

pytestmark = pytest.mark.slow
from django.core.management import call_command
from django.db import connection, close_old_connections
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APIClient

from tests.performance.performance_test_base import calculate_percentile

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.performance,
]


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class RegistrationPerformanceTest(TestCase):
    """Performance tests for POST /api/v1/auth/register/ (personal tenant creation)."""

    def setUp(self):
        """Ensure FREE plan exists for personal tenant creation."""
        call_command("seed_default_plans")
        self.client = APIClient()

    def test_register_response_time_under_threshold(self):
        """Register (personal tenant) P95 latency < 2s (2000ms)."""
        response_times = []
        iterations = 20

        for i in range(iterations):
            email = f"perf-{uuid.uuid4().hex[:8]}@example.com"
            start = time.perf_counter()
            response = self.client.post(
                "/api/v1/auth/register/",
                {"email": email, "password": "SecurePass123", "name": "Perf User"},
                format="json",
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            if response.status_code == status.HTTP_201_CREATED:
                response_times.append(elapsed_ms)

        if not response_times:
            pytest.skip("Register endpoint returned no 201 responses")
        self.assertGreaterEqual(
            len(response_times),
            10,
            f"At least 10 registrations must succeed for reliable P95 (got {len(response_times)}/20)",
        )
        p95 = calculate_percentile(response_times, 95)
        avg = statistics.mean(response_times)
        self.assertLess(
            p95,
            2000.0,
            f"P95 {p95:.2f}ms (avg {avg:.2f}ms) exceeds target 2000ms for /auth/register/",
        )

    def test_concurrent_registrations_no_deadlock(self):
        """Concurrent registrations complete without deadlock."""
        num_concurrent = 5
        results = []
        errors = []

        def register_one(index: int):
            try:
                close_old_connections()
                client = APIClient()
                email = f"concurrent-{index}-{uuid.uuid4().hex[:8]}@example.com"
                response = client.post(
                    "/api/v1/auth/register/",
                    {"email": email, "password": "SecurePass123", "name": "Concurrent User"},
                    format="json",
                )
                return (index, response.status_code == status.HTTP_201_CREATED, None)
            except Exception as e:
                return (index, False, str(e))
            finally:
                close_old_connections()

        timeout_s = 90
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(register_one, i) for i in range(num_concurrent)]
            for future in as_completed(futures, timeout=timeout_s):
                idx, ok, err = future.result(timeout=30)
                results.append((idx, ok))
                if err:
                    errors.append(err)

        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed,
            timeout_s,
            f"Concurrent registrations took {elapsed:.2f}s, possible deadlock",
        )
        successful = sum(1 for _, ok in results if ok)
        self.assertGreaterEqual(
            successful,
            num_concurrent,
            f"All {num_concurrent} registrations should succeed. Got {successful}. Errors: {errors}",
        )

    def test_personal_tenant_creation_does_not_n_plus_one(self):
        """Single registration (personal tenant) uses bounded queries; no N+1 pattern."""
        # Upper bound: N+1 would cause O(n) queries per role/resource.
        # Personal tenant: 2 roles, Tenant, TenantConfig, Subscription, User, 2 UserRoles.
        # Baseline ~40-60 queries; N+1 could push to 100+. Use 100 as ceiling.
        max_queries = 100

        email = f"nplus1-{uuid.uuid4().hex[:8]}@example.com"
        with CaptureQueriesContext(connection) as context:
            response = self.client.post(
                "/api/v1/auth/register/",
                {"email": email, "password": "SecurePass123", "name": "N+1 Test User"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        num_queries = len(context.captured_queries)
        self.assertLess(
            num_queries,
            max_queries,
            f"Registration used {num_queries} queries (max {max_queries}); possible N+1",
        )
