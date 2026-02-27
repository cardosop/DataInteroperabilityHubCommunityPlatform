"""
Performance tests for Compliance API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class ComplianceAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/compliance/runs/."""

    def test_compliance_runs_list_p95_latency(self):
        """List compliance runs endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/compliance/runs/")
