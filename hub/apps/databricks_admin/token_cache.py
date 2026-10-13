"""P0 (openspec add-databricks-control-plane task 0.6) — OAuth M2M token cache.

Redis-backed cache for Databricks OAuth M2M access tokens:

- Keys are ``{prefix}:{workspace_key}:{sha256(client_id|secret)[:24]}`` —
  the credential identity is HASHED, so no secret material lands in a
  Redis key; workspace keys isolate tenants/workspaces.
- TTL is capped at ``MAX_TOKEN_CACHE_TTL_SECONDS`` (55 minutes) — below the
  default Databricks access-token lifetime, so a cached token can never be
  served past its expiry window.
- The token VALUE is never logged anywhere in this module; callers must
  keep the same discipline (the client raises masked errors only).
"""

from __future__ import annotations

import hashlib

import redis

from hub.apps.core.redis_pools import get_redis_cache_pool

DEFAULT_TOKEN_CACHE_TTL_SECONDS = 50 * 60  # 50 min — under the 55 min cap
MAX_TOKEN_CACHE_TTL_SECONDS = 55 * 60


class M2MTokenCache:
    """Real Redis token cache; injectable client for tests/tooling."""

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        ttl_seconds: int | None = None,
        key_prefix: str = "databricks_m2m_token",
    ):
        self._redis = redis_client or redis.Redis(connection_pool=get_redis_cache_pool())
        requested = ttl_seconds if ttl_seconds is not None else DEFAULT_TOKEN_CACHE_TTL_SECONDS
        self._ttl = min(max(int(requested), 1), MAX_TOKEN_CACHE_TTL_SECONDS)
        self._prefix = key_prefix

    @staticmethod
    def _credential_key(credential_ref: str) -> str:
        """Stable hash of the credential identity — never the secret itself."""
        return hashlib.sha256(credential_ref.encode("utf-8")).hexdigest()[:24]

    def key_for(self, workspace_key: str, credential_ref: str) -> str:
        return f"{self._prefix}:{workspace_key}:{self._credential_key(credential_ref)}"

    def get(self, workspace_key: str, credential_ref: str) -> str | None:
        value = self._redis.get(self.key_for(workspace_key, credential_ref))
        # The repo's default connection pools do NOT set decode_responses —
        # a raw pool returns bytes, an injected test client returns str.
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    def set(
        self,
        workspace_key: str,
        credential_ref: str,
        token: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store with an explicit TTL override (still capped at 55 min).

        Callers pass the token-lifetime-derived TTL (expires_in minus a
        safety margin); None falls back to the instance default.
        """
        effective = (
            self._ttl
            if ttl_seconds is None
            else min(max(int(ttl_seconds), 1), MAX_TOKEN_CACHE_TTL_SECONDS)
        )
        self._redis.setex(self.key_for(workspace_key, credential_ref), effective, token)

    def delete(self, workspace_key: str, credential_ref: str) -> None:
        self._redis.delete(self.key_for(workspace_key, credential_ref))
