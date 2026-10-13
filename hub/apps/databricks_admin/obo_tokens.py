"""OBO token vault (openspec add-databricks-control-plane task 0b.4).

- Refresh tokens are encrypted at rest via the repo's real encryption
  chain (``hub.apps.integrations.encryption`` — KMS primary, Fernet
  fallback) and stored ONLY inside ``DatabricksOBOToken`` (one row per
  binding).
- Access tokens live ONLY in the Redis cache, keyed by the binding id
  (no secret material in keys), with TTL ≤ the token's expiry.
- Single-use rotation: each successful refresh REPLACES the stored
  refresh ciphertext; workspaces that do not rotate keep the existing
  token.
- Logout revocation is BEST-EFFORT server-side (OAuth revocation
  endpoint) and ALWAYS local: the vault row is deleted, the cache is
  flushed, and ``DATABRICKS_OBO_TOKEN_REVOKED`` is emitted — a
  revocation-endpoint failure never leaves local token material behind.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import redis
from django.db import transaction

from hub.apps.core.redis_pools import get_redis_cache_pool
from hub.apps.databricks_admin.models import DatabricksOBOToken

logger = logging.getLogger(__name__)

_ACCESS_CACHE_PREFIX = "databricks:obo:access:"
_REVOKE_PATH = "/oidc/v1/revoke"
_TOKEN_PATH = "/oidc/v1/token"
_REVOKE_TIMEOUT_SECONDS = 10


class OBOAccessTokenCache:
    """Access-token cache on the repo's REAL Redis cache pool.

    Mirrors ``M2MTokenCache`` (task 0.6): an injectable ``redis_client``
    seam for real-Redis tests; keys carry the binding id only — no secret
    material in key names.
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client or redis.Redis(connection_pool=get_redis_cache_pool())

    def key_for(self, binding_id) -> str:
        return f"{_ACCESS_CACHE_PREFIX}{binding_id}"

    def get(self, binding_id) -> str | None:
        value = self._redis.get(self.key_for(binding_id))
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value

    def set(self, binding_id, token: str, expires_in_seconds: int) -> None:
        self._redis.set(
            self.key_for(binding_id),
            token,
            ex=max(1, expires_in_seconds),  # TTL ≤ expiry, floored at 1s
        )

    def delete(self, binding_id) -> None:
        self._redis.delete(self.key_for(binding_id))


_DEFAULT_ACCESS_CACHE = OBOAccessTokenCache()


