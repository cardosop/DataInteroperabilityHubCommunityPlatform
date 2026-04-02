"""
Performance tests for Virtualization API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class VirtualizationAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/virtualization/datasets/."""

    def test_virtual_datasets_list_p95_latency(self):
        """List virtual datasets endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/virtualization/datasets/")
