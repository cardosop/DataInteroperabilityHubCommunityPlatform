"""
Internal API key authentication for FastAPI microservices.

Every intra-service call from the Django api-service to these FastAPI
services MUST include the header:
    X-Internal-Api-Key: <INTERNAL_API_KEY env var value>

Uses hmac.compare_digest to prevent timing-based key enumeration attacks.
Raises ValueError at import/startup time if INTERNAL_API_KEY is not set,
so misconfiguration is caught at container start, not on first request.

Two enforcement mechanisms are provided:

1. InternalApiKeyMiddleware (preferred):
   BaseHTTPMiddleware that checks the header BEFORE FastAPI processes the
   request body.  This guarantees 401 is returned for bad/missing keys
   regardless of whether the request body is valid or malformed — avoiding
   the FastAPI ordering issue where 422 (body validation) would otherwise
   take priority over 401 (auth) when using route-level Depends.

   Usage:
       app.add_middleware(InternalApiKeyMiddleware)

   Public paths (/health, /metrics, /ready) are whitelisted automatically.

2. require_internal_key (Depends — kept for backward-compat):
   FastAPI dependency suitable for endpoints where the request body is
   always valid when the auth test runs (e.g. simple GET routes or
   endpoints where the test payload matches the route schema exactly).

   Usage:
       @app.post("/endpoint", dependencies=[Depends(require_internal_key)])
       async def endpoint(): ...

Phase 240.5.G — HMAC payload signature (defence-in-depth beyond TLS):

When ``DQ_REQUIRE_PAYLOAD_SIGNATURE=true`` is set in the environment,
``InternalApiKeyMiddleware`` ALSO verifies an HMAC-SHA256 signature
over the request body before passing the request to the handler.
The signature is keyed on ``DQ_SERVICE_INTERNAL_PAYLOAD_SECRET`` (a
distinct secret from ``INTERNAL_API_KEY`` so a leak of one doesn't
defeat the other) and bound to a request timestamp inside a
5-minute window so an attacker can't replay an old (body, sig) pair.

Canonical signed string:
    canonical = f"{timestamp}\\n".encode() + body
    signature = hmac.sha256(secret, canonical).hexdigest()

Headers required when enforcement is on:
    X-Internal-Payload-Signature: <hex digest>
    X-Internal-Payload-Timestamp: <unix-seconds>

Rollout (Phase 240.5.G.4): Hub side ALWAYS sends the headers. The
dq-service runs with ``DQ_REQUIRE_PAYLOAD_SIGNATURE=false`` for 7
days (soak / observation mode); flips to ``true`` after telemetry
confirms 100% Hub coverage. In soak mode the middleware accepts
unsigned requests but still verifies the signature when present
(so a passing signed request in soak mode validates the producer
contract without coupling the rollout).
"""

import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


def _load_key_at_startup() -> str:
    """
    Read INTERNAL_API_KEY from the environment at module import time.

    Raises ValueError immediately if the variable is absent or empty so
    the service process exits before accepting any connections rather than
    silently serving 500 errors on the first authenticated request.
    """
    key = os.environ.get("INTERNAL_API_KEY", "")
    if not key:
        raise ValueError(
            "INTERNAL_API_KEY environment variable is required but not set. "
            "Set it to a long random secret shared between the api-service "
            "and this FastAPI service (generate: openssl rand -hex 32)."
        )
    return key


# Validated and cached once at module import.
# If the env var is absent the process exits here — before uvicorn binds.
_INTERNAL_API_KEY: str = _load_key_at_startup()

# Previous key for zero-downtime rotation (Phase 270.C.1 — dual-key overlap).
# When non-empty, the middleware accepts BOTH the current key AND this key
# for a 24 h overlap window.  After the window closes the old key is
# removed from the ExternalSecret and this env var is unset, collapsing
# back to single-key mode with no code change or restart needed.
_INTERNAL_API_KEY_PREVIOUS: str = os.environ.get(
    "INTERNAL_API_KEY_PREVIOUS",
    "",
)


def _load_previous_expires_at_at_startup() -> int:
    """Read ``INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT`` at module import.

    The rotation Lambda writes this as a Unix epoch (int) into the SM
    SecretString.  Returns 0 when the env var is absent, empty, or
    malformed — 0 is the "no expiry" sentinel (rollout-compatibility:
    services that predate the expiry field accept the previous key
    indefinitely until the next rotation populates the field).
    """
    raw = os.environ.get("INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT", "")
    if not raw:
        return 0
    try:
        return int(raw.strip())
    except (ValueError, TypeError):
        return 0


# Cached once at module import.  0 = no expiry / malformed.
_INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT: int = _load_previous_expires_at_at_startup()

