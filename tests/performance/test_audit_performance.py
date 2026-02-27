"""
Performance tests for Audit API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
"""
import pytest

from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class AuditAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/audit/audit-events/."""

    def test_audit_events_list_p95_latency(self):
        """List audit events endpoint P95 < 500ms."""
        self.assert_list_endpoint_p95("/api/v1/audit/audit-events/")
