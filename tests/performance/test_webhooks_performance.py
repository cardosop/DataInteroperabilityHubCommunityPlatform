"""
Performance tests for Webhooks API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""

import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class WebhooksAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/webhooks/webhooks/."""

    def test_webhooks_list_p95_latency(self):
        """List webhooks endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/webhooks/webhooks/")