# Paths that must remain publicly reachable (no auth required).
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/metrics", "/ready"})


# ---------------------------------------------------------------------------
# Phase 240.5.G — HMAC payload signature config
# ---------------------------------------------------------------------------

# The signing secret. Optional at module-import time so a service that
# doesn't enforce signatures (rollout-soak mode OR services that aren't
# dq-service) doesn't fail to start. When enforcement is on AND the
# secret is empty, the middleware fails closed (rejects all requests
# with 503 — fail-secure).
_PAYLOAD_SECRET: str = os.environ.get("DQ_SERVICE_INTERNAL_PAYLOAD_SECRET", "")

# Replay-protection window. A signed request is accepted when
# ``abs(now - timestamp) <= _PAYLOAD_TIMESTAMP_WINDOW_SECONDS``. Five
# minutes is the spec-mandated window — long enough to absorb
# clock-drift between Hub and dq-service (NTP keeps both within seconds
# but kubelet pod restarts can briefly break sync), short enough that
# a captured (body, sig, timestamp) tuple has a tiny replay window.
_PAYLOAD_TIMESTAMP_WINDOW_SECONDS: int = 5 * 60

# Header names. Pinned here as constants so the producer
# (``hub.apps.dq.service_client``) can import them and stay aligned
# with the verifier — preventing a typo on either side from silently
# breaking signature verification.
_PAYLOAD_SIGNATURE_HEADER: str = "X-Internal-Payload-Signature"
_PAYLOAD_TIMESTAMP_HEADER: str = "X-Internal-Payload-Timestamp"


def _enforcement_enabled() -> bool:
    """Read ``DQ_REQUIRE_PAYLOAD_SIGNATURE`` at request time.

    Read-at-request (NOT cached) intentionally: the rollout flow in
    240.5.G.4 flips the flag at runtime via a Helm value change +
    pod restart; reading at request time keeps the contract simple
    and avoids a stale cached value if a future change adopts a
    config-reload mechanism that doesn't restart pods.

    Treats only the literal ``"true"`` (case-insensitive) as on.
    Any other value (``""``, ``"false"``, ``"0"``, missing) → off.
    """
    return (
        os.environ.get(
            "DQ_REQUIRE_PAYLOAD_SIGNATURE",
            "false",
        )
        .strip()
        .lower()
        == "true"
    )


