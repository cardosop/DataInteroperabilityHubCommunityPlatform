"""
Integration tests for Redis health-check coverage at the HTTP layer.

These tests validate the GET /health/ endpoint's Redis instance reporting.
The original exporter-metrics tests (which called redis_exporter /metrics and
Prometheus APIs directly) were removed because:

1. They validated oliver006/redis_exporter sidecar behaviour, not application logic.
2. The redis-exporter-*-test sidecars exist in docker-compose.test.yml but are
   not in api-service-test's depends_on, so they are never started in the
   standard test workflow.
3. The app's /health/ endpoint already provides per-instance Redis status via
   HealthService.check_redis_health(), which pings each Redis instance
   directly through its connection pool.

Exporter-metrics tests belong in a dedicated E2E / infrastructure validation
suite where Prometheus + exporters are explicitly required services.
"""

from django.test import TestCase
from rest_framework.test import APIClient


class TestRedisHealthEndpoint(TestCase):
    """Integration tests for Redis health-check via GET /health/.

    The /health/ endpoint returns a flat dict mapping::

        {"redis": {"cache": "connected", "queue": "connected",
                    "events": "connected", "channels": "connected"}}
    """

    def test_health_endpoint_includes_all_four_redis_instances(self):
        """All four Redis instances appear in the health response."""
        client = APIClient()
        response = client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        redis_data = data["redis"]

        expected_instances = ["cache", "queue", "events", "channels"]
        for instance in expected_instances:
            assert instance in redis_data, (
                f"Redis instance '{instance}' missing from health response"
            )

    def test_health_endpoint_redis_status_format(self):
        """Each Redis instance reports 'connected' or 'error:' status."""
        client = APIClient()
        response = client.get("/health/")
        assert response.status_code == 200
        redis_data = response.json()["redis"]

        for instance_name, status in redis_data.items():
            assert status == "connected" or status.startswith("error:"), (
                f"Redis '{instance_name}' has unexpected status: {status}"
            )

    def test_health_endpoint_returns_non_empty(self):
        """Health endpoint returns a non-empty Redis status dict."""
        client = APIClient()
        response = client.get("/health/")
        assert response.status_code == 200
        redis_data = response.json()["redis"]
        assert isinstance(redis_data, dict)
        assert len(redis_data) > 0, "Redis status dict must not be empty"

    def test_health_endpoint_redis_values_are_strings(self):
        """Each Redis status value is a string."""
        client = APIClient()
        response = client.get("/health/")
        assert response.status_code == 200
        redis_data = response.json()["redis"]

        for instance_name, status in redis_data.items():
            assert isinstance(status, str), (
                f"Redis '{instance_name}' status must be a string, got {type(status)}"
            )
