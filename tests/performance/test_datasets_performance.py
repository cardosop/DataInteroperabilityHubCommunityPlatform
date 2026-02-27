"""
Performance tests for Datasets API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class DatasetsAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/datasets/."""

    def test_datasets_list_p95_latency(self):
        """List datasets endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/datasets/")
