"""
Performance tests for Governance API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class GovernanceAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/governance/."""

    def test_access_requests_list_p95_latency(self):
        """List access requests endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/governance/access-requests/")