class DatabricksOBOTokenError(RuntimeError):
    """Vault-operation conflict — carries a stable code for the 0b.5 flow."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def store_tokens(
    *,
    binding,
    access_token: str,
    access_expires_in: int,
    refresh_token: str | None,
    refresh_expires_at: Any | None = None,
    access_cache: OBOAccessTokenCache | None = None,
) -> DatabricksOBOToken:
    """Store (or replace) the vault row for a binding and cache the
    access token. Idempotent per binding."""
    cache = access_cache or _DEFAULT_ACCESS_CACHE
    now = datetime.now(UTC)
    with transaction.atomic():
        token, _created = DatabricksOBOToken.objects.select_for_update().get_or_create(
            binding=binding,
            defaults={"tenant": binding.tenant},
        )
        if refresh_token:
            token.set_refresh_token(refresh_token)
        if refresh_expires_at is not None:
            token.refresh_token_expires_at = refresh_expires_at
        token.access_token_expires_at = now + timedelta(seconds=access_expires_in)
        token.last_refreshed_at = now
        token.save()
    cache.set(binding.id, access_token, access_expires_in)
    return token


def get_access_token(*, binding, access_cache: OBOAccessTokenCache | None = None) -> str | None:
    """The cached access token, if still live (miss → the 0b.5 refresh flow
    re-issues)."""
    cache = access_cache or _DEFAULT_ACCESS_CACHE
    return cache.get(binding.id)


def get_refresh_token(*, binding) -> str:
    """Decrypt and return the CURRENT refresh token."""
    token = DatabricksOBOToken.objects.filter(binding=binding).first()
    if token is None:
        return ""
    return token.get_refresh_token()


def rotate_refresh_token(
    *,
    binding,
    old_refresh_token: str,
    new_access_token: str,
    new_access_expires_in: int,
    new_refresh_token: str | None,
    access_cache: OBOAccessTokenCache | None = None,
) -> DatabricksOBOToken:
    """Single-use rotation: the vault holds ONLY the new refresh token.

    Workspaces that reuse their refresh token (``new_refresh_token=None``)
    keep the existing ciphertext; the access token + cache always update.
    """
    cache = access_cache or _DEFAULT_ACCESS_CACHE
    now = datetime.now(UTC)
    with transaction.atomic():
        token = DatabricksOBOToken.objects.select_for_update().get(binding=binding)
        # Single-use guard: the caller must present the token it ACTUALLY
        # used. A concurrent refresh may have moved the vault on — a stale
        # caller's write would regress the vault to the older chain, so it
        # fails closed instead (the 0b.5 flow re-reads and retries).
        if token.get_refresh_token() != old_refresh_token:
            raise DatabricksOBOTokenError(
                "OBO_REFRESH_STALE_TOKEN",
                "the vault's refresh token moved on; re-read and retry",
            )
        if new_refresh_token:
            token.set_refresh_token(new_refresh_token)
        token.access_token_expires_at = now + timedelta(seconds=new_access_expires_in)
        token.last_refreshed_at = now
        token.save()
    cache.set(binding.id, new_access_token, new_access_expires_in)
    return token


def revoke(
    *,
    binding,
    oidc_base_url: str,
    access_cache: OBOAccessTokenCache | None = None,
) -> None:
    """Logout revocation — best-effort server-side, ALWAYS local delete.

    Emits ``DATABRICKS_OBO_TOKEN_REVOKED`` (best-effort audit; an audit-DB
    outage never blocks the local delete).
    """
    cache = access_cache or _DEFAULT_ACCESS_CACHE
    refresh_token = get_refresh_token(binding=binding)

    if refresh_token:
        try:
            response = httpx.post(
                f"{oidc_base_url}{_REVOKE_PATH}",
                data={"token": refresh_token},
                timeout=_REVOKE_TIMEOUT_SECONDS,
            )
            if not response.is_success:
                # The token may still be live at Databricks — never silent.
                logger.warning(
                    "databricks_obo_revoke_server_rejected",
                    extra={
                        "binding_id": str(binding.id),
                        "status_code": response.status_code,
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "databricks_obo_revoke_server_failed",
                extra={"binding_id": str(binding.id), "error": type(exc).__name__},
            )

    DatabricksOBOToken.objects.filter(binding=binding).delete()
    cache.delete(binding.id)

    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="DATABRICKS_OBO_TOKEN",
            action="REVOKED",
            tenant=binding.tenant,
            resource_id=str(binding.id),
            result="SUCCESS",
            details={"workspace_id": str(binding.workspace_id)},
        )
    except Exception:
        logger.warning(
            "databricks_obo_revoke_audit_failed",
            extra={"binding_id": str(binding.id)},
        )


class OBOTokenProvider:
    """OBO bearer resolution (task 0b.5) — the interactive-path token
    source for ``DatabricksApiClient`` / ``DatabricksConnector``.

    ``get_bearer()`` resolves the per-request identity: cache hit returns
    the live access token; a cold cache performs ONE refresh-token
    exchange against the workspace token endpoint and rotates the vault.
    ``refresh()`` forces that exchange (the client's one-shot 401 path).

    FAIL-CLOSED: a binding with no stored refresh token raises
    ``DatabricksOBOError`` (``DATABRICKS_OBO_REFRESH_FAILED``) BEFORE any
    network call — interactive paths never fall back to a service
    credential. A failing exchange raises the same classified code.
    """

    def __init__(
        self,
        *,
        binding,
        oidc_client_id: str,
        oidc_base_url: str,
        access_cache: OBOAccessTokenCache | None = None,
    ):
        self.binding = binding
        self.oidc_client_id = oidc_client_id
        self.oidc_base_url = str(oidc_base_url).rstrip("/")
        self.access_cache = access_cache or _DEFAULT_ACCESS_CACHE

    def get_bearer(self) -> str:
        cached = self.access_cache.get(self.binding.id)
        if cached:
            return cached
        return self.refresh()

    def refresh(self) -> str:
        from hub.apps.databricks_admin.client import DatabricksOBOError

        refresh_token = get_refresh_token(binding=self.binding)
        if not refresh_token:
            raise DatabricksOBOError(
                "No bound Databricks token for this workspace — sign in "
                "with Databricks again (fail-closed, no service-credential "
                "fallback)."
            )

        try:
            response = httpx.post(
                f"{self.oidc_base_url}{_TOKEN_PATH}",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.oidc_client_id,
                },
                timeout=15,
            )
        except httpx.HTTPError as exc:
            raise DatabricksOBOError(
                f"OBO refresh transport failure: {type(exc).__name__}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            # Classified like every other token-body failure — a raw
            # JSONDecodeError must never leak through _bearer() on the
            # cold-cache path.
            raise DatabricksOBOError(f"OBO refresh response is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise DatabricksOBOError("OBO refresh response is not a JSON object")
        if not response.is_success:
            raise DatabricksOBOError(
                f"OBO refresh rejected: {payload.get('error') or response.status_code}"
            )

        access_token = str(payload.get("access_token") or "")
        if not access_token:
            raise DatabricksOBOError("OBO refresh response had no access_token")

        expires_in = int(payload.get("expires_in") or 0) or 300
        new_refresh = payload.get("refresh_token")
        if new_refresh:
            rotate_refresh_token(
                binding=self.binding,
                old_refresh_token=refresh_token,
                new_access_token=access_token,
                new_access_expires_in=expires_in,
                new_refresh_token=str(new_refresh),
                access_cache=self.access_cache,
            )
        else:
            store_tokens(
                binding=self.binding,
                access_token=access_token,
                access_expires_in=expires_in,
                refresh_token=None,  # keep the existing refresh ciphertext
                access_cache=self.access_cache,
            )
        self._emit_refresh_audit()
        return access_token

    def _emit_refresh_audit(self) -> None:
        """Best-effort DATABRICKS_OBO_TOKEN_REFRESHED (0b.11 — an audit-DB
        outage never blocks the refresh)."""
        try:
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="DATABRICKS_OBO_TOKEN",
                action="REFRESHED",
                tenant=self.binding.tenant,
                resource_id=str(self.binding.id),
                result="SUCCESS",
                details={"workspace_id": str(self.binding.workspace_id)},
            )
        except Exception:
            logger.warning(
                "databricks_obo_refresh_audit_failed",
                extra={"binding_id": str(self.binding.id)},
            )
