"""P0 (openspec add-databricks-control-plane task 0.6) — OAuth M2M token cache.

No mocks: real Redis (endpoint resolved env-first via ``_fixtures.redis_endpoint``
— in-container ``REDIS_CACHE_URL``, host-side the p313 ``127.0.0.1:63799``/db13
convention — flushed per fixture, W16-gated: CI raises, local skips when no
Redis is reachable) and the real local HTTP server from ``tests/_http.py``.
Cache-hit proof = the OAuth endpoint's request count does not grow on the
second call. ``caplog`` proves the token value is never logged.
"""

import time

import pytest

from hub.apps.databricks_admin.client import (
    DatabricksApiClient,
    DatabricksApiError,
    DatabricksAuthError,
    DatabricksRateLimitError,
    DatabricksServerError,
)
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.token_cache import MAX_TOKEN_CACHE_TTL_SECONDS, M2MTokenCache

pytestmark = pytest.mark.django_db(transaction=True)

from hub.apps.databricks_admin.tests._fixtures import redis_13_client

redis_13 = pytest.fixture(autouse=False)(redis_13_client)


class TestM2MTokenCache:
    def test_set_get_roundtrip_on_real_redis(self, redis_13):
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=300)
        assert cache.get("ws-1", "cred-1") is None
        cache.set("ws-1", "cred-1", "tok-roundtrip")
        assert cache.get("ws-1", "cred-1") == "tok-roundtrip"

    def test_ttl_capped_at_55_minutes(self, redis_13):
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=9999)
        cache.set("ws-1", "cred-1", "tok-ttl")
        raw_ttl = redis_13.ttl(cache.key_for("ws-1", "cred-1"))
        assert 0 < raw_ttl <= MAX_TOKEN_CACHE_TTL_SECONDS + 1, "TTL must be capped at 55 minutes"

    def test_short_ttl_expires_for_real(self, redis_13):
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=1)
        cache.set("ws-1", "cred-1", "tok-expires")
        assert cache.get("ws-1", "cred-1") == "tok-expires"
        time.sleep(1.2)
        assert cache.get("ws-1", "cred-1") is None

    def test_keys_isolated_per_workspace_and_credential(self, redis_13):
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=300)
        cache.set("ws-1", "cred-1", "tok-a")
        cache.set("ws-2", "cred-1", "tok-b")
        cache.set("ws-1", "cred-2", "tok-c")
        assert cache.get("ws-1", "cred-1") == "tok-a"
        assert cache.get("ws-2", "cred-1") == "tok-b"
        assert cache.get("ws-1", "cred-2") == "tok-c"
        assert cache.key_for("ws-1", "cred-1") != cache.key_for("ws-1", "cred-2")

    def test_delete_removes(self, redis_13):
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=300)
        cache.set("ws-1", "cred-1", "tok-del")
        cache.delete("ws-1", "cred-1")
        assert cache.get("ws-1", "cred-1") is None

    def test_credential_key_never_contains_secret_material(self, redis_13):
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=300)
        cache.set("ws-1", "client-id-123", "tok-x")
        key = cache.key_for("ws-1", "client-id-123")
        assert "client-id-123" not in key.split(":")[-1], "credential key must be hashed"


