"""
Performance tests for DQ (Data Quality) API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""

import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class DQAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/dq/runs/."""

    def test_dq_runs_list_p95_latency(self):
        """List DQ runs endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/dq/runs/")
