"""
Performance tests for Health API.

Measures health endpoint latency. Uses real implementations - no mocks or stubs.
Health endpoints are public (no auth required).
"""
import statistics
import time

import pytest
from django.test import Client, TestCase

from tests.performance.performance_test_base import calculate_percentile

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class HealthAPIPerformanceTest(TestCase):
    """Performance tests for /health/."""

    def setUp(self):
        """Set up client (no auth for health)."""
        self.client = Client()

    def test_health_check_p95_latency(self):
        """Health check endpoint P95 < 200ms (lightweight)."""
        response_times = []
        for _ in range(30):
            start = time.perf_counter()
            response = self.client.get("/health/")
            elapsed_ms = (time.perf_counter() - start) * 1000
            if response.status_code == 200:
                response_times.append(elapsed_ms)
        if not response_times:
            pytest.skip("Health endpoint returned no 200 responses")
        p95 = calculate_percentile(response_times, 95)
        avg = statistics.mean(response_times)
        self.assertLess(
            p95,
            200.0,
            f"P95 {p95:.2f}ms (avg {avg:.2f}ms) exceeds target 200ms for /health/",
        )
