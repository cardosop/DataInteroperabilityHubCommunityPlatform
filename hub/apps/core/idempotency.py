"""
Phase 250.1.D — generic idempotency-key service for write endpoints.

Implements D250.8 — every write endpoint that opts into the
idempotency contract MUST:

* Require an ``Idempotency-Key`` header on every request.
* Validate the key has the canonical format
  ``<tenant_uuid>:<sha256(body_bytes)>`` (lowercase hex SHA-256 of
  the canonical request body).
* Reject keys whose tenant prefix doesn't match the authenticated
  request tenant.
* Reject keys whose body-hash suffix doesn't match the actual body
  the server received (covers the "client retried with a tweaked
  body but reused the key" mistake).
* Cache the response (status + headers + body) keyed on the
  ``Idempotency-Key`` for 24 hours so duplicate retries within that
  window get the original deterministic response.

The cache backend is the platform Django cache (Redis in prod /
staging, locmem in unit tests). The service degrades gracefully
when the cache is unreachable — get/set failures log a warning
but do not block the request, because the alternative (5xx on
every retry while the cache is down) is worse for tenants than
losing the deduplication property for a few minutes.

Why a dedicated service module rather than a DRF mixin?

* Decouples the contract from any framework — a future GraphQL
  endpoint or async worker can call the same service.
* Lets the SDK reuse :func:`IdempotencyService.compose_key` and
  :func:`IdempotencyService.canonical_body_bytes` so server +
  client agree on the SHA-256 input byte-for-byte (no
  whitespace-induced false-mismatches).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Per D250.8 — 24 h replay window.
DEFAULT_IDEMPOTENCY_TTL_SECONDS: int = 24 * 60 * 60

#: Cache-key prefix so ops can grep / flush the idempotency
#: namespace independently of other cache entries.
_CACHE_KEY_PREFIX: str = "idempotency:v1:"

#: Cache-key prefix for the in-flight request lock (250.1.D review-pass
#: fix). Distinct from the response-cache prefix so the two surfaces
#: can be flushed independently and monitoring can grep them apart.
_LOCK_KEY_PREFIX: str = "idempotency:lock:v1:"

#: Default lock TTL — long enough for the slowest workflow to finish
#: (data-first end-to-end is bounded by ``DEFAULT_WORKFLOW_TIMEOUT_SECONDS``
#: in :mod:`asset_creation`, currently 300 s) plus a 60 s safety margin
#: so a worker that died mid-execution doesn't permanently lock the key.
#: Callers can override via :meth:`acquire_lock`.
DEFAULT_LOCK_TTL_SECONDS: int = 360

#: SHA-256 hex string is exactly 64 lowercase hex chars. Restricted
#: to lowercase per the contract — uppercase hex is a malformed key
#: (deterministic behaviour on the server requires byte-equal keys).
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Typed exceptions — each maps to a distinct API error code so the
# data-first view can return semantically-precise responses without
# string-matching.
# ---------------------------------------------------------------------------


class IdempotencyError(Exception):
    """Base class for idempotency-key validation failures."""

    code: str = "IDEMPOTENCY_ERROR"
    http_status: int = 400


class IdempotencyKeyMissing(IdempotencyError):
    code = "IDEMPOTENCY_KEY_REQUIRED"
    http_status = 400


class IdempotencyKeyMalformed(IdempotencyError):
    code = "IDEMPOTENCY_KEY_MALFORMED"
    http_status = 400


class IdempotencyKeyTenantMismatch(IdempotencyError):
    code = "IDEMPOTENCY_KEY_TENANT_MISMATCH"
    http_status = 400


class IdempotencyKeyBodyMismatch(IdempotencyError):
    code = "IDEMPOTENCY_KEY_MISMATCH"
    http_status = 409


class IdempotencyRequestInProgress(IdempotencyError):
    """Raised when a concurrent request holds the in-flight lock.

    Phase 250.1.D review-pass fix — without the lock, two parallel
    POSTs with the same ``Idempotency-Key`` would both see a cache
    MISS and both run the workflow, then race to overwrite each
    other's cached response. The lock makes the workflow execution
    mutually exclusive per key; the loser of the race gets a 409
    with ``Retry-After`` so the client can poll the cache.
    """

    code = "IDEMPOTENCY_REQUEST_IN_PROGRESS"
    http_status = 409


# ---------------------------------------------------------------------------
# Cached-response payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CachedResponse:
    """Snapshot of an HTTP response stored in the idempotency cache.

    Stored as a plain dict in Redis; this dataclass is the in-Python
    handle. Fields are the minimal set needed to reconstruct an
    equivalent ``rest_framework.response.Response``:

    * ``status_code`` — the original HTTP status (e.g. 201, 422).
    * ``data`` — the response body as JSON-serialisable dict / list
      / primitive (DRF auto-serialises on the wire).
    * ``headers`` — per-response headers we want to preserve (e.g.
      ``Retry-After`` on 503/429); we deliberately whitelist rather
      than copy everything to keep the cache footprint small and
      avoid leaking internal headers like ``X-Request-Id``.
    """

    status_code: int
    data: Any
    headers: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "data": self.data,
            "headers": dict(self.headers),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CachedResponse:
        return cls(
            status_code=int(raw["status_code"]),
            data=raw.get("data"),
            headers=dict(raw.get("headers") or {}),
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IdempotencyService:
    """Stateless helpers for the D250.8 idempotency contract.

    All methods are class- or staticmethods because the service
    holds no per-request state — the cache is the only durable
    surface and it's reached via Django's global ``cache`` import.
    """

    # ------------------------------------------------------------------
    # Key composition / parsing
    # ------------------------------------------------------------------

    @staticmethod
    def canonical_body_bytes(body: bytes | bytearray | str | dict | list) -> bytes:
        """Return the canonical byte representation used to compute the SHA.

        For dict / list payloads we serialise with ``sort_keys=True``
        and the most-compact ``separators`` so two equivalent JSON
        payloads with different whitespace produce the SAME hash.
        Raw bytes / strings pass through unchanged so callers that
        already hold the exact wire body (e.g. SDK clients) get a
        zero-cost path.
        """
        if isinstance(body, (bytes, bytearray)):
            return bytes(body)
        if isinstance(body, str):
            return body.encode("utf-8")
        if isinstance(body, (dict, list)):
            return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        raise TypeError(f"unsupported body type for canonical_body_bytes: {type(body)!r}")

    @classmethod
    def compose_key(
        cls,
        tenant_uuid: str | uuid.UUID,
        body: bytes | bytearray | str | dict | list,
    ) -> str:
        """Compose an Idempotency-Key from ``tenant_uuid`` and ``body``.

        Used by the SDK to build the header value deterministically;
        used by the server-side tests to construct valid keys.
        """
        body_bytes = cls.canonical_body_bytes(body)
        sha = hashlib.sha256(body_bytes).hexdigest()
        # Normalise tenant_uuid to its canonical lowercase string form
        # so a UUID instance and its str() yield identical keys.
        normalised_tenant = str(uuid.UUID(str(tenant_uuid)))
        return f"{normalised_tenant}:{sha}"

    @classmethod
    def parse_key(cls, key: str | None) -> tuple[uuid.UUID, str]:
        """Parse a key into ``(tenant_uuid, body_sha256_hex)`` or raise.

        The key MUST be in **canonical lowercase form** for both the
        UUID prefix and the SHA-256 suffix. ``uuid.UUID()`` accepts
        any case, but the cache uses the raw header bytes — so
        ``ABCDEF00-...:hash`` and ``abcdef00-...:hash`` would yield
        TWO separate cache entries for the same logical request,
        defeating idempotency. We therefore reject non-lowercase
        UUIDs as malformed; the SDK + ``compose_key`` always emit
        the lowercase canonical form, so well-behaved clients are
        unaffected.

        Raises:
            IdempotencyKeyMissing: ``key`` is ``None`` or empty.
            IdempotencyKeyMalformed: ``key`` doesn't match the
                canonical ``<lowercase-uuid>:<lowercase-sha256_hex>``
                shape.
        """
        if not key:
            raise IdempotencyKeyMissing("Idempotency-Key header is required for this endpoint.")
        # Exactly ONE colon separates the two fields (UUIDs themselves
        # contain hyphens, not colons; sha256 hex is colon-free).
        parts = key.split(":")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise IdempotencyKeyMalformed(
                "Idempotency-Key MUST be of the form <tenant_uuid>:<sha256(body)>."
            )
        tenant_part, sha_part = parts
        try:
            tenant_uuid = uuid.UUID(tenant_part)
        except ValueError:
            raise IdempotencyKeyMalformed("Idempotency-Key tenant prefix MUST be a valid UUID.")
        # Reject non-canonical (uppercase / mixed-case) UUIDs. The
        # canonical lowercase string from ``str(uuid.UUID(...))`` is
        # the wire form server + SDK agree on; anything else would
        # bypass the cache via key-form drift.
        if tenant_part != str(tenant_uuid):
            raise IdempotencyKeyMalformed(
                "Idempotency-Key tenant prefix MUST be in canonical "
                "lowercase UUID form (``<8>-<4>-<4>-<4>-<12>``)."
            )
        if not _SHA256_HEX_RE.match(sha_part):
            raise IdempotencyKeyMalformed(
                "Idempotency-Key suffix MUST be a 64-char lowercase SHA-256 hex digest."
            )
        return tenant_uuid, sha_part

    @classmethod
    def assert_body_matches_key(
        cls,
        key: str,
        body: bytes | bytearray | str | dict | list,
        request_tenant_uuid: str | uuid.UUID,
    ) -> tuple[uuid.UUID, str]:
        """Validate ``key`` against the actual request body + tenant.

        Returns ``(tenant_uuid, body_sha)`` on success; raises a
        typed :class:`IdempotencyError` subclass on any mismatch.
        Performs three checks in order so the most-specific error
        wins (parse → tenant → body).
        """
        tenant_uuid, sha_in_key = cls.parse_key(key)
        if str(tenant_uuid) != str(uuid.UUID(str(request_tenant_uuid))):
            raise IdempotencyKeyTenantMismatch(
                "Idempotency-Key tenant prefix does not match the authenticated tenant."
            )
        body_bytes = cls.canonical_body_bytes(body)
        actual_sha = hashlib.sha256(body_bytes).hexdigest()
        if actual_sha != sha_in_key:
            raise IdempotencyKeyBodyMismatch(
                "Idempotency-Key body hash does not match the actual "
                "request body. Either re-use the original body or "
                "send a fresh Idempotency-Key for the new body."
            )
        return tenant_uuid, actual_sha

    # ------------------------------------------------------------------
    # Cache get / store
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(idem_key: str, scope: str | None = None) -> str:
        """Namespace the raw header value behind a versioned prefix.

        The prefix lets ops bump ``v1`` to ``v2`` and instantly
        invalidate every cached response without flushing unrelated
        entries (e.g., the DQ-result cache uses its own prefix).

        ``scope`` (Phase 250.1.D review-pass fix) further partitions
        the cache so two endpoints that both opt into idempotency
        cannot collide on the same header value. Default ``None``
        keeps the global namespace for backward compatibility, but
        view callers SHOULD pass a stable scope (e.g.,
        ``"data-first"``) to lock their bucket.
        """
        if scope:
            return f"{_CACHE_KEY_PREFIX}{scope}:{idem_key}"
        return _CACHE_KEY_PREFIX + idem_key

    @staticmethod
    def _lock_key(idem_key: str, scope: str | None = None) -> str:
        """Cache key for the concurrent-request lock (review-pass fix)."""
        if scope:
            return f"{_LOCK_KEY_PREFIX}{scope}:{idem_key}"
        return _LOCK_KEY_PREFIX + idem_key

    # ------------------------------------------------------------------
    # Concurrent-request lock (Phase 250.1.D review-pass fix)
    # ------------------------------------------------------------------

    @classmethod
    def acquire_lock(
        cls,
        idem_key: str,
        scope: str | None = None,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> bool:
        """Atomically claim the in-flight slot for ``idem_key``.

        Uses ``cache.add()`` (the Django cache API's atomic "set if
        not present" primitive — backed by Redis ``SET NX`` in
        production). Returns ``True`` if this caller now owns the
        lock; ``False`` if another request already has it.

        On any cache backend failure we **return ``True``** and log
        a warning. Rationale: the cache-down degraded-mode contract
        for response caching already accepts the loss of replay
        deduplication; extending that policy to the lock means
        Redis-down doesn't turn writes into 409s. The window for
        true concurrent duplication is then (1) Redis is down AND
        (2) two requests arrive within that window — operators
        prefer that two-failure scenario over uniformly 409-ing
        every write while Redis recovers.
        """
        try:
            return bool(
                cache.add(
                    cls._lock_key(idem_key, scope),
                    "in_progress",
                    timeout=ttl_seconds,
                )
            )
        except Exception as exc:
            logger.warning(
                "idempotency_lock_acquire_failed",
                extra={
                    "idempotency_key": idem_key,
                    "scope": scope,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return True  # let the request through; see docstring

    @classmethod
    def release_lock(
        cls,
        idem_key: str,
        scope: str | None = None,
    ) -> None:
        """Release the in-flight lock for ``idem_key`` after the workflow.

        Called from a ``finally`` block on the view side so the
        lock is freed even if the workflow raised. Cache failures
        are swallowed — the lock will expire naturally via TTL,
        worst case adding a few minutes of "request in progress"
        for the same key (much better than leaking lock keys
        forever or 5xx-ing on cache failure).
        """
        try:
            cache.delete(cls._lock_key(idem_key, scope))
        except Exception as exc:
            logger.warning(
                "idempotency_lock_release_failed",
                extra={
                    "idempotency_key": idem_key,
                    "scope": scope,
                    "error": str(exc),
                },
                exc_info=True,
            )

    @classmethod
    def get_cached_response(
        cls,
        idem_key: str,
        scope: str | None = None,
    ) -> CachedResponse | None:
        """Return the cached :class:`CachedResponse` for ``idem_key``.

        Returns ``None`` for a cache miss OR for any cache backend
        failure — the latter degrades gracefully so a Redis outage
        does not block writes (250.1.D.6 contract).
        """
        try:
            raw = cache.get(cls._cache_key(idem_key, scope))
        except Exception as exc:
            logger.warning(
                "idempotency_cache_get_failed",
                extra={
                    "idempotency_key": idem_key,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return None
        if raw is None:
            return None
        try:
            return CachedResponse.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            # Corrupted cache entry — log + treat as miss; the
            # request will run normally and overwrite the bad row.
            logger.warning(
                "idempotency_cache_entry_corrupt",
                extra={
                    "idempotency_key": idem_key,
                    "error": str(exc),
                    "raw_type": type(raw).__name__,
                },
            )
            return None

    @classmethod
    def store_response(
        cls,
        idem_key: str,
        response: CachedResponse,
        ttl_seconds: int = DEFAULT_IDEMPOTENCY_TTL_SECONDS,
        scope: str | None = None,
    ) -> None:
        """Persist ``response`` keyed on ``idem_key`` for ``ttl_seconds``.

        Cache failures are logged but never raised — the response
        has already been computed and is on its way to the client;
        we MUST NOT turn a successful request into a 5xx because
        the cache write failed.
        """
        try:
            cache.set(
                cls._cache_key(idem_key, scope),
                response.to_dict(),
                timeout=ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "idempotency_cache_set_failed",
                extra={
                    "idempotency_key": idem_key,
                    "scope": scope,
                    "status_code": response.status_code,
                    "error": str(exc),
                },
                exc_info=True,
            )