class TestClientM2MCaching:
    def _m2m_client(self, port, redis_13, client_id="cid-1", **kwargs):
        return DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id="t1",
            auth_mode="OAUTH_M2M",
            credential_config={"client_id": client_id, "client_secret": "secret-1"},
            token_cache=M2MTokenCache(redis_client=redis_13, ttl_seconds=300),
            timeout_ms=5000,
            max_retries=2,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
            **kwargs,
        )

    def test_token_exchanged_once_then_cached(self, local_http_server, redis_13, caplog):
        import logging

        caplog.set_level(logging.DEBUG)
        RecordingHandler.script = [200, 200, 200]
        client = self._m2m_client(local_http_server, redis_13)

        client.request("GET", "workspace.list")
        client.request("GET", "workspace.list")

        token_posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(token_posts) == 1, "second call must hit the Redis cache, not the OAuth endpoint"
        for r in RecordingHandler.requests[1:]:
            assert r["headers"]["Authorization"] == "Bearer tok-abc"

    def test_different_credentials_get_own_cache_entries(self, local_http_server, redis_13):
        RecordingHandler.script = [200, 200, 200, 200]
        self._m2m_client(local_http_server, redis_13, client_id="cid-1").request(
            "GET", "workspace.list"
        )
        self._m2m_client(local_http_server, redis_13, client_id="cid-2").request(
            "GET", "workspace.list"
        )
        token_posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(token_posts) == 2, "different credentials must not share a cache entry"

    def test_exchange_failure_is_not_cached(self, local_http_server, redis_13):
        RecordingHandler.script = [401, 401]
        client = self._m2m_client(local_http_server, redis_13)
        for _ in range(2):
            with pytest.raises(DatabricksAuthError):
                client.request("GET", "workspace.list")
        token_posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(token_posts) == 2, "a failed exchange must never poison the cache"

    def test_token_value_never_logged(self, local_http_server, redis_13, caplog):
        import logging

        caplog.set_level(logging.DEBUG)
        RecordingHandler.script = [200, 200]
        self._m2m_client(local_http_server, redis_13).request("GET", "workspace.list")
        assert "tok-abc" not in caplog.text, "token value must never appear in logs"

    def test_token_endpoint_429_is_retried_then_maps_to_rate_limit(
        self, local_http_server, redis_13
    ):
        RecordingHandler.script = [429, 429]
        with pytest.raises(DatabricksRateLimitError):
            self._m2m_client(local_http_server, redis_13).request("GET", "workspace.list")
        token_posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(token_posts) == 2, "token-endpoint 429 must retry like any other call"

    def test_token_endpoint_503_maps_to_server_error(self, local_http_server, redis_13):
        RecordingHandler.script = [503, 503]
        with pytest.raises(DatabricksServerError):
            self._m2m_client(local_http_server, redis_13).request("GET", "workspace.list")

    def test_cache_ttl_derives_from_expires_in_with_safety_margin(
        self, local_http_server, redis_13
    ):
        # Spec: cached TTL must be strictly below the token's expiry.
        RecordingHandler.json_script = ['{"access_token": "tok-short", "expires_in": 120}', "{}"]
        RecordingHandler.script = [200, 200]
        cache = M2MTokenCache(redis_client=redis_13, ttl_seconds=300)
        client = self._m2m_client(local_http_server, redis_13)
        client._token_cache = cache
        client.request("GET", "workspace.list")
        key = cache.key_for(f"http://127.0.0.1:{local_http_server}", "cid-1|secret-1")
        raw_ttl = redis_13.ttl(key)
        assert 0 < raw_ttl <= 61, f"TTL {raw_ttl} must be ≤ expires_in(120) - safety(60)"

    def test_empty_access_token_raises_auth_error(self, local_http_server, redis_13):
        RecordingHandler.json_script = ['{"access_token": ""}', "{}"]
        RecordingHandler.script = [200, 200]
        with pytest.raises(DatabricksAuthError):
            self._m2m_client(local_http_server, redis_13).request("GET", "workspace.list")

    def test_malformed_token_body_raises_api_error_not_jsondecode(
        self, local_http_server, redis_13
    ):
        RecordingHandler.json_script = ["not-json"]
        RecordingHandler.script = [200]
        with pytest.raises(DatabricksApiError):
            self._m2m_client(local_http_server, redis_13).request("GET", "workspace.list")

    def test_client_supports_context_manager(self, local_http_server, redis_13):
        RecordingHandler.json_script = ['{"access_token": "tok-ctx"}', "{}"]
        RecordingHandler.script = [200, 200]
        with self._m2m_client(local_http_server, redis_13) as client:
            client.request("GET", "workspace.list")