def _compute_signature(body: bytes, timestamp: str, secret: str) -> str:
    """Compute the canonical HMAC-SHA256 of ``timestamp + "\\n" + body``.

    The timestamp is included in the signed canonical so an attacker
    can't replay an old ``(body, sig)`` pair with a new timestamp —
    without it, the 5-min window would be bypassable. This is a
    deliberate strengthening of the literal spec text ("sign
    payload_body") to close the replay-within-window hole.

    The producer (``hub.apps.dq.service_client``) MUST use the
    identical canonical form. The constant name and the producer's
    constant name MUST match.
    """
    canonical = timestamp.encode("utf-8") + b"\n" + body
    return hmac.new(
        secret.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()


def _verify_payload_signature(
    body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    secret: str,
    *,
    now: float | None = None,
) -> tuple[bool, str]:
    """Verify the request's HMAC signature + timestamp window.

    Returns ``(ok, reason)``. ``ok=False`` always carries a
    human-readable ``reason`` suitable for logging (NOT exposed to
    the client — the wire response says only "invalid signature" /
    "stale timestamp" to avoid leaking internal validation logic).

    Order of checks: timestamp before signature so a stale-replay
    attack rejects faster (no need to compute HMAC on a stale
    body), and the rejection reason names the specific failure for
    operators triaging logs.
    """
    if signature_header is None or signature_header == "":
        return False, "missing_signature_header"
    if timestamp_header is None or timestamp_header == "":
        return False, "missing_timestamp_header"
    try:
        ts = int(timestamp_header)
    except (TypeError, ValueError):
        return False, "malformed_timestamp"
    current = now if now is not None else time.time()
    if abs(current - ts) > _PAYLOAD_TIMESTAMP_WINDOW_SECONDS:
        return False, "stale_timestamp"
    expected = _compute_signature(body, timestamp_header, secret)
    if not hmac.compare_digest(
        expected.encode("utf-8"),
        signature_header.encode("utf-8"),
    ):
        return False, "signature_mismatch"
    return True, "ok"


class InternalApiKeyMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware that enforces X-Internal-Api-Key on every request
    except the whitelisted public paths (/health, /metrics, /ready).

    Running auth in middleware guarantees it executes BEFORE FastAPI
    parses the request body.  This means a request with a missing or
    wrong API key always gets 401 — even when the body would fail
    schema validation — eliminating the 422-before-401 ordering problem
    that occurs with route-level Depends.

    Args:
        app: The ASGI application.
        extra_public_paths: Additional paths to allow without authentication
            (e.g. ``{"/.well-known/void", "/ontology/hub"}`` for semantic
            service endpoints that must be publicly reachable).  Combined
            with the built-in ``_PUBLIC_PATHS`` whitelist at construction
            time; defaults to an empty frozenset.
    """

    def __init__(self, app, extra_public_paths: frozenset = frozenset()):
        super().__init__(app)
        self._public_paths = _PUBLIC_PATHS | frozenset(extra_public_paths)

    async def dispatch(self, request: StarletteRequest, call_next) -> StarletteResponse:
        if request.url.path in self._public_paths:
            return await call_next(request)

        key = request.headers.get("X-Internal-Api-Key")

        if not key:
            return StarletteResponse(
                content=json.dumps({"detail": "X-Internal-Api-Key header is required"}),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        key_ok = hmac.compare_digest(
            key.encode("utf-8"),
            _INTERNAL_API_KEY.encode("utf-8"),
        )
        if not key_ok and _INTERNAL_API_KEY_PREVIOUS:
            # Honor the overlap-window expiry if set. 0 = no expiry
            # (rollout-compatibility sentinel — accept indefinitely).
            if (
                _INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT == 0
                or time.time() < _INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT
            ):
                key_ok = hmac.compare_digest(
                    key.encode("utf-8"),
                    _INTERNAL_API_KEY_PREVIOUS.encode("utf-8"),
                )
        if not key_ok:
            return StarletteResponse(
                content=json.dumps({"detail": "Invalid API key"}),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Phase 240.5.G — payload signature verification.
        #
        # Only enforced when ``DQ_REQUIRE_PAYLOAD_SIGNATURE=true``.
        # In soak mode (default until Phase 240.5.G.4 day-7 flip)
        # the middleware skips this block entirely so a Hub pod
        # that's not yet sending headers stays operational.
        if _enforcement_enabled():
            # Fail-closed if enforcement is on but the signing
            # secret is missing — better to 503 than to silently
            # accept all requests because the configured ``secret``
            # is "" (which would HMAC-match against a producer
            # that ALSO happens to use an empty secret).
            if not _PAYLOAD_SECRET:
                return StarletteResponse(
                    content=json.dumps(
                        {
                            "detail": (
                                "DQ_SERVICE_INTERNAL_PAYLOAD_SECRET is "
                                "required when DQ_REQUIRE_PAYLOAD_SIGNATURE="
                                "true; service misconfigured."
                            ),
                        }
                    ),
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    media_type="application/json",
                )

            # Buffer the body via ``request.stream()`` and
            # re-inject it via ``request._receive`` so downstream
            # handlers can re-read. Same pattern as
            # ``RequestSizeLimitMiddleware`` — Starlette's
            # ``request.body()`` would consume the stream and
            # leave nothing for FastAPI to parse.
            chunks: list[bytes] = []
            async for chunk in request.stream():
                chunks.append(chunk)
            body = b"".join(chunks)

            ok, reason = _verify_payload_signature(
                body=body,
                signature_header=request.headers.get(
                    _PAYLOAD_SIGNATURE_HEADER,
                ),
                timestamp_header=request.headers.get(
                    _PAYLOAD_TIMESTAMP_HEADER,
                ),
                secret=_PAYLOAD_SECRET,
            )
            if not ok:
                # Wire response carries a generic message; the
                # specific failure reason is logged for ops.
                # Distinguishing reasons in the wire response
                # would help an attacker probe for window /
                # secret / header-name mistakes.
                if reason in ("stale_timestamp", "malformed_timestamp"):
                    detail = "stale or invalid timestamp"
                else:
                    detail = "missing or invalid signature"
                return StarletteResponse(
                    content=json.dumps({"detail": detail}),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json",
                )

            # Re-inject the buffered body so downstream handlers
            # see a complete stream.
            async def _receive():
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }

            request._receive = _receive

        return await call_next(request)


async def require_internal_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-Api-Key"),
) -> None:
    """
    FastAPI dependency that enforces internal API key authentication.

    Uses the key cached at startup — no per-request env reads.

    NOTE: Prefer InternalApiKeyMiddleware for services with POST endpoints
    that have required request bodies.  With route-level Depends, FastAPI
    validates the request body before calling this dependency, so a missing
    body returns 422 before auth can return 401.

    Usage:
        @app.post("/endpoint", dependencies=[Depends(require_internal_key)])
        async def endpoint(): ...
    """
    if x_internal_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Internal-Api-Key header is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # hmac.compare_digest prevents timing-based key enumeration
    if not hmac.compare_digest(
        x_internal_api_key.encode("utf-8"),
        _INTERNAL_API_KEY.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
