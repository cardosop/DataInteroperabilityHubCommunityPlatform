"""Live Redis + django-redis: sliding-window Lua path (skipped without infra).

Uses ``REDIS_CACHE_URL`` (docker-compose test stack). No mocks of Redis or the
rate-limit helpers.
"""

from __future__ import annotations
import pytest
import pytest

import os
import uuid


pytest.importorskip("django_redis")

import redis as redis_py  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.test import SimpleTestCase  # noqa: E402
from django.test.utils import override_settings  # noqa: E402

from hub.apps.auth.views import (  # noqa: E402
    _redis_sliding_window_zset_key,
    _sliding_window_rate_limit_allow,
)

pytestmark = [pytest.mark.integration, pytest.mark.requires_redis]


class SlidingWindowRedisLuaIntegrationTests(SimpleTestCase):
    def setUp(self):
        url = os.environ.get("REDIS_CACHE_URL")
        if not url:
            self.skipTest("REDIS_CACHE_URL not set")
        try:
            redis_py.Redis.from_url(url, socket_connect_timeout=2).ping()
        except Exception as exc:
            self.skipTest(f"Redis not reachable: {exc}")
        self.redis_url = url
        self._redis_direct = redis_py.Redis.from_url(
            url,
            decode_responses=False,
        )

    def tearDown(self):
        if hasattr(self, "_redis_direct"):
            self._redis_direct.close()

    def test_boundary_via_lua_matches_sliding_window_contract(self):
        logical_key = f"integration_sliding:{uuid.uuid4().hex}"
        caches_override = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": self.redis_url,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "IGNORE_EXCEPTIONS": False,
                },
                "KEY_PREFIX": "hub",
                "TIMEOUT": 300,
            }
        }

        with override_settings(CACHES=caches_override):
            cache.clear()
            physical = _redis_sliding_window_zset_key(logical_key)
            self._redis_direct.delete(physical)
            try:
                limit = 8
                window = 60
                for i in range(5):
                    self.assertTrue(
                        _sliding_window_rate_limit_allow(
                            key=logical_key,
                            limit=limit,
                            window_seconds=window,
                            current_ts=0.0,
                        ),
                        f"burst at t=0 request {i + 1}",
                    )
                for i in range(5):
                    allowed = _sliding_window_rate_limit_allow(
                        key=logical_key,
                        limit=limit,
                        window_seconds=window,
                        current_ts=50.0,
                    )
                    if i < 3:
                        self.assertTrue(allowed, f"boundary burst idx={i}")
                    else:
                        self.assertFalse(allowed, f"expect deny idx={i}")
            finally:
                self._redis_direct.delete(physical)
