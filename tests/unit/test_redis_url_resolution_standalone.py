"""
Standalone unit tests for Redis URL resolution (no Django dependencies).

These tests can run without Django setup, making them faster and more isolated.
"""

import os
import sys
from unittest.mock import patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def test_redis_cache_url_uses_explicit_url():
    """Test that REDIS_CACHE_URL is used when explicitly set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_CACHE_URL = "redis://cache-host:6379/0"
        mock_settings.REDIS_URL = "redis://fallback:6379/0"

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
        assert url == "redis://cache-host:6379/0"


def test_redis_cache_url_fallback_to_redis_url():
    """Test that REDIS_CACHE_URL falls back to REDIS_URL when not set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_CACHE_URL = None
        mock_settings.REDIS_URL = "redis://fallback-host:6379/0"

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
        assert url == "redis://fallback-host:6379/0"


def test_redis_queue_url_uses_explicit_url():
    """Test that REDIS_QUEUE_URL is used when explicitly set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_QUEUE_URL = "redis://queue-host:6380/0"
        mock_settings.REDIS_URL = "redis://fallback:6379/0"

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_QUEUE_URL", 6380)
        assert url == "redis://queue-host:6380/0"


def test_redis_queue_url_fallback_to_redis_url():
    """Test that REDIS_QUEUE_URL falls back to REDIS_URL when not set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_QUEUE_URL = None
        mock_settings.REDIS_URL = "redis://fallback-host:6379/0"

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_QUEUE_URL", 6380)
        assert url == "redis://fallback-host:6379/0"


def test_redis_events_url_uses_explicit_url():
    """Test that REDIS_EVENTS_URL is used when explicitly set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_EVENTS_URL = "redis://events-host:6381/0"
        mock_settings.REDIS_URL = "redis://fallback:6379/0"

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_EVENTS_URL", 6381)
        assert url == "redis://events-host:6381/0"


def test_redis_channels_url_uses_explicit_url():
    """Test that REDIS_CHANNELS_URL is used when explicitly set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_CHANNELS_URL = "redis://channels-host:6382/0"
        mock_settings.REDIS_URL = "redis://fallback:6379/0"

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_CHANNELS_URL", 6382)
        assert url == "redis://channels-host:6382/0"


def test_default_url_when_no_fallback():
    """Test that default URL is used when no environment variables are set."""
    with patch("hub.apps.core.redis_pools.settings") as mock_settings:
        mock_settings.REDIS_CACHE_URL = None
        mock_settings.REDIS_URL = None

        from hub.apps.core.redis_pools import _get_redis_url_with_fallback

        url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)
        assert url == "redis://localhost:6379/0"


def test_parse_redis_url_standard_format():
    """Test parsing standard Redis URL format."""
    from hub.apps.core.redis_pools import parse_redis_url

    host, port = parse_redis_url("redis://localhost:6379/0")
    assert host == "localhost"
    assert port == 6379


def test_parse_redis_url_without_port():
    """Test parsing Redis URL without explicit port."""
    from hub.apps.core.redis_pools import parse_redis_url

    host, port = parse_redis_url("redis://localhost/0")
    assert host == "localhost"
    assert port == 6379  # Default port


def test_parse_redis_url_custom_host_port():
    """Test parsing Redis URL with custom host and port."""
    from hub.apps.core.redis_pools import parse_redis_url

    host, port = parse_redis_url("redis://redis-cache:6379/0")
    assert host == "redis-cache"
    assert port == 6379


def test_parse_redis_url_invalid_format():
    """Test parsing invalid Redis URL format falls back to defaults."""
    from hub.apps.core.redis_pools import parse_redis_url

    host, port = parse_redis_url("invalid-url")
    assert host == "localhost"
    assert port == 6379


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
