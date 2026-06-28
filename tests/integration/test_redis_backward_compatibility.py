"""
Backward compatibility tests for Redis configuration.

Tests that the system correctly falls back to REDIS_URL when the
instance-specific Redis URL is not configured.
"""

import pytest
from django.conf import settings
from django.test import override_settings

from hub.apps.core.redis_pools import _get_redis_url_with_fallback


class TestRedisURLFallback:
    """Verify _get_redis_url_with_fallback returns REDIS_URL when a
    specific instance URL is not set."""

    def test_fallback_cache_url(self):
        with override_settings(REDIS_CACHE_URL=None, REDIS_URL="redis://main:6379/0"):
            url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
            assert url == "redis://main:6379/0"

    def test_fallback_queue_url(self):
        with override_settings(REDIS_QUEUE_URL=None, REDIS_URL="redis://main:6379/0"):
            url = _get_redis_url_with_fallback("REDIS_QUEUE_URL", 6380)
            assert url == "redis://main:6379/0"

    def test_fallback_events_url(self):
        with override_settings(REDIS_EVENTS_URL=None, REDIS_URL="redis://main:6379/0"):
            url = _get_redis_url_with_fallback("REDIS_EVENTS_URL", 6381)
            assert url == "redis://main:6379/0"

    def test_fallback_channels_url(self):
        with override_settings(REDIS_CHANNELS_URL=None, REDIS_URL="redis://main:6379/0"):
            url = _get_redis_url_with_fallback("REDIS_CHANNELS_URL", 6382)
            assert url == "redis://main:6379/0"

    def test_uses_specific_url_when_set(self):
        """When the specific Redis URL is set, it should be used — not REDIS_URL."""
        with override_settings(
            REDIS_CACHE_URL="redis://cache:6379/0",
            REDIS_URL="redis://main:6379/0",
        ):
            url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
            assert url == "redis://cache:6379/0"

    def test_all_four_instances_fallback(self):
        """When all four instance URLs are None, all fall back to REDIS_URL."""
        with override_settings(
            REDIS_CACHE_URL=None,
            REDIS_QUEUE_URL=None,
            REDIS_EVENTS_URL=None,
            REDIS_CHANNELS_URL=None,
            REDIS_URL="redis://main:6379/0",
        ):
            for setting_name in (
                "REDIS_CACHE_URL", "REDIS_QUEUE_URL",
                "REDIS_EVENTS_URL", "REDIS_CHANNELS_URL",
            ):
                url = _get_redis_url_with_fallback(setting_name, 6379)
                assert url == "redis://main:6379/0", (
                    f"{setting_name} should fall back to REDIS_URL"
                )


class TestIdempotencyRedisFallback:
    """Verify idempotency middleware uses the cache Redis (which may fall back)."""

    def test_get_redis_client_returns_client_or_skips(self):
        """get_redis_client() should return a client when Redis is reachable.

        When Redis is not reachable the test skips — this is an infra
        check, not a logic bug.
        """
        with override_settings(REDIS_CACHE_URL=None, REDIS_URL="redis://localhost:6379/0"):
            from hub.apps.api.middleware.idempotency_utils import get_redis_client

            try:
                client = get_redis_client()
                assert client is not None, "get_redis_client() returned None"
                # Verify the client can actually communicate
                assert client.ping(), "Redis ping failed"
            except (ConnectionError, TimeoutError, OSError):
                pytest.skip("Redis not reachable — skipping connectivity test")
            except Exception as exc:
                # redis.exceptions.ConnectionError inherits from Exception,
                # not the built-in ConnectionError.  Catch any Redis-level
                # transport failures and skip rather than fail.
                if "Connection" in type(exc).__name__ or "Redis" in type(exc).__name__:
                    pytest.skip(f"Redis transport error — skipping: {exc}")
                raise
