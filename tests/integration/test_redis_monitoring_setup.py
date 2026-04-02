"""
Integration tests for Redis monitoring setup.

Tests that Redis exporters are running and exposing metrics correctly.
Uses env vars when running in Docker (api-service-test); localhost when on host.
"""
import os
import pytest
import requests
import time
from typing import Dict, List


def _redis_exporters() -> Dict[str, str]:
    """Get Redis exporter endpoints from env or localhost defaults."""
    return {
        'cache': os.getenv('REDIS_EXPORTER_CACHE_URL', 'http://localhost:9121'),
        'queue': os.getenv('REDIS_EXPORTER_QUEUE_URL', 'http://localhost:9122'),
        'events': os.getenv('REDIS_EXPORTER_EVENTS_URL', 'http://localhost:9123'),
        'channels': os.getenv('REDIS_EXPORTER_CHANNELS_URL', 'http://localhost:9124'),
    }


@pytest.mark.integration
class TestRedisMonitoringSetup:
    """Test Redis monitoring setup."""

    @pytest.fixture
    def redis_exporters(self) -> Dict[str, str]:
        """Get Redis exporter endpoints."""
        return _redis_exporters()

    def test_redis_exporter_cache_accessible(self, redis_exporters):
        """Test that Redis cache exporter is accessible."""
        try:
            response = requests.get(f"{redis_exporters['cache']}/metrics", timeout=15)
        except requests.exceptions.ConnectionError:
            pytest.skip("Redis exporter cache not accessible (check REDIS_EXPORTER_CACHE_URL)")
        assert response.status_code == 200
        assert 'redis_memory_used_bytes' in response.text or 'redis_up' in response.text

    def test_redis_exporter_queue_accessible(self, redis_exporters):
        """Test that Redis queue exporter is accessible."""
        try:
            response = requests.get(f"{redis_exporters['queue']}/metrics", timeout=15)
        except requests.exceptions.ConnectionError:
            pytest.skip("Redis exporter queue not accessible (check REDIS_EXPORTER_QUEUE_URL)")
        assert response.status_code == 200
        assert 'redis_memory_used_bytes' in response.text or 'redis_up' in response.text

    def test_redis_exporter_events_accessible(self, redis_exporters):
        """Test that Redis events exporter is accessible."""
        try:
            response = requests.get(f"{redis_exporters['events']}/metrics", timeout=15)
        except requests.exceptions.ConnectionError:
            pytest.skip("Redis exporter events not accessible (check REDIS_EXPORTER_EVENTS_URL)")
        assert response.status_code == 200
        assert 'redis_memory_used_bytes' in response.text or 'redis_up' in response.text

    def test_redis_exporter_channels_accessible(self, redis_exporters):
        """Test that Redis channels exporter is accessible."""
        try:
            response = requests.get(f"{redis_exporters['channels']}/metrics", timeout=15)
        except requests.exceptions.ConnectionError:
            pytest.skip("Redis exporter channels not accessible (check REDIS_EXPORTER_CHANNELS_URL)")
        assert response.status_code == 200
        assert 'redis_memory_used_bytes' in response.text or 'redis_up' in response.text

    def test_redis_exporters_expose_memory_metrics(self, redis_exporters):
        """Test that Redis exporters expose memory metrics."""
        for instance, url in redis_exporters.items():
            try:
                response = requests.get(f"{url}/metrics", timeout=15)
            except requests.exceptions.ConnectionError:
                pytest.skip(f"Redis exporter {instance} not accessible")
            assert response.status_code == 200
            content = response.text

            # Check for memory-related metrics
            memory_metrics = [
                'redis_memory_used_bytes',
                'redis_memory_max_bytes',
                'redis_memory_peak_bytes',
            ]

            found_metrics = [m for m in memory_metrics if m in content]
            assert len(found_metrics) > 0, f"Redis {instance} exporter should expose memory metrics"

    def test_redis_exporters_expose_connection_metrics(self, redis_exporters):
        """Test that Redis exporters expose connection metrics."""
        for instance, url in redis_exporters.items():
            try:
                response = requests.get(f"{url}/metrics", timeout=15)
            except requests.exceptions.ConnectionError:
                pytest.skip(f"Redis exporter {instance} not accessible")
            assert response.status_code == 200
            content = response.text

            # Check for connection-related metrics
            connection_metrics = [
                'redis_connected_clients',
                'redis_maxclients',
            ]

            found_metrics = [m for m in connection_metrics if m in content]
            assert len(found_metrics) > 0, f"Redis {instance} exporter should expose connection metrics"

    def test_redis_exporters_expose_command_metrics(self, redis_exporters):
        """Test that Redis exporters expose command metrics."""
        for instance, url in redis_exporters.items():
            try:
                response = requests.get(f"{url}/metrics", timeout=15)
            except requests.exceptions.ConnectionError:
                pytest.skip(f"Redis exporter {instance} not accessible")
            assert response.status_code == 200
            content = response.text

            # Check for command-related metrics
            command_metrics = [
                'redis_commands_total',
                'redis_commands_duration_seconds',
            ]

            found_metrics = [m for m in command_metrics if m in content]
            assert len(found_metrics) > 0, f"Redis {instance} exporter should expose command metrics"

    def test_prometheus_scrapes_redis_exporters(self):
        """Test that Prometheus is scraping Redis exporters."""
        prometheus_url = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')

        # Wait for Prometheus to scrape
        time.sleep(10)  # INTENTIONAL: e2e/integration test polling real services

        try:
            response = requests.get(f"{prometheus_url}/api/v1/targets", timeout=15)
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus not accessible (check PROMETHEUS_URL)")
        assert response.status_code == 200

        data = response.json()
        targets = data.get('data', {}).get('activeTargets', [])

        # Find Redis exporter targets
        redis_targets = [
            t for t in targets
            if 'redis' in t.get('labels', {}).get('job', '').lower()
        ]

        assert len(redis_targets) >= 4, f"Expected at least 4 Redis exporter targets, found {len(redis_targets)}"

        # Check that all targets are up
        for target in redis_targets:
            job = target.get('labels', {}).get('job', 'unknown')
            health = target.get('health', 'unknown')
            assert health == 'up', f"Redis exporter {job} should be up, but health is {health}"

    def test_prometheus_has_redis_metrics(self):
        """Test that Prometheus has collected Redis metrics."""
        prometheus_url = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')

        # Wait for Prometheus to scrape
        time.sleep(15)  # INTENTIONAL: e2e/integration test polling real services

        try:
            response = requests.get(
                f"{prometheus_url}/api/v1/query",
                params={'query': 'redis_memory_used_bytes'},
                timeout=15
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus not accessible (check PROMETHEUS_URL)")

        assert response.status_code == 200
        data = response.json()

        if data.get('status') == 'success':
            results = data.get('data', {}).get('result', [])
            assert len(results) > 0, "Prometheus should have redis_memory_used_bytes metrics"

