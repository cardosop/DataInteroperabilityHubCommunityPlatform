"""
Performance tests for Social API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class SocialAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/social/."""

    def test_social_communities_list_p95_latency(self):
        """List social communities endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/social/communities/")
