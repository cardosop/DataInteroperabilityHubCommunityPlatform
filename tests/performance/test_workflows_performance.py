"""
Performance tests for Workflows API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class WorkflowsAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/workflows/."""

    def test_workflows_list_p95_latency(self):
        """List workflows endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/workflows/")
