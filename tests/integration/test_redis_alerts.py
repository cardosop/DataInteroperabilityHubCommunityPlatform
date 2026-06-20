"""
Integration tests for Redis alerts.

Tests that Redis alerts are properly configured and can be triggered.
Uses PROMETHEUS_URL from env when running in Docker.
"""

import os
import time

import pytest
import requests


@pytest.mark.integration
class TestRedisAlerts:
    """Test Redis alerts."""

    @pytest.fixture
    def prometheus_url(self):
        """Get Prometheus URL from env or localhost."""
        return os.getenv("PROMETHEUS_URL", "http://localhost:9090")

@pytest.mark.skip(reason="Prometheus not accessible (check PROMETHEUS_URL)")
    def test_redis_alerts_loaded(self, prometheus_url):
        """Test that Redis alerts are loaded in Prometheus."""
        # Wait for Prometheus to load rules
        time.sleep(5)  # INTENTIONAL: e2e/integration test polling real services

        try:
            response = requests.get(f"{prometheus_url}/api/v1/rules", timeout=15)
        except requests.exceptions.ConnectionError:
        assert response.status_code == 200

        data = response.json()
        groups = data.get("data", {}).get("groups", [])

        # Find Redis alerts group
        redis_groups = [g for g in groups if "redis" in g.get("name", "").lower()]

        assert len(redis_groups) > 0, "Redis alerts group should be loaded"

        # Check for specific alerts
        redis_group = redis_groups[0]
        rules = redis_group.get("rules", [])

        alert_names = [r.get("name") for r in rules]

        expected_alerts = [
            "RedisMemoryUsageHigh",
            "RedisConnectionPoolExhaustion",
            "RedisLatencyHigh",
        ]

        for alert_name in expected_alerts:
            assert alert_name in alert_names, f"Alert {alert_name} should be configured"

@pytest.mark.skip(reason="Prometheus not accessible (check PROMETHEUS_URL)")
    def test_redis_memory_alert_rule(self, prometheus_url):
        """Test Redis memory alert rule."""
        query = "redis_memory_used_bytes / redis_memory_max_bytes > 0.80"
        try:
            response = requests.get(
                f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=15
            )
        except requests.exceptions.ConnectionError:
        assert response.status_code == 200

@pytest.mark.skip(reason="Prometheus not accessible (check PROMETHEUS_URL)")
    def test_redis_connection_pool_alert_rule(self, prometheus_url):
        """Test Redis connection pool alert rule."""
        query = "redis_connected_clients / redis_maxclients > 0.90"
        try:
            response = requests.get(
                f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=15
            )
        except requests.exceptions.ConnectionError:
        assert response.status_code == 200

@pytest.mark.skip(reason="Prometheus not accessible (check PROMETHEUS_URL)")
    def test_redis_latency_alert_rule(self, prometheus_url):
        """Test Redis latency alert rule."""
        query = "histogram_quantile(0.95, sum(rate(redis_commands_duration_seconds_bucket[5m])) by (le)) > 0.1"
        try:
            response = requests.get(
                f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=15
            )
        except requests.exceptions.ConnectionError:
        assert response.status_code == 200

@pytest.mark.skip(reason="Alertmanager not accessible")
    def test_alertmanager_receives_alerts(self, prometheus_url):
        """Test that Alertmanager can receive alerts."""
        alertmanager_url = os.getenv("ALERTMANAGER_URL", "http://localhost:9093")

        try:
            response = requests.get(f"{alertmanager_url}/api/v2/alerts", timeout=15)
            assert response.status_code == 200
        except requests.exceptions.RequestException:

@pytest.mark.skip(reason="Prometheus not accessible (check PROMETHEUS_URL)")
    def test_redis_metrics_available_for_alerts(self, prometheus_url):
        """Test that Redis metrics are available for alert evaluation."""
        time.sleep(15)  # INTENTIONAL: e2e/integration test polling real services
        metrics_to_check = [
            "redis_memory_used_bytes",
            "redis_memory_max_bytes",
            "redis_connected_clients",
            "redis_maxclients",
        ]
        try:
            for metric in metrics_to_check:
                response = requests.get(
                    f"{prometheus_url}/api/v1/query", params={"query": metric}, timeout=15
                )
                assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            data = response.json()

            # Metric should exist (may have no data points if Redis is idle)
            if data.get("status") == "success":
                # Metric is queryable
                pass
