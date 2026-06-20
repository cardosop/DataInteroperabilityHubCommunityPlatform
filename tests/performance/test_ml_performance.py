"""
Performance tests for ML API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""

import pytest

pytestmark = pytest.mark.slow

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class MLAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/ml/models/."""

    def test_ml_models_list_p95_latency(self):
        """List ML models endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/ml/models/")
