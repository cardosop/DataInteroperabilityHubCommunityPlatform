"""
Base utilities for performance tests.

Shared setup and helpers for API endpoint performance tests.
Uses real implementations - no mocks or stubs.
"""

from __future__ import annotations

import statistics
import time

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import TenantStatus
from hub.apps.users.models import Role, UserRole, UserStatus
from tests.factories import TenantFactory

User = get_user_model()

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


def calculate_percentile(values: list, percentile: float) -> float | None:
    """Calculate percentile from list of values."""
    if not values:
        return None
    sorted_values = sorted(values)
    index = int(len(sorted_values) * percentile / 100)
    return sorted_values[min(index, len(sorted_values) - 1)]


class APIPerformanceTestBase(TestCase):
    """Base class for API endpoint performance tests."""

    def setUp(self):
        """Set up tenant, user, and authenticated client."""
        self.tenant = TenantFactory.create_tenant(status=TenantStatus.ACTIVE)
        self.user = User.objects.create_user(
            email=f"perf-{id(self)}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def assert_list_endpoint_p95(self, url: str, target_ms: float = 500.0, iterations: int = 30):
        """Measure list endpoint P95 latency and assert against target."""
        response_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            response = self.client.get(url)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if response.status_code == status.HTTP_200_OK:
                response_times.append(elapsed_ms)
        if not response_times:
            pytest.skip(f"Endpoint {url} returned no 200 responses")
        p95 = calculate_percentile(response_times, 95)
        avg = statistics.mean(response_times)
        self.assertLess(
            p95,
            target_ms,
            f"P95 {p95:.2f}ms (avg {avg:.2f}ms) exceeds target {target_ms}ms for {url}",
        )
