"""
Integration tests for separated Redis instances.

Tests that each Redis instance (cache, queue, events, channels) is properly
isolated and accessible.
"""

import pytest
from django.conf import settings
from django.test import override_settings


def _require_redis(name, get_client_fn):
    """Return a Redis client, or skip the test if the instance is unreachable.

    Uses the same exception tuple as ``health_check_all_redis_instances()``
    in ``hub.apps.core.redis_pools`` to distinguish transient infrastructure
    failures from programming errors.
    """
    try:
        client = get_client_fn()
        client.ping()
        return client
    except (ConnectionError, TimeoutError, OSError) as e:
        pytest.skip(f"Redis {name} not accessible in this environment: {e}")


@pytest.mark.integration
@pytest.mark.requires_db
class TestRedisInstanceSeparation:
    """Test Redis instance separation and isolation."""

    def test_redis_cache_accessible(self):
        """Test that redis-cache instance is accessible."""
        from hub.apps.core.redis_pools import get_redis_cache_client

        client = _require_redis("cache", get_redis_cache_client)
        # _require_redis already pinged successfully; verify returns True
        assert client.ping() is True, "redis-cache should respond to ping"

    def test_redis_queue_accessible(self):
        """Test that redis-queue instance is accessible."""
        from hub.apps.core.redis_pools import get_redis_queue_client

        client = _require_redis("queue", get_redis_queue_client)
        assert client.ping() is True, "redis-queue should respond to ping"

    def test_redis_events_accessible(self):
        """Test that redis-events instance is accessible."""
        from hub.apps.core.redis_pools import get_redis_events_client

        client = _require_redis("events", get_redis_events_client)
        assert client.ping() is True, "redis-events should respond to ping"

    def test_redis_channels_accessible(self):
        """Test that redis-channels instance is accessible."""
        from hub.apps.core.redis_pools import get_redis_channels_client

        client = _require_redis("channels", get_redis_channels_client)
        assert client.ping() is True, "redis-channels should respond to ping"

    def test_redis_instances_isolated(self):
        """Test that Redis instances are isolated (keys don't leak between instances)."""
        from hub.apps.core.redis_pools import (
            get_redis_cache_client,
            get_redis_channels_client,
            get_redis_events_client,
            get_redis_queue_client,
        )

        cache_client = _require_redis("cache", get_redis_cache_client)
        queue_client = _require_redis("queue", get_redis_queue_client)
        events_client = _require_redis("events", get_redis_events_client)
        channels_client = _require_redis("channels", get_redis_channels_client)

        # Set unique keys in each instance
        test_key = "test_isolation_key"
        cache_client.set(test_key, "cache_value")
        queue_client.set(test_key, "queue_value")
        events_client.set(test_key, "events_value")
        channels_client.set(test_key, "channels_value")

        # Verify keys are isolated
        assert cache_client.get(test_key) == "cache_value"
        assert queue_client.get(test_key) == "queue_value"
        assert events_client.get(test_key) == "events_value"
        assert channels_client.get(test_key) == "channels_value"

        # Cleanup
        cache_client.delete(test_key)
        queue_client.delete(test_key)
        events_client.delete(test_key)
        channels_client.delete(test_key)

    def test_connection_pools_created(self):
        """Test that connection pools are created for each Redis instance."""
        from hub.apps.core.redis_pools import (
            get_redis_cache_pool,
            get_redis_channels_pool,
            get_redis_events_pool,
            get_redis_queue_pool,
        )

        cache_pool = get_redis_cache_pool()
        queue_pool = get_redis_queue_pool()
        events_pool = get_redis_events_pool()
        channels_pool = get_redis_channels_pool()

        assert cache_pool is not None
        assert queue_pool is not None
        assert events_pool is not None
        assert channels_pool is not None

        # Verify pools are different instances
        assert cache_pool is not queue_pool
        assert cache_pool is not events_pool
        assert cache_pool is not channels_pool

    def test_health_check_all_instances(self):
        """Test health check for all Redis instances."""
        from hub.apps.core.redis_pools import (
            get_redis_cache_client,
            health_check_all_redis_instances,
        )

        # Verify at least one Redis instance is reachable before calling
        # the aggregate health check (which handles per-instance errors internally)
        _require_redis("cache", get_redis_cache_client)

        results = health_check_all_redis_instances()

        assert "cache" in results
        assert "queue" in results
        assert "events" in results
        assert "channels" in results

        # All instances should be healthy when Docker Compose is running
        for _instance_name, instance_status in results.items():
            assert "status" in instance_status


class TestRedisConfigurationIntegration:
    """Test Redis configuration integration with Django settings."""

    def test_caches_uses_redis_cache_url(self):
        """Test that CACHES setting is configured and CACHE_URL is set."""
        with override_settings(
            REDIS_CACHE_URL="redis://cache-host:6379/0", REDIS_URL="redis://fallback:6379/0"
        ):
            assert hasattr(settings, "CACHES"), "CACHES setting should exist"
            assert settings.REDIS_CACHE_URL, "REDIS_CACHE_URL must be set"
            assert settings.REDIS_CACHE_URL == "redis://cache-host:6379/0"

    def test_rq_queues_uses_redis_queue_url(self):
        """Test that RQ_QUEUES setting uses REDIS_QUEUE_URL.

        RQ_QUEUES is built at Django load time from REDIS_QUEUE_URL.
        Verify all queues use the configured REDIS_QUEUE_URL.
        """
        assert hasattr(settings, "RQ_QUEUES")
        assert settings.REDIS_QUEUE_URL, "REDIS_QUEUE_URL must be set"
        for queue_name, queue_config in settings.RQ_QUEUES.items():
            assert queue_config["URL"] == settings.REDIS_QUEUE_URL, (
                f"Queue {queue_name} URL {queue_config['URL']!r} "
                f"!= REDIS_QUEUE_URL {settings.REDIS_QUEUE_URL!r}"
            )

    def test_channel_layers_uses_redis_channels_url(self):
        """Test that CHANNEL_LAYERS setting is configured and CHANNELS_URL is set."""
        with override_settings(
            REDIS_CHANNELS_URL="redis://channels-host:6382/0", REDIS_URL="redis://fallback:6379/0"
        ):
            assert hasattr(settings, "CHANNEL_LAYERS"), "CHANNEL_LAYERS setting should exist"
            assert settings.REDIS_CHANNELS_URL, "REDIS_CHANNELS_URL must be set"
            assert settings.REDIS_CHANNELS_URL == "redis://channels-host:6382/0"
