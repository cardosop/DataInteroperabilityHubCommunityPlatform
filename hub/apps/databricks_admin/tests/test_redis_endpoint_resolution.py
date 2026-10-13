"""Pins for the real-Redis endpoint resolver (close-test-coverage-gaps 0.3).

The budget + OBO-token suites require a REAL Redis and used to hardcode
``127.0.0.1:63799`` (the host-side p313 convention), which made every
in-container batch run skip the suites — the compose stack exports
``REDIS_CACHE_URL=redis://redis-cache-test:6379/0`` and the hardcoded host
endpoint is unreachable from inside the container. ``redis_endpoint()``
resolves the endpoint the same way the app does (env first, legacy host
probe as the host-side fallback), so the W16 guard only fires when NO
reachable Redis exists in the current context.

Pure-function drills — the resolution is environment-independent (explicit
environ dicts), so this module runs identically in-container and host-side.
"""

from hub.apps.databricks_admin.tests._fixtures import (
    REDIS_HOST_DB,
    REDIS_HOST_PORT,
    redis_endpoint,
)


class TestRedisEndpointResolution:
    def test_env_url_wins_over_the_legacy_host_probe(self):
        endpoint = redis_endpoint({"REDIS_CACHE_URL": "redis://redis-cache-test:6379/0"})
        assert endpoint == ("redis-cache-test", 6379, 0)

    def test_env_url_db_path_is_honored(self):
        endpoint = redis_endpoint({"REDIS_CACHE_URL": "redis://cache:6380/13"})
        assert endpoint == ("cache", 6380, 13)

    def test_env_url_without_port_defaults_to_6379(self):
        endpoint = redis_endpoint({"REDIS_CACHE_URL": "redis://cache/5"})
        assert endpoint == ("cache", 6379, 5)

    def test_redis_url_fallback_when_cache_url_absent(self):
        endpoint = redis_endpoint({"REDIS_URL": "redis://other:6390/2"})
        assert endpoint == ("other", 6390, 2)

    def test_redis_cache_url_preferred_over_redis_url(self):
        endpoint = redis_endpoint(
            {
                "REDIS_CACHE_URL": "redis://cache-test:6379/0",
                "REDIS_URL": "redis://other:6390/2",
            }
        )
        assert endpoint == ("cache-test", 6379, 0)

    def test_no_env_falls_back_to_the_host_side_probe(self):
        endpoint = redis_endpoint({})
        assert endpoint == ("127.0.0.1", REDIS_HOST_PORT, REDIS_HOST_DB)

    def test_host_side_defaults_match_the_runbook_convention(self):
        assert REDIS_HOST_PORT == 63799
        assert REDIS_HOST_DB == 13
