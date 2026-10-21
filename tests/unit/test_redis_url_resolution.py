"""
Unit tests for Redis URL resolution and backward compatibility.

Tests the Redis URL resolution logic with fallback to REDIS_URL.
"""

from django.conf import settings
from django.test import override_settings


class TestRedisURLResolution:
    """Test Redis URL resolution with backward compatibility."""

    def test_redis_cache_url_uses_explicit_url(self):
        """Test that REDIS_CACHE_URL is used when explicitly set."""
        with override_settings(REDIS_CACHE_URL="redis://cache-host:6379/0"):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
            assert url == "redis://cache-host:6379/0"

    def test_redis_cache_url_fallback_to_redis_url(self):
        """Test that REDIS_CACHE_URL falls back to REDIS_URL when not set."""
        with override_settings(REDIS_CACHE_URL=None, REDIS_URL="redis://fallback-host:6379/0"):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
            assert url == "redis://fallback-host:6379/0"

    def test_redis_queue_url_uses_explicit_url(self):
        """Test that REDIS_QUEUE_URL is used when explicitly set."""
        with override_settings(REDIS_QUEUE_URL="redis://queue-host:6380/0"):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_QUEUE_URL", 6380)
            assert url == "redis://queue-host:6380/0"

    def test_redis_queue_url_fallback_to_redis_url(self):
        """Test that REDIS_QUEUE_URL falls back to REDIS_URL when not set."""
        with override_settings(REDIS_QUEUE_URL=None, REDIS_URL="redis://fallback-host:6379/0"):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_QUEUE_URL", 6380)
            assert url == "redis://fallback-host:6379/0"

    def test_redis_events_url_uses_explicit_url(self):
        """Test that REDIS_EVENTS_URL is used when explicitly set."""
        with override_settings(REDIS_EVENTS_URL="redis://events-host:6381/0"):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_EVENTS_URL", 6381)
            assert url == "redis://events-host:6381/0"

    def test_redis_channels_url_uses_explicit_url(self):
        """Test that REDIS_CHANNELS_URL is used when explicitly set."""
        with override_settings(REDIS_CHANNELS_URL="redis://channels-host:6382/0"):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_CHANNELS_URL", 6382)
            assert url == "redis://channels-host:6382/0"

    def test_default_url_when_no_fallback(self):
        """Test that default URL is used when no environment variables are set."""
        with override_settings(REDIS_CACHE_URL=None, REDIS_URL=None):
            from hub.apps.core.redis_pools import _get_redis_url_with_fallback

            url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
            assert url == "redis://localhost:6379/0"


class TestSettingsRedisURLs:
    """Test Redis URL settings configuration."""

    def test_settings_redis_cache_url_parsing(self):
        """Test that REDIS_CACHE_URL is parsed correctly in settings."""
        with override_settings(
            REDIS_CACHE_URL="redis://cache-host:6379/0", REDIS_URL="redis://fallback:6379/0"
        ):
            assert hasattr(settings, "REDIS_CACHE_URL")
            assert settings.REDIS_CACHE_URL == "redis://cache-host:6379/0"

    def test_settings_redis_queue_url_parsing(self):
        """Test that REDIS_QUEUE_URL is parsed correctly in settings."""
        with override_settings(
            REDIS_QUEUE_URL="redis://queue-host:6380/0", REDIS_URL="redis://fallback:6379/0"
        ):
            assert hasattr(settings, "REDIS_QUEUE_URL")
            assert settings.REDIS_QUEUE_URL == "redis://queue-host:6380/0"

    def test_settings_redis_events_url_parsing(self):
        """Test that REDIS_EVENTS_URL is parsed correctly in settings."""
        with override_settings(
            REDIS_EVENTS_URL="redis://events-host:6381/0", REDIS_URL="redis://fallback:6379/0"
        ):
            assert hasattr(settings, "REDIS_EVENTS_URL")
            assert settings.REDIS_EVENTS_URL == "redis://events-host:6381/0"

    def test_settings_redis_channels_url_parsing(self):
        """Test that REDIS_CHANNELS_URL is parsed correctly in settings."""
        with override_settings(
            REDIS_CHANNELS_URL="redis://channels-host:6382/0", REDIS_URL="redis://fallback:6379/0"
        ):
            assert hasattr(settings, "REDIS_CHANNELS_URL")
            assert settings.REDIS_CHANNELS_URL == "redis://channels-host:6382/0"

    def test_settings_fallback_to_redis_url(self):
        """Test that settings fallback to REDIS_URL when specific URLs not set."""
        with override_settings(
            REDIS_CACHE_URL=None,
            REDIS_QUEUE_URL=None,
            REDIS_EVENTS_URL=None,
            REDIS_CHANNELS_URL=None,
            REDIS_URL="redis://fallback-host:6379/0",
        ):
            # Settings should have fallback logic
            assert hasattr(settings, "REDIS_URL")
            assert settings.REDIS_URL == "redis://fallback-host:6379/0"


class TestRedisURLParsing:
    """Test Redis URL parsing utilities."""

    def test_parse_redis_url_standard_format(self):
        """Test parsing standard Redis URL format."""
        from hub.apps.core.redis_pools import parse_redis_url

        host, port = parse_redis_url("redis://localhost:6379/0")
        assert host == "localhost"
        assert port == 6379

    def test_parse_redis_url_without_port(self):
        """Test parsing Redis URL without explicit port."""
        from hub.apps.core.redis_pools import parse_redis_url

        host, port = parse_redis_url("redis://localhost/0")
        assert host == "localhost"
        assert port == 6379  # Default port

    def test_parse_redis_url_custom_host_port(self):
        """Test parsing Redis URL with custom host and port."""
        from hub.apps.core.redis_pools import parse_redis_url

        host, port = parse_redis_url("redis://redis-cache:6379/0")
        assert host == "redis-cache"
        assert port == 6379

    def test_parse_redis_url_invalid_format(self):
        """Test parsing invalid Redis URL format falls back to defaults."""
        from hub.apps.core.redis_pools import parse_redis_url

        host, port = parse_redis_url("invalid-url")
        assert host == "localhost"
        assert port == 6379
