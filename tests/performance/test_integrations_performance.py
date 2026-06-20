"""
Performance tests for Integrations API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""

import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class IntegrationsAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/integrations/marketplace/connections/."""

    def test_marketplace_connections_list_p95_latency(self):
        """List marketplace connections endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/integrations/marketplace/connections/")
